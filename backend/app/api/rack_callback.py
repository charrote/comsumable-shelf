"""
料架储位变化回调接口。

接收新智能料架的 HTTP 回调通知，处理储位变化事件：
  - status=1（放入）: 自动绑定待上架料盘
  - status=0（取出）: 记录释放事件

与轮询服务（RackSlotPoller）配合使用：回调处理即时变化，轮询用于一致性校验。

设计依据：《智能料架重构任务清单》T4 - 储位变化回调接口
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.utils.database import get_db
from app.models import ShelfSlot, Shelf, InventoryReel, MaterialMaster, ShelfSlotEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rack", tags=["Rack Callback"])


# ── Schemas ──────────────────────────────────────────────────────────


class CellChangeItem(BaseModel):
    """单个储位变化项"""
    cellId: str
    status: int  # 0=取出, 1=放入
    timestamp: str


class CellChangeCallbackRequest(BaseModel):
    """储位变化回调请求"""
    data: List[CellChangeItem]
    code: int = 0
    message: str = ""
    sessionId: str = ""


class CellChangeCallbackResponse(BaseModel):
    """储位变化回调响应"""
    code: int = 0
    message: str = "OK"
    sessionId: str = ""


# ── 路由 ─────────────────────────────────────────────────────────────


@router.post("/callback/cell-changed", response_model=CellChangeCallbackResponse)
async def cell_change_callback(
    data: CellChangeCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """接收料架储位变化回调

    处理流程:
        1. 查找 cell_id → ShelfSlot
        2. status=1（放入）→ 查找待上架料盘并自动绑定
        3. 记录 ShelfSlotEvent
        4. 更新 slot 状态
        5. WebSocket 推送通知（含绑定详情）
    """
    session_id = data.sessionId
    processed = 0
    # 收集待广播消息（commit 后统一推送）
    broadcasts: list[dict] = []

    for item in data.data:
        try:
            # 1. 查找 cell_id → shelf_slot
            result = await db.execute(
                select(ShelfSlot).where(ShelfSlot.cell_id == item.cellId)
            )
            slot = result.scalar_one_or_none()
            if not slot:
                logger.warning("Callback unknown cell_id: %s", item.cellId)
                continue

            bound_reel_id = None
            binding_info = None  # 自动绑定的详情，用于广播

            if item.status == 1:
                # ── 放入事件 → 自动绑定 ──
                reel = await _find_unbound_reel(db)
                if reel:
                    # 检查储位是否已被占用
                    existing = await db.execute(
                        select(InventoryReel).where(
                            InventoryReel.shelf_slot_id == slot.id,
                            InventoryReel.status == "on_shelf",
                        ).limit(1)
                    )
                    if not existing.scalar_one_or_none():
                        reel.shelf_slot_id = slot.id
                        reel.status = "on_shelf"
                        reel.updated_at = datetime.utcnow()
                        bound_reel_id = reel.id

                        # 获取料架/储位编码
                        slot_info = await db.execute(
                            select(ShelfSlot, Shelf.code)
                            .join(Shelf, ShelfSlot.shelf_id == Shelf.id)
                            .where(ShelfSlot.id == slot.id)
                        )
                        row = slot_info.one_or_none()
                        shelf_code = row[1] if row else ""
                        slot_obj = row[0] if row else None
                        slot_code = slot_obj.code or str(slot_obj.slot_on_board) if slot_obj else ""

                        # 获取物料信息
                        material_info = await db.execute(
                            select(MaterialMaster.code, MaterialMaster.name)
                            .where(MaterialMaster.id == reel.material_id)
                        )
                        mat_row = material_info.one_or_none()
                        material_code = mat_row[0] if mat_row else ""
                        material_name = mat_row[1] if mat_row else ""

                        binding_info = {
                            "reel_id": reel.id,
                            "cell_id": item.cellId,
                            "shelf_code": shelf_code,
                            "slot_code": slot_code,
                            "material_code": material_code,
                            "material_name": material_name,
                            "timestamp": item.timestamp,
                        }

                        logger.info(
                            "Auto-bound reel %d to slot %d (cell: %s, shelf: %s/%s)",
                            reel.id, slot.id, item.cellId, shelf_code, slot_code,
                        )

            # 2. 记录事件
            event = ShelfSlotEvent(
                shelf_slot_id=slot.id,
                event_type="occupied" if item.status == 1 else "released",
                reel_id=bound_reel_id,
                source="api",
                old_state=abs(1 - item.status),
                new_state=item.status,
                cell_id=item.cellId,
                raw_data=item.model_dump_json(),
            )
            db.add(event)

            # 3. 更新 slot 状态
            slot.last_event_at = datetime.utcnow()
            slot.last_sensor_state = item.status

            processed += 1

            # 4. 收集广播消息
            if binding_info:
                broadcasts.append({"type": "reel_bound", "data": binding_info})
            else:
                broadcasts.append({
                    "type": "cell_changed",
                    "data": {
                        "cell_id": item.cellId,
                        "status": item.status,
                        "timestamp": item.timestamp,
                    },
                })

        except Exception as e:
            logger.error("Callback processing error: %s", e, exc_info=True)

    await db.commit()

    # ── WebSocket 推送 ──
    try:
        from app.services.websocket_service import ws_manager as _ws
        for b in broadcasts:
            await _ws.broadcast(b["type"], b["data"])
    except Exception as e:
        logger.warning("WebSocket broadcast failed: %s", e)

    logger.info("Callback processed: %d/%d items, %d broadcasts (session=%s)",
                processed, len(data.data), len(broadcasts), session_id)
    return CellChangeCallbackResponse(
        sessionId=session_id,
        message=f"Processed {processed} items",
    )


# ── 辅助函数 ─────────────────────────────────────────────────────────


async def _find_unbound_reel(db: AsyncSession) -> Optional[InventoryReel]:
    """查找最旧的待上架料盘

    条件:
        - shelf_slot_id IS NULL
        - status = 'pending_shelving'
    排序:
        - created_at ASC（先进先上架）
    """
    result = await db.execute(
        select(InventoryReel)
        .where(
            InventoryReel.shelf_slot_id.is_(None),
            InventoryReel.status == "pending_shelving",
        )
        .order_by(InventoryReel.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()
