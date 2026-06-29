"""
灯控调试 API — 专为硬件工程师调试智能料架 LED 控制而设计。

所有接口直接透传 RackApiClient 调用，返回详尽的请求/响应信息，
方便硬件工程师定位通信问题。

⚠ 本模块仅供调试使用，不应用于生产业务流程。
"""

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ShelfResponse
from app.services.rack_api_client import RackApiClient, get_rack_api_config
from app.utils.database import get_db
from app.models import Shelf, ShelfSlot, ShelfSlotEvent, User
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/light-debug", tags=["Light Control Debug"])


# ── 辅助函数 ──────────────────────────────────────────────────────────


async def _get_client(db: AsyncSession) -> RackApiClient:
    """获取 RackApiClient 实例，未配置时抛出 400。"""
    api_config = await get_rack_api_config(db)
    if not api_config:
        raise HTTPException(
            status_code=400,
            detail="未配置控灯服务地址。请在「系统设置」中配置 rack_api_base_url、rack_api_user_id、rack_api_client_id",
        )
    return RackApiClient(
        base_url=api_config["base_url"],
        user_id=api_config["user_id"],
        client_id=api_config["client_id"],
    )


def _ok(data: dict = None, message: str = "ok") -> dict:
    resp = {"status": "ok", "message": message}
    if data is not None:
        resp["data"] = data
    return resp


# ── 获取料架列表（供调试页面下拉选择） ───────────────────────────────


@router.get("/shelves")
async def debug_list_shelves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有启用料架列表，供调试页面的料架选择器使用。"""
    result = await db.execute(
        select(Shelf).where(Shelf.active == 1).order_by(Shelf.code)
    )
    shelves = result.scalars().all()
    return [
        {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "location": s.location,
        }
        for s in shelves
    ]


# ── 单灯调试 ──────────────────────────────────────────────────────────


@router.post("/single")
async def debug_light_up_single(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """点亮单个储位灯。

    请求体::

        {
            "cell_id": "A0010001",      # 储位号（必填）
            "led_color": 1,             # 色值 0-7（必填，0=灭灯）
            "blink": false,             # 是否闪烁
            "turn_on_time": 0,          # 亮灯秒数，0=常亮
        }

    色值映射: 0=灭, 1=红, 2=绿, 3=黄, 4=蓝, 5=洋红, 6=青, 7=白
    """
    cell_id = data.get("cell_id")
    if not cell_id:
        raise HTTPException(status_code=400, detail="cell_id 为必填参数")

    led_color = data.get("led_color", 1)
    blink = data.get("blink", False)
    turn_on_time = data.get("turn_on_time", 0)

    client = await _get_client(db)
    try:
        raw = await client.light_up_cell(
            cell_id=cell_id,
            led_color=led_color,
            is_blink=blink,
            turn_on_time=turn_on_time,
        )
        return _ok({
            "request": {
                "cell_id": cell_id,
                "led_color": led_color,
                "blink": blink,
                "turn_on_time": turn_on_time,
            },
            "response": raw,
        }, "单灯指令已发送")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")


# ── 批量调试 ──────────────────────────────────────────────────────────


@router.post("/batch")
async def debug_light_up_batch(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量点亮多个储位灯，支持语音播报。

    请求体::

        {
            "cells": [
                {"cell_id": "A0010001", "led_color": 1, "blink": true},
                {"cell_id": "A0010002", "led_color": 2, "blink": false}
            ],
            "turn_on_time": 0,
            "voice_text": ""
        }
    """
    cells = data.get("cells")
    if not cells or not isinstance(cells, list) or len(cells) == 0:
        raise HTTPException(status_code=400, detail="cells 为必填参数，且至少包含一项")

    turn_on_time = data.get("turn_on_time", 0)
    voice_text = data.get("voice_text", "")

    # 校验并转换格式
    formatted_cells = []
    for c in cells:
        formatted_cells.append({
            "cellId": c["cell_id"],
            "ledColor": c.get("led_color", 1),
            "blink": c.get("blink", False),
        })

    client = await _get_client(db)
    try:
        raw = await client.light_up_cells_batch(
            cells=formatted_cells,
            turn_on_time=turn_on_time,
            voice_text=voice_text,
        )
        return _ok({
            "request": {
                "cells": cells,
                "turn_on_time": turn_on_time,
                "voice_text": voice_text,
            },
            "response": raw,
        }, "批量灯指令已发送")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")


# ── 警示灯调试 ────────────────────────────────────────────────────────


