"""Operation History service — helper to record operations.

Provides a single `record_operation()` function that can be called
from various places (shelving, issue, receipt, etc.) to log an
operation into the operation_history table.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperationHistory


async def record_operation(
    db: AsyncSession,
    operation_type: str,
    *,
    shelving_mode: Optional[str] = None,
    led_color: Optional[str] = None,
    reel_id: Optional[int] = None,
    reel_code: Optional[str] = None,
    material_id: Optional[int] = None,
    material_code: Optional[str] = None,
    material_name: Optional[str] = None,
    shelf_id: Optional[int] = None,
    shelf_code: Optional[str] = None,
    slot_id: Optional[int] = None,
    slot_code: Optional[str] = None,
    customer_id: Optional[int] = None,
    quantity: Optional[float] = None,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    source_no: Optional[str] = None,
    operator: Optional[str] = None,
    note: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> OperationHistory:
    """Record an operation in the operation_history table.

    Args:
        db: Database session
        operation_type: 操作类型 shelving_on | shelving_off | inventory_in | inventory_out | adjustment
        shelving_mode: 上架模式 auto(智能) | manual(手动) — 仅上架操作
        led_color: 亮灯颜色 red/green/blue/etc — 涉及亮灯的操作
        reel_id: 卷盘ID
        reel_code: 卷盘编码
        material_id: 物料ID
        material_code: 物料编码
        material_name: 物料名称
        shelf_id: 料架ID
        shelf_code: 料架编码
        slot_id: 储位ID
        slot_code: 储位编码
        customer_id: 客户ID
        quantity: 操作数量
        source_type: 来源类型 receipt | issue | xr_transfer | sensor | manual_adjust | direct_outbound | shelving_bind
        source_id: 来源单据ID
        source_no: 来源单号
        operator: 操作人
        note: 备注
        created_at: 操作时间（默认当前时间）

    Returns:
        The created OperationHistory record.
    """
    record = OperationHistory(
        operation_type=operation_type,
        shelving_mode=shelving_mode,
        led_color=led_color,
        reel_id=reel_id,
        reel_code=reel_code,
        material_id=material_id,
        material_code=material_code,
        material_name=material_name,
        shelf_id=shelf_id,
        shelf_code=shelf_code,
        slot_id=slot_id,
        slot_code=slot_code,
        customer_id=customer_id,
        quantity=quantity,
        source_type=source_type,
        source_id=source_id,
        source_no=source_no,
        operator=operator,
        note=note,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(record)
    return record
