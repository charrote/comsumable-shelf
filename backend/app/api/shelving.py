"""Shelving API routes — bind reels to shelf slots.

Supports two modes:
  1. Smart (sensor-based): scan reel -> put in slot -> sensor detects -> auto-bind
  2. Manual: scan reel -> scan shelf slot barcode -> bind
"""

import re
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.utils.database import get_db
from app.models import InventoryReel, MaterialMaster, Shelf, ShelfSlot, ShelfSlotEvent

router = APIRouter(prefix="/shelving", tags=["Shelving"])


class ShelvingScanRequest(BaseModel):
    barcode: str


class ShelvingScanResponse(BaseModel):
    status: str  # ok | already_bound | error
    reel_id: int
    material_code: str
    material_name: Optional[str] = None
    quantity: float = 0
    shelf_slot_id: Optional[int] = None
    shelf_code: Optional[str] = None
    slot_code: Optional[str] = None
    message: str = ""


class ShelvingBindRequest(BaseModel):
    reel_id: int
    shelf_id: int
    shelf_slot_id: Optional[int] = None
    operator: str = ""


class ShelvingBindResponse(BaseModel):
    status: str
    reel_id: int
    shelf_id: int
    shelf_slot_id: int
    shelf_code: Optional[str] = None
    slot_code: Optional[str] = None
    message: str = ""


