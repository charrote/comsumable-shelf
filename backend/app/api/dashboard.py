"""Dashboard API routes — summary statistics and pending lists."""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query
from app.config import settings
from app.utils.database import get_db
from app.models import InventoryReel, IssueOrder, IssueDetail, Receipt, ReceiptReel, MaterialMaster

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


@router.get("/pending-lists")
async def get_dashboard_pending_lists(
    db: AsyncSession = Depends(get_db),
):
    """Return three pending lists for the homepage dashboard."""
    # ── 1. 待入库收料单 (draft receipts) ──
    receipt_query = (
        select(
            Receipt,
            func.count(ReceiptReel.id).label("items_count"),
        )
        .outerjoin(ReceiptReel, ReceiptReel.receipt_id == Receipt.id)
        .where(Receipt.status == "draft")
        .group_by(Receipt.id)
        .order_by(Receipt.created_at.desc())
    )
    receipt_rows = (await db.execute(receipt_query)).all()
    pending_receipts = [
        {
            "id": r.Receipt.id,
            "receipt_no": r.Receipt.receipt_no,
            "purchase_order_no": r.Receipt.purchase_order_no or "",
            "created_at": r.Receipt.created_at.isoformat() if r.Receipt.created_at else None,
            "items_count": r.items_count,
            "operator": r.Receipt.created_by or "",
        }
        for r in receipt_rows
    ]

    # ── 2. 待上架物料 (pending_shelving inventory reels) ──
    shelving_query = (
        select(
            InventoryReel,
            MaterialMaster.code.label("material_code"),
            MaterialMaster.name.label("material_name"),
        )
        .join(MaterialMaster, InventoryReel.material_id == MaterialMaster.id)
        .where(
            InventoryReel.status == "pending_shelving",
            InventoryReel.quantity > 0,
        )
        .order_by(InventoryReel.created_at.desc())
    )
    shelving_rows = (await db.execute(shelving_query)).all()
    pending_shelving = [
        {
            "reel_id": r.InventoryReel.id,
            "reel_code": r.InventoryReel.reel_code or str(r.InventoryReel.id),
            "material_code": r.material_code,
            "material_name": r.material_name,
            "quantity": r.InventoryReel.quantity,
            "created_at": r.InventoryReel.created_at.isoformat() if r.InventoryReel.created_at else None,
        }
        for r in shelving_rows
    ]

    # ── 3. 待发料料单 (pending issue orders) ──
    issue_query = (
        select(IssueOrder)
        .where(IssueOrder.status == "pending")
        .order_by(IssueOrder.created_at.desc())
    )
    issue_orders = (await db.execute(issue_query)).scalars().all()
    pending_issues = []
    for order in issue_orders:
        detail_count_result = await db.execute(
            select(func.count(IssueDetail.id)).where(IssueDetail.issue_order_id == order.id)
        )
        detail_count = detail_count_result.scalar() or 0
        pending_issues.append(
            {
                "id": order.id,
                "order_no": order.order_no,
                "production_quantity": order.production_quantity,
                "required_date": order.required_date.isoformat() if order.required_date else None,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "detail_count": detail_count,
            }
        )

    return {
        "pending_receipts": pending_receipts,
        "pending_shelving": pending_shelving,
        "pending_issues": pending_issues,
    }
