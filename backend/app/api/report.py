"""Report API routes."""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query
from app.schemas import (
    DailyReportResponse, DailyReportSummary, DailyReportDetail,
    CustomerSummaryResponse,
)
from app.utils.database import get_db
from app.models import Transaction, MaterialMaster, InventoryPallet, Customer

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/daily")
async def get_daily_report(
    date: str = Query(..., description="YYYY-MM-DD"),
    customer_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get daily report."""
    try:
        day_transactions = await db.execute(
            select(Transaction, MaterialMaster.code.label("material_code"))
            .join(MaterialMaster, Transaction.material_id == MaterialMaster.id, isouter=True)
            .where(
                func.date(Transaction.created_at) == date,
            )
        )
        rows = day_transactions.all() or []

        material_stats = {}
        for row in rows:
            txn = row[0] if hasattr(row, '__getitem__') else row
            code = row.material_code if hasattr(row, 'material_code') else (row[1] if len(row) > 1 else "")
            mat_id = txn.material_id or 0
            if mat_id not in material_stats:
                material_stats[mat_id] = {
                    "material_id": mat_id,
                    "material_code": code or "",
                    "in_qty": 0.0,
                    "out_qty": 0.0,
                }
            if txn.type in ("in", "restock"):
                material_stats[mat_id]["in_qty"] += float(txn.quantity or 0)
            elif txn.type == "out":
                material_stats[mat_id]["out_qty"] += float(txn.quantity or 0)

        details = []
        total_in = 0.0
        total_out = 0.0

        for mat_id, stats in material_stats.items():
            if not stats["material_code"]:
                continue
            in_qty = stats["in_qty"]
            out_qty = stats["out_qty"]
            total_in += in_qty
            total_out += out_qty

            stock_result = await db.execute(
                select(func.coalesce(func.sum(InventoryPallet.quantity), 0))
                .where(
                    InventoryPallet.material_id == mat_id,
                    InventoryPallet.status == "on_shelf",
                )
            )
            stock = stock_result.scalar_one() or 0

            details.append(DailyReportDetail(
                material_id=mat_id,
                material_code=stats["material_code"],
                material_name=stats["material_code"],
                opening_balance=0.0,
                in_qty=in_qty,
                out_qty=out_qty,
                closing_balance=float(stock),
                pallets_on_shelf=0,
                pallets_tracking=0,
            ))

        summary = DailyReportSummary(
            total_materials=len(details),
            total_in=total_in,
            total_out=total_out,
            total_balance=total_in - total_out,
            total_pallets_on_shelf=0,
            total_pallets_tracking=0,
        )

        return DailyReportResponse(
            report_date=date,
            customer_id=customer_id or 0,
            customer_name="",
            summary=summary,
            details=details,
        )
    except Exception:
        return DailyReportResponse(
            report_date=date,
            customer_id=customer_id or 0,
            customer_name="",
            summary=DailyReportSummary(
                total_materials=0, total_in=0, total_out=0,
                total_balance=0, total_pallets_on_shelf=0, total_pallets_tracking=0,
            ),
            details=[],
        )


@router.get("/customer-summary")
async def get_customer_summary(
    customer_id: int = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get customer summary report."""
    customer_result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = customer_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    return CustomerSummaryResponse(
        customer_name=customer.name,
        period=f"{start_date} ~ {end_date}",
        by_category=[],
    )
