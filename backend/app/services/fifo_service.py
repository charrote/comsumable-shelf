"""FIFO (First-In-First-Out) calculation service.

Strategies:
- tail_first: 优先出库剩余量少的盘（尾数优先）
- time_fifo: 严格按入库时间先后顺序
- mixed: 同尾数时按时间排序

锁定规则：
- 整盘出库（最小单位 = 1 reel，不拆盘）
- 已锁定的 reel（有 active 的 reel_reservation）不参与计算
"""

from datetime import datetime
from typing import List, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import InventoryReel, MaterialAlternative, SystemSetting, ReelReservation


async def _get_db_strategy(db) -> str | None:
    """Read FIFO strategy from system_settings table.

    Returns None if not set, allowing caller to fall back to env config.
    """
    result = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "fifo_strategy")
    )
    return result.scalar_one_or_none()


async def _get_reserved_reel_ids(db: AsyncSession) -> List[int]:
    """Get all reel IDs that currently have active reservations."""
    result = await db.execute(
        select(ReelReservation.reel_id).where(ReelReservation.status == "active")
    )
    return [row[0] for row in result.all()]


async def calculate_fifo_pallets(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
    required_qty: float,
    strategy: str = "config",
) -> Dict:
    """Calculate which inventory pallets to pick (whole-reel mode).

    Args:
        db: Database session
        material_id: Material ID to pick from
        customer_id: Customer ID for scope
        required_qty: Total quantity needed
        strategy: FIFO strategy (config | tail_first | time_fifo | mixed)

    Returns:
        Dict with reels, total_selected, shortage, strategy_used
        NOTE: total_selected may exceed required_qty in whole-reel mode.
    """
    if strategy == "config":
        db_strategy = await _get_db_strategy(db)
        strategy = db_strategy if db_strategy else settings.FIFO_STRATEGY

    # Get IDs of all currently locked reels
    reserved_ids = await _get_reserved_reel_ids(db)

    # Fetch all on_shelf pallets, excluding reserved ones
    query = (
        select(InventoryReel)
        .where(
            InventoryReel.material_id == material_id,
            InventoryReel.customer_id == customer_id,
            InventoryReel.status == "on_shelf",
            InventoryReel.quantity > 0,
        )
        .order_by(InventoryReel.last_in_time.asc())
    )
    result = await db.execute(query)
    pallets = result.scalars().all()

    # Filter out reserved reels
    pallets = [p for p in pallets if p.id not in reserved_ids]

    if not pallets:
        return {
            "reels": [],
            "total_selected": 0,
            "shortage": required_qty,
            "strategy_used": strategy,
        }

    # Sort by strategy
    if strategy == "tail_first":
        pallets.sort(key=lambda p: p.quantity)
    elif strategy == "time_fifo":
        pallets.sort(key=lambda p: p.last_in_time)
    elif strategy == "mixed":
        pallets.sort(key=lambda p: (p.quantity, p.last_in_time))

    # Whole-reel greedy selection (不拆盘)
    selected = []
    remaining = required_qty

    for pallet in pallets:
        if remaining <= 0:
            break
        # 整盘出库，取一整盘
        selected.append({
            "reel_id": pallet.id,
            "quantity": pallet.quantity,
            "last_in_time": pallet.last_in_time,
            "shelf_slot_id": pallet.shelf_slot_id,
            "remaining_after": 0,  # 整盘取走，盘上不留
        })
        remaining -= pallet.quantity

    total_selected = sum(s["quantity"] for s in selected)
    shortage = required_qty - total_selected

    return {
        "reels": selected,
        "total_selected": total_selected,
        "shortage": max(0, shortage),
        "strategy_used": strategy,
    }


async def get_available_qty(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
) -> float:
    """Get total available quantity for a material (excluding reserved reels)."""
    reserved_ids = await _get_reserved_reel_ids(db)

    query = select(func.coalesce(func.sum(InventoryReel.quantity), 0)).where(
        InventoryReel.material_id == material_id,
        InventoryReel.customer_id == customer_id,
        InventoryReel.status == "on_shelf",
        InventoryReel.quantity > 0,
    )

    # 如果不为空才加排除条件
    if reserved_ids:
        query = query.where(InventoryReel.id.notin_(reserved_ids))

    result = await db.execute(query)
    return float(result.scalar_one())


async def check_alternative_material(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
) -> List[int]:
    """Find alternative material IDs for a given material."""
    from sqlalchemy import literal_column
    subq = select(MaterialMaster.code).where(MaterialMaster.id == material_id).scalar_subquery()
    result = await db.execute(
        select(MaterialAlternative.alternate_code)
        .where(
            MaterialAlternative.original_code == subq,
            MaterialAlternative.customer_id == customer_id,
            MaterialAlternative.active == 1,
        )
    )
    return [row[0] for row in result.all()]


from app.models import MaterialMaster  # noqa: E402
