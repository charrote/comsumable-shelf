"""LED control service — AMKN7141-CHXX Protocol 2.

Contains both an in-memory queue for direct commands and a DB-backed worker
that polls the LedCommand table for queued commands from the API.
"""

import asyncio
import struct
import structlog
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.hal.modbus import Amkn8702g, LedColor
from app.models import Shelf, ShelfSlot, LedCommand as LedCommandModel
from app.config import settings
from app.utils.database import async_session_factory

logger = structlog.get_logger()


@dataclass
class LedCommand:
    """LED control command (in-memory)."""
    face: str  # 'A' or 'B'
    board_addr: int  # 1-based RTU address
    slot_num: int  # 1-based slot number
    color: LedColor
    duration_ms: int = 0  # 0 = permanent, >0 = flash


class LedService:
    """Smart shelf LED control service."""

    def __init__(self):
        self.master: Optional[Amkn8702g] = None
        self._active_commands: List[LedCommand] = []
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._queue_worker: Optional[asyncio.Task] = None
        self._db_worker: Optional[asyncio.Task] = None

    async def init(self, master_ip: str = None, port: int = None):
        """Initialize LED controller and start workers."""
        self.master = Amkn8702g(
            ip=master_ip or settings.MASTER_IP,
            port=port or settings.MASTER_PORT,
        )
        await self.master.connect()
        self._queue_worker = asyncio.create_task(self._command_worker())
        self._db_worker = asyncio.create_task(self._db_command_worker())
        logger.info("LED service started with queue + DB workers")

    async def shutdown(self):
        """Shutdown LED controller and workers."""
        if self._queue_worker:
            self._queue_worker.cancel()
        if self._db_worker:
            self._db_worker.cancel()
        if self.master:
            await self.master.disconnect()
        logger.info("LED service stopped")

    # ------------------------------------------------------------------
    # In-memory queue worker (for real-time direct commands)
    # ------------------------------------------------------------------
    async def _command_worker(self):
        """Process LED commands from in-memory queue."""
        while True:
            try:
                cmd = await asyncio.wait_for(
                    self._command_queue.get(), timeout=1.0
                )
                await self._execute_led(cmd)
                self._command_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("led_queue_worker_error", error=str(e))
                await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # DB-backed worker (consumes LedCommand table)
    # ------------------------------------------------------------------
    async def _db_command_worker(self):
        """Poll LedCommand table and send queued commands to hardware.

        Polls every 2 seconds for status='queued' records and processes
        them one at a time, updating status to 'sent' or 'failed'.
        """
        while True:
            try:
                await self._process_queued_commands()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("led_db_worker_error", error=str(e))
            await asyncio.sleep(2.0)

    async def _process_queued_commands(self):
        """Process all queued LED commands from the database."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(LedCommandModel)
                .where(LedCommandModel.status == "queued")
                .order_by(LedCommandModel.created_at.asc())
                .limit(20)
            )
            commands = result.scalars().all()

            for cmd in commands:
                try:
                    # Look up shelf slot for hardware addressing
                    slot_result = await session.execute(
                        select(ShelfSlot).where(ShelfSlot.id == cmd.slot_id)
                    )
                    slot = slot_result.scalar_one_or_none()
                    if not slot:
                        cmd.status = "failed"
                        logger.warning("led_slot_not_found", slot_id=cmd.slot_id)
                        continue

                    # Map color string to LedColor
                    color_map = {
                        "green": LedColor.GREEN,
                        "red": LedColor.RED,
                        "blue": LedColor.BLUE,
                        "off": LedColor.OFF,
                    }
                    color = color_map.get(cmd.color, LedColor.GREEN)

                    # Send to hardware
                    if cmd.duration and cmd.duration > 0:
                        # Flash
                        await self.master.set_led(
                            slot.side, slot.board_address, slot.slot_on_board, color
                        )
                        await asyncio.sleep(min(cmd.duration, 30) / 1000.0)
                        await self.master.set_led(
                            slot.side, slot.board_address, slot.slot_on_board, LedColor.OFF
                        )
                    else:
                        # Permanent
                        await self.master.set_led(
                            slot.side, slot.board_address, slot.slot_on_board, color
                        )

                    cmd.status = "sent"
                    cmd.sent_at = datetime.utcnow()
                    logger.info("led_command_sent",
                                command_id=cmd.id, slot_id=cmd.slot_id, color=cmd.color)

                except Exception as e:
                    cmd.status = "failed"
                    logger.error("led_command_failed",
                                 command_id=cmd.id, slot_id=cmd.slot_id, error=str(e))

            if commands:
                await session.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def light_slot(self, slot_id: int, color: LedColor = LedColor.GREEN,
                         duration_ms: int = 0):
        """Light a specific slot by ShelfSlot ID (via in-memory queue)."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(ShelfSlot).where(ShelfSlot.id == slot_id)
            )
            slot = result.scalar_one_or_none()
            if not slot:
                return False

            cmd = LedCommand(
                face=slot.side,
                board_addr=slot.board_address,
                slot_num=slot.slot_on_board,
                color=color,
                duration_ms=duration_ms,
            )
            await self._command_queue.put(cmd)
            return True

    async def light_slot_direct(self, shelf_slot_id: int,
                                color: LedColor = LedColor.GREEN):
        """Light a slot directly (bypasses queue)."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(ShelfSlot).where(ShelfSlot.id == shelf_slot_id)
            )
            slot = result.scalar_one_or_none()
            if not slot:
                return False

            await self.master.set_led(
                slot.side, slot.board_address, slot.slot_on_board, color
            )
            return True

    async def clear_all_leds(self):
        """Turn off all LEDs — optimized per-board broadcast.

        Instead of one Modbus call per slot (800 calls for 800 slots),
        we send one 'all off' command per board.
        """
        if not self.master:
            return

        for face_name, board_count in [('A', self.master.a_boards),
                                        ('B', self.master.b_boards)]:
            for board in range(1, board_count + 1):
                try:
                    # Send a single "all off" command per board
                    await self.master.set_led(
                        face_name, board, 0, LedColor.OFF
                    )
                    logger.debug("clear_board", face=face_name, board=board)
                except Exception as e:
                    logger.warning("clear_board_failed",
                                   face=face_name, board=board, error=str(e))

    async def _execute_led(self, cmd: LedCommand):
        """Execute a single LED command on hardware."""
        try:
            if cmd.duration_ms > 0:
                await self.master.set_led(
                    cmd.face, cmd.board_addr, cmd.slot_num, cmd.color
                )
                await asyncio.sleep(cmd.duration_ms / 1000.0)
                await self.master.set_led(
                    cmd.face, cmd.board_addr, cmd.slot_num, LedColor.OFF
                )
            else:
                await self.master.set_led(
                    cmd.face, cmd.board_addr, cmd.slot_num, cmd.color
                )
        except Exception as e:
            logger.error("led_execute_error", error=str(e))
            raise

    async def flash_led(self, face: str, board_addr: int, slot_num: int,
                        color: LedColor = LedColor.RED):
        """Flash LED briefly for verification."""
        await self.master.flash_led(face, board_addr, slot_num, color)

    async def verify_pallet(self, shelf_slot_id: int) -> bool:
        """Verify material pallet placement by flashing green."""
        await self.light_slot_direct(shelf_slot_id, LedColor.GREEN)
        await asyncio.sleep(0.5)
        await self.light_slot_direct(shelf_slot_id, LedColor.OFF)
        return True
