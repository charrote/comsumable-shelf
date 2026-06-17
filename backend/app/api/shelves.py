"""Shelf management API routes — CRUD + slot sensor polling + events."""

from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.schemas import (
    ShelfCreate, ShelfResponse, ShelfSlotCreate, ShelfSlotResponse,
    ShelfSlotEventResponse, SlotSensorState,
)
from app.utils.database import get_db
from app.models import Shelf, ShelfSlot, ShelfSlotEvent, InventoryReel

router = APIRouter(prefix="/shelves", tags=["Shelf Management"])


@router.get("")
async def list_shelves(
    active: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Shelf)
    if active is not None:
        query = query.where(Shelf.active == active)
    query = query.order_by(Shelf.code)
    result = await db.execute(query)
    shelves = result.scalars().all()
    return [ShelfResponse(
        id=s.id, code=s.code, name=s.name,
        a_sides=s.a_sides, b_sides=s.b_sides, total_slots=s.total_slots,
        controller_ip=s.controller_ip, controller_port=s.controller_port,
        a_side_count=s.a_side_count, b_side_count=s.b_side_count,
        location=s.location, active=s.active,
    ) for s in shelves]


@router.post("")
async def create_shelf(
    data: ShelfCreate,
    db: AsyncSession = Depends(get_db),
):
    shelf = Shelf(
        code=data.code, name=data.name,
        a_sides=data.a_sides, b_sides=data.b_sides,
        total_slots=(data.a_sides + data.b_sides) * 20,
        controller_ip=data.controller_ip,
        controller_port=data.controller_port,
        a_side_count=data.a_sides, b_side_count=data.b_sides,
        location=data.location, active=1,
    )
    db.add(shelf)
    await db.commit()
    await db.refresh(shelf)
    return ShelfResponse(
        id=shelf.id, code=shelf.code, name=shelf.name,
        a_sides=shelf.a_sides, b_sides=shelf.b_sides,
        total_slots=shelf.total_slots,
        controller_ip=shelf.controller_ip, controller_port=shelf.controller_port,
        a_side_count=shelf.a_side_count, b_side_count=shelf.b_side_count,
        location=shelf.location, active=shelf.active,
    )


@router.get("/{shelf_id}")
async def get_shelf(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    shelf = result.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=404, detail="料架不存在")
    return ShelfResponse(
        id=shelf.id, code=shelf.code, name=shelf.name,
        a_sides=shelf.a_sides, b_sides=shelf.b_sides,
        total_slots=shelf.total_slots,
        controller_ip=shelf.controller_ip, controller_port=shelf.controller_port,
        a_side_count=shelf.a_side_count, b_side_count=shelf.b_side_count,
        location=shelf.location, active=shelf.active,
    )


@router.put("/{shelf_id}")
async def update_shelf(
    shelf_id: int,
    data: ShelfCreate,
    db: AsyncSession = Depends(get_db),
):
    shelf = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    shelf = shelf.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=404, detail="料架不存在")
    shelf.code = data.code
    shelf.name = data.name
    shelf.a_sides = data.a_sides
    shelf.b_sides = data.b_sides
    shelf.total_slots = (data.a_sides + data.b_sides) * 20
    shelf.controller_ip = data.controller_ip
    shelf.controller_port = data.controller_port
    shelf.a_side_count = data.a_sides
    shelf.b_side_count = data.b_sides
    shelf.location = data.location
    await db.commit()
    await db.refresh(shelf)
    return ShelfResponse(
        id=shelf.id, code=shelf.code, name=shelf.name,
        a_sides=shelf.a_sides, b_sides=shelf.b_sides,
        total_slots=shelf.total_slots,
        controller_ip=shelf.controller_ip, controller_port=shelf.controller_port,
        a_side_count=shelf.a_side_count, b_side_count=shelf.b_side_count,
        location=shelf.location, active=shelf.active,
    )


@router.delete("/{shelf_id}")
async def delete_shelf(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    shelf = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    shelf = shelf.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=404, detail="料架不存在")
    shelf.active = 0
    await db.commit()
    return {"status": "ok", "message": "料架已禁用"}


@router.get("/{shelf_id}/slots")
async def list_slots(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShelfSlot).where(ShelfSlot.shelf_id == shelf_id)
        .order_by(ShelfSlot.side, ShelfSlot.board_address, ShelfSlot.slot_on_board)
    )
    slots = result.scalars().all()
    return [ShelfSlotResponse(
        id=s.id, shelf_id=s.shelf_id, side=s.side,
        board_address=s.board_address, slot_on_board=s.slot_on_board,
        global_index=s.global_index, modbus_tcp_id=s.modbus_tcp_id,
        modbus_coil_base=s.modbus_coil_base,
        max_quantity=s.max_quantity,
        last_event_at=s.last_event_at,
        last_sensor_state=s.last_sensor_state,
    ) for s in slots]


# ═══════════════════════════════════════════════
# Slot Sensor & Polling Endpoints
# ═══════════════════════════════════════════════

