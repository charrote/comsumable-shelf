"""Inventory business logic — direct outbound, etc."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryReel, Transaction, MaterialMaster
from app.services.operation_history_service import record_operation


async def direct_out(
    db: AsyncSession,
    reel_id: int,
    operator: str,
    note: str | None = None,
    release_slot: bool = True,
) -> dict:
    """Direct outbound — remove an entire reel from inventory (whole-reel mode).

    Because inventory is managed in Reel units, partial-quantity outbound
    is NOT supported.  Every outbound operation removes the full reel.

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

    # ── 3. Whole-reel outbound: always exhaust the reel ──
    qty_before = pallet.quantity
    now = datetime.utcnow()
    slot_released = False

    pallet.quantity = 0
    pallet.status = "exhausted"
    pallet.last_out_time = now
    pallet.updated_at = now

    if release_slot and pallet.shelf_slot_id is not None:
        pallet.shelf_slot_id = None
        slot_released = True

    # ── 4. Create transaction record ──
    # Calculate balance_after: sum of all non-exhausted pallets of same material
    all_pallets = await db.execute(
        select(InventoryReel).where(
            InventoryReel.material_id == pallet.material_id,
            InventoryReel.status != "exhausted",
        )
    )
    balance_after = sum(p.quantity for p in all_pallets.scalars().all())

    tx = Transaction(
        customer_id=pallet.customer_id,
        material_id=pallet.material_id,
        type="out",
        quantity=qty_before,
        balance_after=balance_after,
        reel_id=pallet.id,
        source_type="direct_outbound",
        source_id=pallet.id,
        operator=operator,
        note=note or "直接出库（整盘）",
        created_at=now,
    )
    db.add(tx)

    # ── 记录作业履历：出库 ──
    # 获取物料信息
    mat_result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == pallet.material_id)
    )
    mat = mat_result.scalar_one_or_none()

    await record_operation(
        db,
        operation_type="shelving_off",
        reel_id=pallet.id,
        reel_code=pallet.reel_code,
        material_id=pallet.material_id,
        material_code=mat.code if mat else None,
        material_name=mat.name if mat else None,
        shelf_id=None,
        shelf_code=None,
        slot_id=None,
        slot_code=None,
        customer_id=pallet.customer_id,
        quantity=qty_before,
        source_type="direct_outbound",
        operator=operator,
        note=note or "直接出库（整盘）",
    )

    await db.commit()

    return {
        "status": "exhausted",
        "reel_id": pallet.id,
        "quantity_before": qty_before,
        "quantity_after": 0,
        "reel_status": pallet.status,
        "slot_released": slot_released,
        "message": f"整盘出库成功，盘 #{pallet.id}（数量 {qty_before}）已全部出库",
    }
