"""Shelf management API routes — CRUD + smart shelf operations."""

from typing import Optional, List
from sqlalchemy import select, func, delete, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, Query
import structlog

logger = structlog.get_logger()
from app.schemas import (
    ShelfCreate, ShelfUpdate, ShelfResponse,
    ShelfSlotCreate, ShelfSlotUpdate, ShelfSlotResponse,
)
from app.services.rack_api_client import RackApiClient, get_rack_api_config
from app.utils.database import get_db
from app.models import Shelf, ShelfSlot, ShelfSlotEvent, InventoryReel

router = APIRouter(prefix="/shelves", tags=["Shelf Management"])


# ── 辅助函数 ──────────────────────────────────────────────────────────


def _compute_cell_id(shelf_code: str, slot_code: str) -> str:
    """自动生成 cell_id: UPPER(shelf_code + slot_code)"""
    return f"{shelf_code}{slot_code}".upper()


async def _get_shelf_or_404(shelf_id: int, db: AsyncSession) -> Shelf:
    result = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    shelf = result.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=404, detail="料架不存在")
    return shelf


async def _get_slot_or_404(slot_id: int, shelf_id: int, db: AsyncSession) -> ShelfSlot:
    result = await db.execute(
        select(ShelfSlot).where(
            ShelfSlot.id == slot_id,
            ShelfSlot.shelf_id == shelf_id,
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="储位不存在")
    return slot


def _shelf_to_response(shelf: Shelf, slot_count: int = 0) -> ShelfResponse:
    return ShelfResponse(
        id=shelf.id,
        code=shelf.code,
        name=shelf.name,
        location=shelf.location,
        active=shelf.active,
        slot_count=slot_count,
    )


def _slot_to_response(slot: ShelfSlot) -> ShelfSlotResponse:
    return ShelfSlotResponse(
        id=slot.id,
        shelf_id=slot.shelf_id,
        code=slot.code,
        name=slot.name,
        cell_id=slot.cell_id,
        max_quantity=slot.max_quantity,
        last_event_at=slot.last_event_at,
        last_sensor_state=slot.last_sensor_state,
    )


# ── 料架 CRUD ─────────────────────────────────────────────────────────


@router.get("")
async def list_shelves(
    active: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Shelf)
    if active is not None:
        query = query.where(Shelf.active == active)
    query = query.order_by(Shelf.code)
    result = await db.execute(query)
    shelves = result.scalars().all()

    # 批量查询 slot_count
    shelf_ids = [s.id for s in shelves]
    if shelf_ids:
        count_query = (
            select(ShelfSlot.shelf_id, func.count(ShelfSlot.id))
            .where(ShelfSlot.shelf_id.in_(shelf_ids))
            .group_by(ShelfSlot.shelf_id)
        )
        count_result = await db.execute(count_query)
        slot_counts = dict(count_result.all())
    else:
        slot_counts = {}

    return [
        _shelf_to_response(s, slot_counts.get(s.id, 0)) for s in shelves
    ]


@router.post("")
async def create_shelf(
    data: ShelfCreate,
    db: AsyncSession = Depends(get_db),
):
    shelf = Shelf(
        code=data.code,
        name=data.name,
        location=data.location,
        active=1,
    )
    db.add(shelf)
    await db.commit()
    await db.refresh(shelf)
    return _shelf_to_response(shelf)


@router.get("/{shelf_id}")
async def get_shelf(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    shelf = await _get_shelf_or_404(shelf_id, db)
    # 查储位数量
    count_result = await db.execute(
        select(func.count(ShelfSlot.id))
        .where(ShelfSlot.shelf_id == shelf_id)
    )
    slot_count = count_result.scalar() or 0
    return _shelf_to_response(shelf, slot_count)


@router.put("/{shelf_id}")
async def update_shelf(
    shelf_id: int,
    data: ShelfUpdate,
    db: AsyncSession = Depends(get_db),
):
    shelf = await _get_shelf_or_404(shelf_id, db)
    old_code = shelf.code

    if data.code is not None:
        shelf.code = data.code
    if data.name is not None:
        shelf.name = data.name
    if data.location is not None:
        shelf.location = data.location

    await db.commit()

    # 如果 code 变了，重新生成所有关联储位的 cell_id
    if data.code is not None and data.code != old_code:
        slots_result = await db.execute(
            select(ShelfSlot).where(ShelfSlot.shelf_id == shelf_id)
        )
        for slot in slots_result.scalars().all():
            slot.cell_id = _compute_cell_id(shelf.code, slot.code)
        await db.commit()

    await db.refresh(shelf)
    return _shelf_to_response(shelf)


@router.delete("/{shelf_id}")
async def delete_shelf(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a shelf (hard delete).

    - Cascades: shelf_slot_events → shelf_slots → shelf
    - If any inventory_reels or other business records reference the shelf's slots,
      returns HTTP 409 with detailed message (same pattern as material master delete).
    """
    result = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    shelf = result.scalar_one_or_none()
    if not shelf:
        raise HTTPException(status_code=404, detail="料架不存在")

    # Collect all slot IDs belonging to this shelf
    slots_result = await db.execute(
        select(ShelfSlot.id).where(ShelfSlot.shelf_id == shelf_id)
    )
    slot_ids = [row[0] for row in slots_result.all()]

    # ── Check FK references ──────────────────────────────────────────
    ref_tables: list[tuple[str, str, str]] = [
        ("inventory_reels", "shelf_slot_id", "库存记录"),
    ]

    # Dynamically discover additional FK references from PostgreSQL catalog
    fk_discovery_sql = text("""
        SELECT
            pgc.conrelid::regclass::text AS ref_table,
            a.attname AS ref_column,
            pgc.conname AS constraint_name
        FROM pg_constraint pgc
        JOIN pg_attribute a
            ON a.attnum = ANY(pgc.conkey)
            AND a.attrelid = pgc.conrelid
        WHERE pgc.contype = 'f'
          AND pgc.conrelid::regclass::text != 'shelves'
          AND pgc.confrelid::regclass::text = 'shelves'
          AND pgc.conkey[1] = a.attnum
    """)
    try:
        fk_result = await db.execute(fk_discovery_sql)
        fk_rows = fk_result.fetchall()
        for row in fk_rows:
            ref_table = row[0]
            ref_column = row[1]
            constraint_name = row[2]
            if not any(r[0] == ref_table for r in ref_tables):
                ref_tables.append(
                    (ref_table, ref_column, f"外键约束:{constraint_name}")
                )
    except Exception:
        pass

    referenced_by = []

    if slot_ids:
        for table, fk_column, label in ref_tables:
            try:
                count_result = await db.execute(
                    text(
                        f"SELECT COUNT(*) FROM {table} WHERE {fk_column} = ANY(:slot_ids)"
                    ),
                    {"slot_ids": slot_ids},
                )
                count = count_result.scalar()
                if count and count > 0:
                    referenced_by.append(f"{label}({count}条)")
            except Exception:
                pass

        # Also check references that point directly to shelves (e.g. led_commands.shelf_id)
        try:
            led_count = await db.execute(
                text("SELECT COUNT(*) FROM led_commands WHERE shelf_id = :sid"),
                {"sid": shelf_id},
            )
            led_val = led_count.scalar() or 0
            if led_val > 0:
                referenced_by.append(f"控灯指令({led_val}条)")
        except Exception:
            pass

    if referenced_by:
        ref_detail = "、".join(referenced_by)
        raise HTTPException(
            status_code=409,
            detail=(
                f"料架 '{shelf.code}' 无法删除，已被以下模块引用：{ref_detail}。"
                f"请先清理相关引用记录后再试。"
            ),
        )

    # ── Cascade delete: events → slots → shelf ──────────────────────
    if slot_ids:
        await db.execute(
            delete(ShelfSlotEvent).where(ShelfSlotEvent.shelf_slot_id.in_(slot_ids))
        )
        await db.execute(
            delete(ShelfSlot).where(ShelfSlot.shelf_id == shelf_id)
        )

    await db.execute(delete(Shelf).where(Shelf.id == shelf_id))
    await db.commit()
    return {"status": "ok", "message": f"料架 '{shelf.code}' 已永久删除"}


# ── 储位管理 ──────────────────────────────────────────────────────────


@router.get("/{shelf_id}/slots")
async def list_slots(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    await _get_shelf_or_404(shelf_id, db)
    result = await db.execute(
        select(ShelfSlot)
        .where(ShelfSlot.shelf_id == shelf_id)
        .order_by(ShelfSlot.slot_on_board)
    )
    return [_slot_to_response(s) for s in result.scalars().all()]


@router.post("/{shelf_id}/slots")
async def create_slot(
    shelf_id: int,
    data: ShelfSlotCreate,
    db: AsyncSession = Depends(get_db),
):
    """新增储位，自动生成 cell_id = UPPER(shelf_code + 4位补零code)"""
    shelf = await _get_shelf_or_404(shelf_id, db)

    padded_code = str(int(data.code)).zfill(4)
    cell_id = f"{shelf.code}{padded_code}".upper()

    # 全局 cell_id 唯一性检查
    dup = await db.execute(
        select(ShelfSlot).where(ShelfSlot.cell_id == cell_id).limit(1)
    )
    dup = dup.scalar_one_or_none()
    if dup:
        raise HTTPException(
            status_code=409,
            detail=(
                f"cell_id {cell_id} 已被占用"
                f"（料架 {dup.shelf_id}"
                f"{', 编号 ' + dup.code if dup.code else ''}"
                f"{', 名称 ' + dup.name if dup.name else ''}）"
            ),
        )

    # 自动分配 slot_on_board 避免 uq_slot_pos 唯一约束冲突
    max_board = await db.execute(
        select(func.max(ShelfSlot.slot_on_board)).where(ShelfSlot.shelf_id == shelf_id)
    )
    slot_on_board = (max_board.scalar() or 0) + 1

    slot = ShelfSlot(
        shelf_id=shelf_id,
        slot_on_board=slot_on_board,
        code=padded_code,
        name=data.name,
        cell_id=cell_id,
        max_quantity=data.max_quantity,
    )
    db.add(slot)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        error_str = str(e)
        logger.warning("create_slot integrity_error", cell_id=cell_id, error=error_str)
        if "violates not-null constraint" in error_str:
            raise HTTPException(
                status_code=400,
                detail="储位创建失败：数据库缺少必要字段，请联系管理员",
            )
        raise HTTPException(
            status_code=409,
            detail=f"cell_id {cell_id} 已被其他储位使用（并发冲突），请重试",
        )
    await db.refresh(slot)
    return _slot_to_response(slot)


@router.put("/{shelf_id}/slots/{slot_id}")
async def update_slot(
    shelf_id: int,
    slot_id: int,
    data: ShelfSlotUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新储位信息，若 code 改变则重新生成 cell_id"""
    shelf = await _get_shelf_or_404(shelf_id, db)
    slot = await _get_slot_or_404(slot_id, shelf_id, db)

    if data.code is not None:
        slot.code = data.code
    if data.name is not None:
        slot.name = data.name
    if data.max_quantity is not None:
        slot.max_quantity = data.max_quantity

    # 如果 code 变了或 cell_id 为空，重新生成
    if data.code is not None or not slot.cell_id:
        slot.cell_id = _compute_cell_id(shelf.code, slot.code)

    await db.commit()
    await db.refresh(slot)
    return _slot_to_response(slot)


@router.delete("/{shelf_id}/slots/{slot_id}")
async def delete_slot(
    shelf_id: int,
    slot_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除储位"""
    await _get_shelf_or_404(shelf_id, db)
    slot = await _get_slot_or_404(slot_id, shelf_id, db)
    await db.delete(slot)
    await db.commit()
    return {"status": "ok", "message": "储位已删除"}


# ═══════════════════════════════════════════════
# 智能料架硬件功能
# ═══════════════════════════════════════════════

@router.post("/{shelf_id}/rack-test")
async def rack_test(
    shelf_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """料架硬件灯测试

    请求体::

        {"test_mode": 15, "interval": 1000}

    test_mode:
        - 0: 取消测试
        - 1: RGB 灯珠测试
        - 2: 灯序测试
        - 4: 警示灯测试
        - 8: 感应传感器测试
        - 15: 全部测试
    """
    shelf = await _get_shelf_or_404(shelf_id, db)

    api_config = await get_rack_api_config(db)
    if not api_config:
        raise HTTPException(status_code=400, detail="未配置控灯服务地址（请在系统设置中配置 rack_api_base_url）")

    test_mode = data.get("test_mode", 15)
    interval = data.get("interval", 1000)

    try:
        async with RackApiClient(
            base_url=api_config["base_url"],
            user_id=api_config["user_id"],
            client_id=api_config["client_id"],
        ) as client:
            result = await client.rack_test(rack_id=shelf.code, test_mode=test_mode, interval=interval)
        return {
            "status": "ok",
            "shelf_id": shelf_id,
            "rackNo": shelf.code,
            "test_mode": test_mode,
            "result": result,
            "message": f"灯测试指令已发送 (mode={test_mode})",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")


@router.get("/{shelf_id}/slots/state-extended")
async def get_slot_states_extended(
    shelf_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取储位扩展状态（含电池电量、灯色等）

    通过 rackNo 调用 GetCellList 获取实时储位数据。
    """
    shelf = await _get_shelf_or_404(shelf_id, db)

    api_config = await get_rack_api_config(db)
    if not api_config:
        raise HTTPException(status_code=400, detail="未配置控灯服务地址（请在系统设置中配置 rack_api_base_url）")

    try:
        async with RackApiClient(
            base_url=api_config["base_url"],
            user_id=api_config["user_id"],
            client_id=api_config["client_id"],
        ) as client:
            result = await client.get_cell_list(rack_id=shelf.code, page_size=200)
        cells = result.get("data", [])
        return {
            "shelf_id": shelf_id,
            "rackNo": shelf.code,
            "cells": cells,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"控灯 API 调用失败: {e}")