@router.post("/indicator")
async def debug_set_indicator(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """设置料架警示灯状态。

    请求体::

        {
            "rack_id": "A001",          # 料架号（必填）
            "indicator_id": 0,          # 警示灯位置 0=正面, 1=反面, 2=双面
            "indicator_status": 1,      # 色值组合 0-7
            "blink": false
        }

    警示灯色值: 0=关, 1=红, 2=黄, 3=红+黄, 4=绿, 5=红+绿, 6=黄+绿, 7=红+黄+绿
    """
    rack_id = data.get("rack_id")
    if not rack_id:
        raise HTTPException(status_code=400, detail="rack_id 为必填参数")

    indicator_id = data.get("indicator_id", 0)
    indicator_status = data.get("indicator_status", 1)
    blink = data.get("blink", False)

    client = await _get_client(db)
    try:
        raw = await client.set_indicator_status(
            rack_id=rack_id,
            indicator_id=indicator_id,
            indicator_status=indicator_status,
            is_blink=blink,
        )
        return _ok({
            "request": {
                "rack_id": rack_id,
                "indicator_id": indicator_id,
                "indicator_status": indicator_status,
                "blink": blink,
            },
            "response": raw,
        }, "警示灯指令已发送")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")


# ── 料架测试 ──────────────────────────────────────────────────────────


@router.post("/test")
async def debug_rack_test(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """料架硬件测试。

    请求体::

        {
            "rack_id": "A001",      # 料架号或储位号
            "test_mode": 15,        # 测试模式（可组合）
            "interval": 1000        # 变化间隔（毫秒）
        }

    测试模式:
        - 0:  取消测试
        - 1:  RGB 灯珠测试
        - 2:  灯序测试
        - 4:  警示灯测试
        - 8:  感应传感器测试
        - 15: 全部测试 (1+2+4+8)
    """
    rack_id = data.get("rack_id")
    if not rack_id:
        raise HTTPException(status_code=400, detail="rack_id 为必填参数")

    test_mode = data.get("test_mode", 15)
    interval = data.get("interval", 1000)

    client = await _get_client(db)
    try:
        raw = await client.rack_test(
            rack_id=rack_id,
            test_mode=test_mode,
            interval=interval,
        )
        return _ok({
            "request": {
                "rack_id": rack_id,
                "test_mode": test_mode,
                "interval": interval,
            },
            "response": raw,
        }, "料架测试指令已发送")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")


# ── 储位查询 ──────────────────────────────────────────────────────────


@router.post("/cell-list")
async def debug_get_cell_list(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询料架储位状态（含电量、当前灯色等）。

    请求体::

        {
            "rack_id": "A001",      # 料架号（可选，不传则查全部）
            "filter": "",           # 储位号筛选（可选）
            "page_index": 1,
            "page_size": 200
        }
    """
    rack_id = data.get("rack_id")
    cell_filter = data.get("filter")
    page_index = data.get("page_index", 1)
    page_size = data.get("page_size", 200)

    client = await _get_client(db)
    try:
        raw = await client.get_cell_list(
            rack_id=rack_id,
            cell_filter=cell_filter,
            page_index=page_index,
            page_size=page_size,
        )
        return _ok({
            "request": {
                "rack_id": rack_id,
                "filter": cell_filter,
                "page_index": page_index,
                "page_size": page_size,
            },
            "response": raw,
        }, "储位状态查询完成")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")


# ── 快捷灭灯 ──────────────────────────────────────────────────────────


@router.post("/turn-off")
async def debug_turn_off(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """关闭指定储位灯（通过发送 led_color=0 实现）。

    请求体::

        {
            "cell_id": "A0010001"   # 储位号（必填）
        }
    """
    cell_id = data.get("cell_id")
    if not cell_id:
        raise HTTPException(status_code=400, detail="cell_id 为必填参数")

    client = await _get_client(db)
    try:
        raw = await client.light_up_cell(
            cell_id=cell_id,
            led_color=0,
            is_blink=False,
            turn_on_time=0,
        )
        return _ok({
            "request": {"cell_id": cell_id, "led_color": 0},
            "response": raw,
        }, f"储位 {cell_id} 灯已关闭")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")


@router.post("/turn-off-all")
async def debug_turn_off_all(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """关闭整个料架所有储位灯。

    请求体::

        {
            "rack_id": "A001",      # 料架号（必填）
            "page_size": 500        # 一次性查询的储位数量上限
        }
    """
    rack_id = data.get("rack_id")
    if not rack_id:
        raise HTTPException(status_code=400, detail="rack_id 为必填参数")

    page_size = data.get("page_size", 500)

    client = await _get_client(db)

    # 第一步：查询料架所有储位
    try:
        cell_data = await client.get_cell_list(rack_id=rack_id, page_size=page_size)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"查询储位列表失败: {e}")

    items = cell_data.get("data", []) or cell_data.get("resultData", {}).get("items", [])
    if not items:
        # 尝试其他可能的响应格式
        items = cell_data.get("resultData", [])
    if not items:
        return _ok({
            "rack_id": rack_id,
            "cells_found": 0,
            "turned_off": 0,
            "response": cell_data,
        }, "料架下未找到储位，无需灭灯")

    # 第二步：逐个发送灭灯指令
    cell_ids = []
    for item in items:
        cid = item.get("cellId") or item.get("cell_id")
        if cid:
            cell_ids.append(cid)

    success_count = 0
    errors = []
    for cid in cell_ids:
        try:
            await client.light_up_cell(cell_id=cid, led_color=0, is_blink=False, turn_on_time=0)
            success_count += 1
        except Exception as e:
            errors.append({"cell_id": cid, "error": str(e)})

    return _ok({
        "rack_id": rack_id,
        "cells_found": len(cell_ids),
        "turned_off": success_count,
        "errors": errors if errors else None,
    }, f"灭灯完成: 成功 {success_count}/{len(cell_ids)}")


# ── 回调事件查询 ──────────────────────────────────────────────────────


@router.get("/callback-events")
async def debug_callback_events(
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
    shelf_id: Optional[int] = Query(None, description="按料架筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询最近的储位变化回调事件日志。

    返回 callback 处理记录（ShelfSlotEvent），按时间倒序排列。
    硬件工程师可在此确认硬件触发的回调是否被系统正确接收和处理。
    """
    query = (
        select(
            ShelfSlotEvent.id,
            ShelfSlotEvent.cell_id,
            ShelfSlotEvent.event_type,
            ShelfSlotEvent.source,
            ShelfSlotEvent.old_state,
            ShelfSlotEvent.new_state,
            ShelfSlotEvent.reel_id,
            ShelfSlotEvent.created_at,
            ShelfSlotEvent.raw_data,
            ShelfSlot.id.label("slot_id"),
            ShelfSlot.cell_id.label("slot_cell_id"),
            Shelf.code.label("shelf_code"),
        )
        .outerjoin(ShelfSlot, ShelfSlotEvent.shelf_slot_id == ShelfSlot.id)
        .outerjoin(Shelf, ShelfSlot.shelf_id == Shelf.id)
        .order_by(desc(ShelfSlotEvent.created_at))
    )

    if shelf_id is not None:
        query = query.where(ShelfSlot.shelf_id == shelf_id)

    result = await db.execute(query.limit(limit))
    rows = result.all()

    return [
        {
            "id": row.id,
            "cell_id": row.cell_id,
            "event_type": row.event_type,
            "source": row.source,
            "old_state": row.old_state,
            "new_state": row.new_state,
            "reel_id": row.reel_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "raw_data": row.raw_data,
            "slot_info": {
                "slot_id": row.slot_id,
                "cell_id": row.slot_cell_id,
                "shelf_code": row.shelf_code,
            } if row.slot_id else None,
        }
        for row in rows
    ]


# ── 传感器测试触发 ──────────────────────────────────────────────────


@router.post("/sensor-test")
async def debug_sensor_test(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对指定料架运行传感器测试（test_mode=8），辅助触发回调。

    传感器测试会触发料架所有储位的传感器进行自检，
    自检过程中产生的状态变化会以回调形式发送到系统，
    从而达到测试回调链路的目的。

    请求体::

        {
            "rack_id": "A001",      # 料架号（必填）
            "interval": 2000        # 测试间隔毫秒
        }
    """
    rack_id = data.get("rack_id")
    if not rack_id:
        raise HTTPException(status_code=400, detail="rack_id 为必填参数")

    interval = data.get("interval", 2000)

    client = await _get_client(db)
    try:
        raw = await client.rack_test(
            rack_id=rack_id,
            test_mode=8,  # 传感器测试
            interval=interval,
        )
        return _ok({
            "request": {
                "rack_id": rack_id,
                "test_mode": 8,
                "mode_desc": "感应传感器测试",
                "interval": interval,
            },
            "response": raw,
            "note": "传感器测试已启动，请观察料架上的储位指示灯。"
                    "传感器自检产生的状态变化会以回调形式发送到系统，"
                    "可在下方「回调日志」中查看接收到的回调事件。",
        }, "传感器测试指令已发送，请观察回调日志")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")
