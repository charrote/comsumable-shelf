"""Report API routes."""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    DailyReportResponse, DailyReportSummary, DailyReportDetail,
    CustomerSummaryResponse,
)
from app.utils.database import get_db
from app.models import Transaction, MaterialMaster, InventoryReel, Customer, MaterialCategory

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/daily")
async def get_daily_report(
    date: str = Query(..., description="YYYY-MM-DD"),
    customer_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get daily report with correct opening balance and material names."""
    try:
        report_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")

    try:
        # Base query: all transactions for the given date
        txn_query = (
            select(Transaction)
            .where(func.date(Transaction.created_at) == date)
        )
        if customer_id:
            txn_query = txn_query.where(Transaction.customer_id == customer_id)

        day_transactions = await db.execute(txn_query)
        txns = day_transactions.scalars().all()

        # Collect unique material IDs from transactions
        material_ids_in_txns = set()
        for txn in txns:
            if txn.material_id:
                material_ids_in_txns.add(txn.material_id)

        # Also include materials that have on-shelf inventory (even if no transactions today)
        inv_query = (
            select(InventoryReel.material_id)
            .where(InventoryReel.status == "on_shelf")
            .distinct()
        )
        if customer_id:
            inv_query = inv_query.where(InventoryReel.customer_id == customer_id)
        inv_result = await db.execute(inv_query)
        for row in inv_result.all():
            if row[0]:
                material_ids_in_txns.add(row[0])

        if not material_ids_in_txns:
            return DailyReportResponse(
                report_date=date,
                customer_id=customer_id or 0,
                customer_name="",
                summary=DailyReportSummary(
                    total_materials=0, total_in=0, total_out=0,
                    total_balance=0, total_reels_on_shelf=0, total_reels_tracking=0,
                ),
                details=[],
            )

        details = []
        total_in = 0.0
        total_out = 0.0
        total_reels_on_shelf = 0
        total_reels_tracking = 0

        for mat_id in sorted(material_ids_in_txns):
            # --- Material name ---
            mat_result = await db.execute(
                select(MaterialMaster.code, MaterialMaster.name)
                .where(MaterialMaster.id == mat_id)
            )
            mat_row = mat_result.one_or_none()
            if not mat_row:
                continue
            material_code = mat_row.code
            material_name = mat_row.name

            # --- Opening balance: sum of all transactions BEFORE the report date ---
            opening_result = await db.execute(
                select(func.coalesce(func.sum(
                    func.case(
                        (Transaction.type.in_(["in", "restock", "reverse_in"]), Transaction.quantity),
                        else_=0 - Transaction.quantity,
                    )
                ), 0))
                .where(
                    Transaction.material_id == mat_id,
                    Transaction.created_at < datetime.combine(report_date, datetime.min.time()),
                )
            )
            # Actually, let's do a simpler approach:
            # opening = sum(in) - sum(out) for all transactions before report date
            opening_in_result = await db.execute(
                select(func.coalesce(func.sum(Transaction.quantity), 0))
                .where(
                    Transaction.material_id == mat_id,
                    Transaction.type.in_(["in", "restock"]),
                    Transaction.created_at < datetime.combine(report_date, datetime.min.time()),
                )
            )
            opening_out_result = await db.execute(
                select(func.coalesce(func.sum(Transaction.quantity), 0))
                .where(
                    Transaction.material_id == mat_id,
                    Transaction.type == "out",
                    Transaction.created_at < datetime.combine(report_date, datetime.min.time()),
                )
            )
            opening_balance = float(opening_in_result.scalar_one() or 0) - float(opening_out_result.scalar_one() or 0)

            # --- Today's in/out quantities ---
            day_in = 0.0
            day_out = 0.0
            for txn in txns:
                if txn.material_id == mat_id:
                    if txn.type in ("in", "restock"):
                        day_in += float(txn.quantity or 0)
                    elif txn.type == "out":
                        day_out += float(txn.quantity or 0)

            total_in += day_in
            total_out += day_out

            # Closing balance = opening + in - out
            closing_balance = opening_balance + day_in - day_out

            # --- Current on-shelf / tracking pallet counts ---
            shelf_count = 0
            tracking_count = 0

            shelf_result = await db.execute(
                select(func.count())
                .where(
                    InventoryReel.material_id == mat_id,
                    InventoryReel.status == "on_shelf",
                )
            )
            shelf_count = shelf_result.scalar_one() or 0

            tracking_result = await db.execute(
                select(func.count())
                .where(
                    InventoryReel.material_id == mat_id,
                    InventoryReel.status == "tracking",
                )
            )
            tracking_count = tracking_result.scalar_one() or 0

            total_reels_on_shelf += shelf_count
            total_reels_tracking += tracking_count

            details.append(DailyReportDetail(
                material_id=mat_id,
                material_code=material_code,
                material_name=material_name,
                opening_balance=max(0, opening_balance),
                in_qty=day_in,
                out_qty=day_out,
                closing_balance=max(0, closing_balance),
                reels_on_shelf=shelf_count,
                reels_tracking=tracking_count,
            ))

        total_balance = sum(d.closing_balance for d in details)

        # Customer name
        customer_name = ""
        if customer_id:
            c_result = await db.execute(
                select(Customer.name).where(Customer.id == customer_id)
            )
            customer_name = c_result.scalar_one_or_none() or ""

        summary = DailyReportSummary(
            total_materials=len(details),
            total_in=total_in,
            total_out=total_out,
            total_balance=total_balance,
            total_reels_on_shelf=total_reels_on_shelf,
            total_reels_tracking=total_reels_tracking,
        )

        return DailyReportResponse(
            report_date=date,
            customer_id=customer_id or 0,
            customer_name=customer_name,
            summary=summary,
            details=details,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"报表生成失败: {str(e)}")


@router.get("/customer-summary")
async def get_customer_summary(
    customer_id: int = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get customer summary report with material category breakdown."""
    # Validate customer
    customer_result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = customer_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式无效，请使用 YYYY-MM-DD")

    # Get all categories for this customer
    cat_result = await db.execute(
        select(MaterialCategory).where(MaterialCategory.customer_id == customer_id)
    )
    categories = cat_result.scalars().all()

    by_category = []
    for cat in categories:
        # Get materials in this category
        mat_result = await db.execute(
            select(MaterialMaster.id, MaterialMaster.code, MaterialMaster.name)
            .where(
                MaterialMaster.customer_id == customer_id,
                MaterialMaster.category_id == cat.id,
            )
        )
        materials = mat_result.all()

        if not materials:
            continue

        category_in = 0.0
        category_out = 0.0
        material_details = []

        for mat in materials:
            # Sum transactions in period
            txn_in_result = await db.execute(
                select(func.coalesce(func.sum(Transaction.quantity), 0))
                .where(
                    Transaction.material_id == mat.id,
                    Transaction.type.in_(["in", "restock"]),
                    Transaction.created_at >= start_dt,
                    Transaction.created_at < end_dt,
                )
            )
            txn_out_result = await db.execute(
                select(func.coalesce(func.sum(Transaction.quantity), 0))
                .where(
                    Transaction.material_id == mat.id,
                    Transaction.type == "out",
                    Transaction.created_at >= start_dt,
                    Transaction.created_at < end_dt,
                )
            )
            mat_in = float(txn_in_result.scalar_one() or 0)
            mat_out = float(txn_out_result.scalar_one() or 0)
            category_in += mat_in
            category_out += mat_out

            if mat_in > 0 or mat_out > 0:
                material_details.append({
                    "material_code": mat.code,
                    "material_name": mat.name,
                    "in_qty": mat_in,
                    "out_qty": mat_out,
                })

        by_category.append({
            "category_id": cat.id,
            "category_name": cat.name,
            "in_qty": category_in,
            "out_qty": category_out,
            "materials": material_details,
        })

    return CustomerSummaryResponse(
        customer_name=customer.name,
        period=f"{start_date} ~ {end_date}",
        by_category=by_category,
    )
