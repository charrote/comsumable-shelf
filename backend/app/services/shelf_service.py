"""Shelf service — slot sensor polling, event recording, auto-bind logic."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.hal.modbus import Amkn8702g, SlotPoller, SlotChangeEvent, SlotState
from app.models import Shelf, ShelfSlot, ShelfSlotEvent, InventoryReel
from app.utils.database import async_session_factory

logger = logging.getLogger(__name__)


async def _slot_key_to_db(slot_key: str, shelf_id: int, db: AsyncSession) -> Optional[ShelfSlot]:
    """Resolve a slot key like 'A1-5' to a ShelfSlot DB record.

    Key format: {side}{board_addr}-{slot_num}
    Example: A1-5 → side='A', board_address=1, slot_on_board=5
    """
    try:
        side = slot_key[0]
        rest = slot_key[1:]  # e.g. "1-5"
        board_str, slot_str = rest.split("-")
        board_addr = int(board_str)
        slot_num = int(slot_str)
    except (IndexError, ValueError):
        return None

    result = await db.execute(
        select(ShelfSlot).where(
            ShelfSlot.shelf_id == shelf_id,
            ShelfSlot.side == side,
            ShelfSlot.board_address == board_addr,
            ShelfSlot.slot_on_board == slot_num,
        )
    )
    return result.scalar_one_or_none()


async def _find_unbound_reel(db: AsyncSession, shelf_id: int) -> Optional[InventoryReel]:
    """Find the most recently created InventoryReel that has no slot
    assigned and is in pending_shelving status. This is the reel being put away."""
    result = await db.execute(
        select(InventoryReel)
        .where(
            InventoryReel.shelf_slot_id.is_(None),
            InventoryReel.status == "pending_shelving",
        )
        .order_by(InventoryReel.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _record_event(
    db: AsyncSession,
    slot: ShelfSlot,
    event_type: str,
    reel_id: Optional[int] = None,
    old_state: int = 0,
    new_state: int = 0,
    source: str = "sensor",
):
    """Record a ShelfSlotEvent and update the slot's last_event_at."""
    event = ShelfSlotEvent(
        shelf_slot_id=slot.id,
        event_type=event_type,
        reel_id=reel_id,
        source=source,
        old_state=old_state,
        new_state=new_state,
    )
    db.add(event)
    slot.last_event_at = datetime.utcnow()
    slot.last_sensor_state = new_state


class SlotPollingService:
    """Manages the SlotPoller lifecycle and handles sensor events.

    Wiring (in main.py):
        app.state.slot_service = SlotPollingService()
        await app.state.slot_service.start()
    """

    def __init__(self):
        self._master: Optional[Amkn8702g] = None
        self._poller: Optional[SlotPoller] = None
        self._shelf_id: Optional[int] = None
        self._running = False

    async def start(self, shelf_id: int):
        """Initialize Modbus master and start polling for a specific shelf."""
        if settings.HARDWARE_SIMULATION:
            self._shelf_id = shelf_id
            self._running = True
            logger.info("SIM: SlotPollingService started for shelf %d (no hardware)", shelf_id)
            return

        shelf_result = None
        async with async_session_factory() as db:
            result = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
            shelf_result = result.scalar_one_or_none()

        if not shelf_result:
            logger.error("SlotPollingService: shelf %d not found", shelf_id)
            return

        self._shelf_id = shelf_id
        self._master = Amkn8702g(
            host=shelf_result.controller_ip or settings.MASTER_IP,
            port=shelf_result.controller_port or settings.MASTER_PORT,
            station=settings.MASTER_STATION,
        )
        await self._master.connect()

        self._poller = SlotPoller(
            master=self._master,
            on_change=self._on_change,
        )
        await self._poller.start(interval=settings.SLOT_POLL_INTERVAL)
        self._running = True
        logger.info("SlotPollingService started for shelf %d", shelf_id)

    async def stop(self):
        """Stop polling and disconnect."""
        self._running = False
        if self._poller:
            await self._poller.stop()
        if self._master:
            await self._master.disconnect()
        logger.info("SlotPollingService stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def get_live_state(self) -> list[dict]:
        """Get the current sensor state for all slots on the shelf."""
        if not self._master:
            return []
        states = await self._master.read_all_slots()
        result = []
        async with async_session_factory() as db:
            for key, st in states.items():
                slot_db = await _slot_key_to_db(key, self._shelf_id, db) if self._shelf_id else None
                # Find bound pallet
                bound_id = None
                if slot_db:
                    pallet = await db.execute(
                        select(InventoryReel).where(
                            InventoryReel.shelf_slot_id == slot_db.id,
                            InventoryReel.status == "on_shelf",
                        ).limit(1)
                    )
                    p = pallet.scalar_one_or_none()
                    bound_id = p.id if p else None

                result.append({
                    "slot_id": slot_db.id if slot_db else 0,
                    "side": st.face,
                    "board_address": st.board_addr,
                    "slot_on_board": st.slot_num,
                    "has_material": st.has_material,
                    "last_event_at": slot_db.last_event_at.isoformat() if slot_db and slot_db.last_event_at else None,
                    "bound_reel_id": bound_id,
                })
        return result

    # ── Callback (runs in async context) ──────────────────────────

    def _on_change(self, event: SlotChangeEvent):
        """Called by SlotPoller when a slot state changes.

        This runs inside the poller's async task. We create a new DB
        session for each event to avoid cross-task session sharing.
        """
        asyncio.ensure_future(self._handle_change(event))

    async def _handle_change(self, event: SlotChangeEvent):
        """Handle a slot change event — record event, auto-bind if occupied."""
        if not self._shelf_id:
            return

        async with async_session_factory() as db:
            slot = await _slot_key_to_db(event.slot_key, self._shelf_id, db)
            if not slot:
                logger.warning("Slot change for unknown slot: %s", event.slot_key)
                return

            bound_reel_id = None
            if event.event_type == "occupied" and settings.AUTO_ASSIGN_ENABLED:
                # Try auto-bind: find unbound reel and assign it to this slot
                reel = await _find_unbound_reel(db, self._shelf_id)
                if reel:
                    # Check slot isn't already occupied
                    existing = await db.execute(
                        select(InventoryReel).where(
                            InventoryReel.shelf_slot_id == slot.id,
                            InventoryReel.status == "on_shelf",
                        ).limit(1)
                    )
                    if not existing.scalar_one_or_none():
                        reel.shelf_slot_id = slot.id
                        reel.status = "on_shelf"  # pending_shelving → on_shelf
                        bound_reel_id = reel.id
                        logger.info(
                            "Auto-bound reel %d to slot %d (shelf %d)",
                            reel.id, slot.id, self._shelf_id,
                        )

            await _record_event(
                db,
                slot=slot,
                event_type=event.event_type,
                reel_id=bound_reel_id,
                old_state=1 if event.old_has_material else 0,
                new_state=1 if event.new_has_material else 0,
            )
            await db.commit()
