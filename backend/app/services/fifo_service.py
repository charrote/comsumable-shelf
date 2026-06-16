"""FIFO (First-In-First-Out) calculation service.

Strategies:
- tail_first: 优先出库剩余量少的盘（尾数优先）
- time_fifo: 严格按入库时间先后顺序
- mixed: 同尾数时按时间排序
"""

from datetime import datetime
from typing import List, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import InventoryPallet, MaterialAlternative


async def calculate_fifo_pallets(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
    required_qty: float,
    strategy: str = "config",
) -> Dict:
    """Calculate which inventory pallets to pick.
    
    Args:
        db: Database session
        material_id: Material ID to pick from
        customer_id: Customer ID for scope
        required_qty: Total quantity needed
        strategy: FIFO strategy (config | tail_first | time_fifo | mixed)
        
    Returns:
        Dict with pallets_selected, total_selected, shortage, strategy_used
    """
    if strategy == "config":
        strategy = settings.FIFO_STRATEGY

    # Fetch all on_shelf pallets
    query = (
        select(InventoryPallet)
        .where(
            InventoryPallet.material_id == material_id,
            InventoryPallet.customer_id == customer_id,
            InventoryPallet.status == "on_shelf",
            InventoryPallet.quantity > 0,
        )
        .order_by(InventoryPallet.last_in_time.asc())
    )
    result = await db.execute(query)
    pallets = result.scalars().all()

    if not pallets:
        return {
            "pallets": [],
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

    # Greedy selection
    selected = []
    remaining = required_qty

    for pallet in pallets:
        if remaining <= 0:
            break
        take_qty = min(pallet.quantity, remaining)
        selected.append({
            "pallet_id": pallet.id,
            "quantity": take_qty,
            "last_in_time": pallet.last_in_time,
            "shelf_slot_id": pallet.shelf_slot_id,
            "remaining_after": pallet.quantity - take_qty,
        })
        remaining -= take_qty

    total_selected = sum(s["quantity"] for s in selected)
    shortage = required_qty - total_selected

    return {
        "pallets": selected,
        "total_selected": total_selected,
        "shortage": max(0, shortage),
        "strategy_used": strategy,
    }


async def get_available_qty(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
) -> float:
    """Get total available quantity for a material."""
    result = await db.execute(
        select(func.coalesce(func.sum(InventoryPallet.quantity), 0))
        .where(
            InventoryPallet.material_id == material_id,
            InventoryPallet.customer_id == customer_id,
            InventoryPallet.status == "on_shelf",
            InventoryPallet.quantity > 0,
        )
    )
    return float(result.scalar_one())


async def check_alternative_material(
    db: AsyncSession,
    material_id: int,
    customer_id: int,
) -> List[int]:
    """Find alternative material IDs for a given material."""
    result = await db.execute(
        select(MaterialAlternative.alternate_code)
        .where(
            MaterialAlternative.original_code == (
                select(MaterialMaster.code)
                .where(MaterialMaster.id == material_id)
            ),
            MaterialAlternative.customer_id == customer_id,
            MaterialAlternative.active == 1,
        )
    )
    return [row[0] for row in result.all()]


from app.models import MaterialMaster  # noqa: E402
