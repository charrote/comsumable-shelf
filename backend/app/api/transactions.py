"""Transactions API routes — recent operation history for dashboard."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query

from app.utils.database import get_db
from app.models import Transaction, MaterialMaster
from app.schemas import TransactionRecord

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("/recent", response_model=list[TransactionRecord])
async def get_recent_transactions(
    limit: int = Query(20, ge=1, le=100, description="返回记录条数"),
    db: AsyncSession = Depends(get_db),
):
    """获取最近操作履历，按时间倒序排列，用于仪表盘「最近操作记录」展示。"""
    result = await db.execute(
        select(
            Transaction.id,
            Transaction.type,
            Transaction.quantity,
            Transaction.operator,
            Transaction.created_at,
            MaterialMaster.code.label("material_code"),
            MaterialMaster.name.label("material_name"),
        )
        .join(MaterialMaster, Transaction.material_id == MaterialMaster.id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    rows = result.all()

    return [
        TransactionRecord(
            id=r.id,
            time=r.created_at.isoformat(),
            type=r.type,
            material_code=r.material_code,
            material_name=r.material_name,
            quantity=r.quantity,
            operator=r.operator or "系统",
        )
        for r in rows
    ]