@router.get("/{shelf_id}/slots/state")
async def get_slot_states(
    shelf_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get live sensor states for all slots on a shelf.

    Returns hardware sensor reading + DB binding info.
    """
    slot_service = getattr(request.app.state, "slot_service", None)
    if not slot_service or not slot_service.is_running:
        # Fallback: return DB-only state without live sensor data
        slots_result = await db.execute(
            select(ShelfSlot).where(ShelfSlot.shelf_id == shelf_id)
            .order_by(ShelfSlot.side, ShelfSlot.board_address, ShelfSlot.slot_on_board)
        )
        slots = slots_result.scalars().all()
        result = []
        for s in slots:
            pallet = await db.execute(
                select(InventoryReel).where(
                    InventoryReel.shelf_slot_id == s.id,
                    InventoryReel.status == "on_shelf",
                ).limit(1)
            )
            p = pallet.scalar_one_or_none()
            result.append({
                "slot_id": s.id,
                "side": s.side,
                "board_address": s.board_address,
                "slot_on_board": s.slot_on_board,
                "has_material": bool(s.last_sensor_state),
                "last_event_at": s.last_event_at.isoformat() if s.last_event_at else None,
                "bound_reel_id": p.id if p else None,
            })
        return {"shelf_id": shelf_id, "polling_active": False, "slots": result}

    # Live sensor data
    live = await slot_service.get_live_state()
    return {"shelf_id": shelf_id, "polling_active": True, "slots": live}


@router.get("/{shelf_id}/events")
async def list_slot_events(
    shelf_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List recent sensor events for a shelf's slots."""
    result = await db.execute(
        select(ShelfSlotEvent)
        .join(ShelfSlot, ShelfSlotEvent.shelf_slot_id == ShelfSlot.id)
        .where(ShelfSlot.shelf_id == shelf_id)
        .order_by(ShelfSlotEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [ShelfSlotEventResponse(
        id=e.id,
        shelf_slot_id=e.shelf_slot_id,
        event_type=e.event_type,
        reel_id=e.reel_id,
        source=e.source,
        old_state=e.old_state,
        new_state=e.new_state,
        created_at=e.created_at,
    ) for e in events]


@router.get("/{shelf_id}/polling")
async def get_polling_status(
    shelf_id: int,
    request: Request,
):
    """Get the polling status for a shelf."""
    slot_service = getattr(request.app.state, "slot_service", None)
    return {
        "shelf_id": shelf_id,
        "polling_active": slot_service.is_running if slot_service else False,
    }


@router.post("/{shelf_id}/polling/start")
async def start_polling(
    shelf_id: int,
    request: Request,
):
    """Start the slot sensor polling service for a shelf."""
    slot_service = getattr(request.app.state, "slot_service", None)
    if not slot_service:
        raise HTTPException(status_code=500, detail="Slot service not initialized")
    if slot_service.is_running:
        return {"status": "ok", "message": "Polling already running"}

    await slot_service.start(shelf_id)
    return {"status": "ok", "message": f"Polling started for shelf {shelf_id}"}


@router.post("/{shelf_id}/polling/stop")
async def stop_polling(
    shelf_id: int,
    request: Request,
):
    """Stop the slot sensor polling service."""
    slot_service = getattr(request.app.state, "slot_service", None)
    if not slot_service:
        raise HTTPException(status_code=500, detail="Slot service not initialized")
    if not slot_service.is_running:
        return {"status": "ok", "message": "Polling already stopped"}

    await slot_service.stop()
    return {"status": "ok", "message": f"Polling stopped for shelf {shelf_id}"}


@router.post("/{shelf_id}/auto-assign")
async def manual_auto_assign(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger auto-assign: bind unassigned reels to occupied slots.

    Scans all slots on the shelf: for each slot where sensor says occupied
    but no reel is bound, find the most recent unassigned reel and bind it.
    """
    from app.services.shelf_service import _find_unbound_reel

    slots_result = await db.execute(
        select(ShelfSlot).where(ShelfSlot.shelf_id == shelf_id)
        .order_by(ShelfSlot.side, ShelfSlot.board_address, ShelfSlot.slot_on_board)
    )
    slots = slots_result.scalars().all()

    bound = 0
    for slot in slots:
        # Check if slot is occupied (by sensor or manual state)
        if not slot.last_sensor_state:
            continue
        # Check if already bound
        existing = await db.execute(
            select(InventoryReel).where(
                InventoryReel.shelf_slot_id == slot.id,
                InventoryReel.status == "on_shelf",
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            continue
        # Find unbound reel
        reel = await _find_unbound_reel(db, shelf_id)
        if not reel:
            break
        reel.shelf_slot_id = slot.id
        bound += 1

    if bound > 0:
        await db.commit()

    return {
        "status": "ok",
        "shelf_id": shelf_id,
        "bound": bound,
        "message": f"已自动绑定 {bound} 个盘料",
    }