@router.post("/scan", response_model=ShelvingScanResponse)
async def scan_reel_for_shelving(
    data: ShelvingScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Scan a reel barcode to get info for shelving."""
    barcode = data.barcode.strip()
    if not barcode:
        raise HTTPException(status_code=400, detail="条码不能为空")

    # Try to find by reel ID (from barcode which might be reel ID)
    reel_id = None
    try:
        reel_id = int(barcode)
    except ValueError:
        pass

    query = select(InventoryReel)
    if reel_id:
        query = query.where(InventoryReel.id == reel_id)
    else:
        query = query.where(InventoryReel.reel_barcode == barcode)

    result = await db.execute(query)
    reel = result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="未找到该料盘，请先入库")

    # Get material info
    mat_result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == reel.material_id)
    )
    material = mat_result.scalar_one_or_none()
    material_code = material.code if material else ""
    material_name = material.name if material else ""

    # Check if already bound
    shelf_code = None
    slot_code = None
    slot_id = reel.shelf_slot_id
    if slot_id:
        slot_result = await db.execute(
            select(ShelfSlot, Shelf.code)
            .join(Shelf, ShelfSlot.shelf_id == Shelf.id)
            .where(ShelfSlot.id == slot_id)
        )
        row = slot_result.one_or_none()
        if row:
            slot, sc = row
            shelf_code = sc
            slot_code = f"{slot.side}{slot.slot_on_board}"

    status = "already_bound" if slot_id else "ok"

    return ShelvingScanResponse(
        status=status,
        reel_id=reel.id,
        material_code=material_code,
        material_name=material_name,
        quantity=reel.quantity,
        shelf_slot_id=slot_id,
        shelf_code=shelf_code,
        slot_code=slot_code,
        message=f"已识别料盘 #{reel.id}" if not slot_id else f"料盘 #{reel.id} 已上架至 {shelf_code}/{slot_code}",
    )


# ──── Slot Barcode Scanning (Manual Mode) ────

class ShelvingScanSlotRequest(BaseModel):
    barcode: str


class ShelvingScanSlotResponse(BaseModel):
    status: str  # ok | not_found | occupied
    shelf_slot_id: int
    shelf_id: int
    shelf_code: str
    slot_code: str
    side: str = ""
    slot_on_board: int = 0
    is_occupied: bool = False
    message: str = ""


def _parse_slot_barcode(barcode: str) -> Optional[dict]:
    """Parse shelf slot barcode into shelf_code, side, slot_on_board.

    Supported formats (case-insensitive):
      - A1A05       (shelf + side + 2-digit slot)
      - A1-A05      (with dash before slot)
      - A1A-05      (dash between side and slot)
      - A1-A-05     (fully separated)
      - a1a05       (lowercase)
    """
    b = barcode.strip().upper()
    if not b:
        return None

    # Try fully separated: A1-A-05 → groups: A1, A, 05
    m = re.match(r'^([A-Z0-9]+)-([A-B])(\d+)$', b)
    if m:
        return {"shelf_code": m.group(1), "side": m.group(2), "slot_on_board": int(m.group(3))}

    # Try: A1-A05 or A1A-05 → split on dash to find side
    m = re.match(r'^([A-Z0-9]+)-?([A-B])-?(\d+)$', b)
    if m:
        return {"shelf_code": m.group(1), "side": m.group(2), "slot_on_board": int(m.group(3))}

    # Try compact: A1A05 → split shelf_code from side+slot
    m = re.match(r'^([A-Z]+\d+)([A-B])(\d+)$', b)
    if m:
        return {"shelf_code": m.group(1), "side": m.group(2), "slot_on_board": int(m.group(3))}

    return None


@router.post("/scan-slot", response_model=ShelvingScanSlotResponse)
async def scan_slot_for_shelving(
    data: ShelvingScanSlotRequest,
    db: AsyncSession = Depends(get_db),
):
    """Scan a shelf slot barcode to identify the slot (manual mode).

    Barcode format: {SHELF_CODE}{SIDE}{SLOT_NUMBER}
    Examples: A1A05, A1-A05, A1-A-05
    """
    parsed = _parse_slot_barcode(data.barcode)
    if not parsed:
        raise HTTPException(status_code=400, detail="储位条码格式无效，示例: A1A05")

    # Look up shelf by code
    shelf_result = await db.execute(
        select(Shelf).where(Shelf.code == parsed["shelf_code"], Shelf.active == 1)
    )
    shelf = shelf_result.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=404, detail=f"未找到料架 {parsed['shelf_code']}")

    # Look up slot
    slot_result = await db.execute(
        select(ShelfSlot).where(
            ShelfSlot.shelf_id == shelf.id,
            ShelfSlot.side == parsed["side"],
            ShelfSlot.slot_on_board == parsed["slot_on_board"],
        )
    )
    slot = slot_result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail=f"未找到储位 {parsed['shelf_code']}-{parsed['side']}{parsed['slot_on_board']}")

    # Check if slot is already occupied
    occupied = await db.execute(
        select(InventoryReel).where(
            InventoryReel.shelf_slot_id == slot.id,
            InventoryReel.status == "on_shelf",
        ).limit(1)
    )
    is_occupied = occupied.scalar_one_or_none() is not None

    slot_code = f"{slot.side}{slot.slot_on_board}"

    return ShelvingScanSlotResponse(
        status="occupied" if is_occupied else "ok",
        shelf_slot_id=slot.id,
        shelf_id=shelf.id,
        shelf_code=shelf.code,
        slot_code=slot_code,
        side=slot.side,
        slot_on_board=slot.slot_on_board,
        is_occupied=is_occupied,
        message=f"已识别储位: {shelf.code}/{slot_code}" if not is_occupied
                 else f"储位 {shelf.code}/{slot_code} 已被占用",
    )


@router.post("/bind", response_model=ShelvingBindResponse)
async def bind_shelving_slot(
    data: ShelvingBindRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bind a reel to a specific shelf slot (manual assignment)."""
    # Verify reel exists
    reel_result = await db.execute(
        select(InventoryReel).where(InventoryReel.id == data.reel_id)
    )
    reel = reel_result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="料盘不存在")

    if reel.status not in ("pending_shelving", "on_shelf"):
        raise HTTPException(status_code=400, detail=f"料盘状态为 {reel.status}，无法上架")

    # If shelf_slot_id provided, verify and assign to that slot
    shelf_slot_id = data.shelf_slot_id
    if shelf_slot_id:
        slot_result = await db.execute(
            select(ShelfSlot).where(ShelfSlot.id == shelf_slot_id)
        )
        slot = slot_result.scalar_one_or_none()
        if not slot:
            raise HTTPException(status_code=404, detail="储位不存在")

        # Check slot is not occupied
        occupied = await db.execute(
            select(InventoryReel).where(
                InventoryReel.shelf_slot_id == shelf_slot_id,
                InventoryReel.id != data.reel_id,
                InventoryReel.status == "on_shelf",
            )
        )
        if occupied.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该储位已被占用")

        reel.shelf_slot_id = shelf_slot_id

    # If no shelf_slot_id but shelf_id provided, find an empty slot
    elif data.shelf_id:
        shelf_result = await db.execute(
            select(Shelf).where(Shelf.id == data.shelf_id)
        )
        shelf = shelf_result.scalar_one_or_none()
        if not shelf:
            raise HTTPException(status_code=404, detail="料架不存在")

        # Find first empty slot
        slots_result = await db.execute(
            select(ShelfSlot).where(
                ShelfSlot.shelf_id == data.shelf_id,
                ShelfSlot.last_sensor_state == 0,  # sensor says empty
            )
            .order_by(ShelfSlot.side, ShelfSlot.board_address, ShelfSlot.slot_on_board)
            .limit(1)
        )
        empty_slot = slots_result.scalar_one_or_none()
        if not empty_slot:
            raise HTTPException(status_code=400, detail="该料架没有可用的空储位")

        reel.shelf_slot_id = empty_slot.id
        shelf_slot_id = empty_slot.id

    # If reel was pending shelving, mark as on_shelf now
    if reel.status == "pending_shelving":
        reel.status = "on_shelf"

    await db.commit()

    # Get shelf code and slot code
    slot_info_result = await db.execute(
        select(ShelfSlot, Shelf.code)
        .join(Shelf, ShelfSlot.shelf_id == Shelf.id)
        .where(ShelfSlot.id == shelf_slot_id)
    )
    row = slot_info_result.one_or_none()
    shelf_code = row[1] if row else ""
    slot_obj = row[0] if row else None
    slot_code = f"{slot_obj.side}{slot_obj.slot_on_board}" if slot_obj else ""

    # Record event
    event = ShelfSlotEvent(
        shelf_slot_id=shelf_slot_id,
        event_type="bound",
        reel_id=data.reel_id,
        source="pda",
    )
    db.add(event)
    await db.commit()

    return ShelvingBindResponse(
        status="ok",
        reel_id=data.reel_id,
        shelf_id=data.shelf_id,
        shelf_slot_id=shelf_slot_id,
        shelf_code=shelf_code,
        slot_code=slot_code,
        message=f"上架成功: {shelf_code}/{slot_code}",
    )
