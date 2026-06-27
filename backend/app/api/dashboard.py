"""Dashboard API routes — summary statistics for PDA home screen."""

from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from app.config import settings
from app.utils.database import get_db
from app.models import InventoryReel, IssueOrder, Receipt

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard summary for PDA home screen."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Today's inbound count (receipts created today)
    today_inbound_result = await db.execute(
        select(func.count(Receipt.id)).where(Receipt.created_at >= today_start)
    )
    today_inbound = today_inbound_result.scalar() or 0

    # Today's outbound count (issues completed today)
    today_outbound_result = await db.execute(
        select(func.count(IssueOrder.id)).where(
            IssueOrder.completed_at >= today_start
        )
    )
    today_outbound = today_outbound_result.scalar() or 0

    # Pending issues (status = picking or assigned)
    pending_issues_result = await db.execute(
        select(func.count(IssueOrder.id)).where(
            IssueOrder.status.in_(["picking", "assigned"])
        )
    )
    pending_issues = pending_issues_result.scalar() or 0

    # On-shelf pallets
    on_shelf_result = await db.execute(
        select(func.count(InventoryReel.id)).where(
            InventoryReel.status == "on_shelf",
            InventoryReel.quantity > 0,
        )
    )
    on_shelf_pallets = on_shelf_result.scalar() or 0

    # Tracking pallets
    tracking_result = await db.execute(
        select(func.count(InventoryReel.id)).where(
            InventoryReel.status == "tracking"
        )
    )
    tracking_pallets = tracking_result.scalar() or 0

    # Pending receipts (status = draft)
    pending_receipts_result = await db.execute(
        select(func.count(Receipt.id)).where(Receipt.status == "draft")
    )
    pending_receipts = pending_receipts_result.scalar() or 0

    # Pending shelving pallets (received but not yet shelved)
    pending_shelving_result = await db.execute(
        select(func.count(InventoryReel.id)).where(
            InventoryReel.status == "pending_shelving",
            InventoryReel.quantity > 0,
        )
    )
    pending_shelving_pallets = pending_shelving_result.scalar() or 0

    # 物理在库总量 = 待上架 + 在架
    physical_inventory = pending_shelving_pallets + on_shelf_pallets

    return {
        "app_name": settings.APP_NAME,
        "today_inbound": today_inbound,
        "today_outbound": today_outbound,
        "pending_issues": pending_issues,
        "on_shelf_pallets": on_shelf_pallets,
        "pending_shelving_pallets": pending_shelving_pallets,
        "physical_inventory": physical_inventory,
        "tracking_pallets": tracking_pallets,
        "pending_receipts": pending_receipts,
    }
