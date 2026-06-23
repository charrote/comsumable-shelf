"""Inventory business logic — direct outbound, etc."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryReel, Transaction, MaterialMaster


async def direct_out(
    db: AsyncSession,
    reel_id: int,
    quantity: float,
    operator: str,
    note: str | None = None,
    release_slot: bool = True,
) -> dict:
    """Direct outbound — reduce reel quantity without going through IssueOrder.

    Returns dict with keys:
        status, reel_id, quantity_before, quantity_after,
        reel_status, slot_released, message
    """
    # ── 1. Fetch pallet ──
    result = await db.execute(
        select(InventoryReel).where(InventoryReel.id == reel_id)
    )
    pallet = result.scalar_one_or_none()
    if not pallet:
        return {
            "status": "error",
            "reel_id": reel_id,
            "quantity_before": 0,
            "quantity_after": 0,
            "reel_status": "",
            "slot_released": False,
            "message": "盘料不存在",
        }

    # ── 2. Validate ──
    if pallet.status == "exhausted":
        return {
            "status": "error",
            "reel_id": pallet.id,
            "quantity_before": pallet.quantity,
            "quantity_after": pallet.quantity,
            "reel_status": pallet.status,
            "slot_released": False,
            "message": f"盘 #{pallet.id} 已耗尽（status=exhausted），不可重复出库",
        }

    if quantity > pallet.quantity:
        return {
            "status": "error",
            "reel_id": pallet.id,
            "quantity_before": pallet.quantity,
            "quantity_after": pallet.quantity,
            "reel_status": pallet.status,
            "slot_released": False,
            "message": f"出库数量 {quantity} 超过库存 {pallet.quantity}",
        }

    # ── 3. Update pallet ──
    qty_before = pallet.quantity
    new_qty = pallet.quantity - quantity
    now = datetime.utcnow()
    slot_released = False

    if new_qty <= 0:
        # Fully consumed
        pallet.quantity = 0
        pallet.status = "exhausted"
        if release_slot and pallet.shelf_slot_id is not None:
            pallet.shelf_slot_id = None
            slot_released = True
    else:
        pallet.quantity = new_qty
        # status stays unchanged (on_shelf / in_use / tracking)

    pallet.last_out_time = now
    pallet.updated_at = now

    # ── 4. Create transaction record ──
    # Fetch material for balance calculation (use a simple total)
    mat_result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == pallet.material_id)
    )
    material = mat_result.scalar_one_or_none()

    # Calculate balance_after: sum of all non-exhausted pallets of same material
    all_pallets = await db.execute(
        select(InventoryReel).where(
            InventoryReel.material_id == pallet.material_id,
            InventoryReel.status != "exhausted",
        )
    )
    balance_after = sum(p.quantity for p in all_pallets.scalars().all())
    balance_after -= quantity  # current pallet already reduced in memory

    tx = Transaction(
        customer_id=pallet.customer_id,
        material_id=pallet.material_id,
        type="out",
        quantity=quantity,
        balance_after=balance_after,
        reel_id=pallet.id,
        source_type="direct_outbound",
        source_id=pallet.id,
        operator=operator,
        note=note or "直接出库",
        created_at=now,
    )
    db.add(tx)
    await db.commit()

    return {
        "status": "exhausted" if new_qty <= 0 else "ok",
        "reel_id": pallet.id,
        "quantity_before": qty_before,
        "quantity_after": new_qty,
        "reel_status": pallet.status,
        "slot_released": slot_released,
        "message": f"出库成功，盘 #{pallet.id} 数量 {qty_before} → {max(0, new_qty)}",
    }
