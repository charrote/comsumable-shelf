"""Operation History API — 作业履历查询接口。

提供时间段内所有库存、货架相关业务操作履历的查询，
涉及上/落架的操作区分智能/手动模式，并标记亮灯颜色。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException, Query

from app.utils.database import get_db
from app.models import (
    OperationHistory, InventoryReel, MaterialMaster,
    Shelf, ShelfSlot, Customer,
)
from app.schemas import (
    OperationHistoryQuery, OperationHistoryRecord, OperationHistoryResponse,
)

router = APIRouter(prefix="/operation-history", tags=["Operation History"])

# ── 操作类型标签映射 ──
OPERATION_TYPE_LABELS = {
    "shelving_on": "上架",
    "shelving_off": "落架",
    "inventory_in": "入库",
    "inventory_out": "出库",
    "adjustment": "调整",
}

SHELVING_MODE_LABELS = {
    "auto": "智能上架",
    "manual": "手动上架",
}

# LED 颜色 → 显示名称
LED_COLOR_LABELS = {
    "red": "红色",
    "green": "绿色",
    "blue": "蓝色",
    "yellow": "黄色",
    "magenta": "品红",
    "cyan": "青色",
    "white": "白色",
}


def _get_operation_type_label(op_type: str) -> str:
    return OPERATION_TYPE_LABELS.get(op_type, op_type)


def _get_shelving_mode_label(mode: Optional[str]) -> Optional[str]:
    if not mode:
        return None
    return SHELVING_MODE_LABELS.get(mode, mode)


def _get_led_color_label(color: Optional[str]) -> Optional[str]:
    if not color:
        return None
    return LED_COLOR_LABELS.get(color, color)


@router.get("", response_model=OperationHistoryResponse)
async def query_operation_history(
    start_time: str = Query(..., description="开始时间 (ISO格式，如 2026-06-01T00:00:00)"),
    end_time: str = Query(..., description="结束时间 (ISO格式，如 2026-06-30T23:59:59)"),
    operation_type: Optional[str] = Query(None, description="操作类型筛选"),
    shelving_mode: Optional[str] = Query(None, description="上架模式筛选: auto | manual"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
):
    """查询作业履历 — 支持按时间段、操作类型、上架模式、关键词等筛选。"""
    # Parse time range
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式无效，请使用 ISO 格式 (如 2026-06-01T00:00:00)")

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")

    # Build query
    query = select(OperationHistory).where(
        OperationHistory.created_at >= start_dt,
        OperationHistory.created_at <= end_dt,
    )

    if operation_type:
        valid_types = ["shelving_on", "shelving_off", "inventory_in", "inventory_out", "adjustment"]
        if operation_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"无效的操作类型: {operation_type}，有效值: {', '.join(valid_types)}"
            )
        query = query.where(OperationHistory.operation_type == operation_type)

    if shelving_mode:
        valid_modes = ["auto", "manual"]
        if shelving_mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"无效的上架模式: {shelving_mode}，有效值: {', '.join(valid_modes)}"
            )
        query = query.where(OperationHistory.shelving_mode == shelving_mode)

    if customer_id:
        query = query.where(OperationHistory.customer_id == customer_id)

    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            OperationHistory.material_code.ilike(like)
            | OperationHistory.material_name.ilike(like)
            | OperationHistory.reel_code.ilike(like)
            | OperationHistory.shelf_code.ilike(like)
            | OperationHistory.slot_code.ilike(like)
            | OperationHistory.source_no.ilike(like)
            | OperationHistory.operator.ilike(like)
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page
    query = query.order_by(OperationHistory.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    records = result.scalars().all()

    items = []
    for r in records:
        items.append(OperationHistoryRecord(
            id=r.id,
            operation_type=r.operation_type,
            operation_type_label=_get_operation_type_label(r.operation_type),
            shelving_mode=r.shelving_mode,
            shelving_mode_label=_get_shelving_mode_label(r.shelving_mode),
            led_color=r.led_color,
            reel_id=r.reel_id,
            reel_code=r.reel_code,
            material_id=r.material_id,
            material_code=r.material_code,
            material_name=r.material_name,
            shelf_id=r.shelf_id,
            shelf_code=r.shelf_code,
            slot_id=r.slot_id,
            slot_code=r.slot_code,
            customer_id=r.customer_id,
            quantity=r.quantity,
            source_type=r.source_type,
            source_id=r.source_id,
            source_no=r.source_no,
            operator=r.operator,
            note=r.note,
            created_at=r.created_at.isoformat() if r.created_at else None,
        ))

    return OperationHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/types")
async def get_operation_types():
    """获取所有操作类型列表（用于前端下拉筛选）。"""
    return {
        "operation_types": [
            {"value": "shelving_on", "label": "上架"},
            {"value": "shelving_off", "label": "落架"},
            {"value": "inventory_in", "label": "入库"},
            {"value": "inventory_out", "label": "出库"},
            {"value": "adjustment", "label": "调整"},
        ],
        "shelving_modes": [
            {"value": "auto", "label": "智能上架"},
            {"value": "manual", "label": "手动上架"},
        ],
    }
