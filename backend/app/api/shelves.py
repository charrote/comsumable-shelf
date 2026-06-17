"""Shelf management API routes."""

from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import ShelfCreate, ShelfResponse, ShelfSlotCreate, ShelfSlotResponse
from app.utils.database import get_db
from app.models import Shelf, ShelfSlot

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
    ) for s in slots]
