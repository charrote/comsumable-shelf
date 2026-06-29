"""Issue (outbound) API routes."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    IssueCreateRequest, IssueOrderListItem, IssueOrderDetail, IssueDetailItem,
    ReelAssignment, IssueCalculateRequest, IssueCalculateResponse,
    IssueAssignResponse, IssueConfirmPickRequest, IssueConfirmPickResponse,
    MaterialCalcResult, ReelSelection,
)
from app.utils.database import get_db
from app.models import (
    IssueOrder, IssueDetail, InventoryReel, LedCommand, ShelfSlot, Shelf,
    Bom, BomItem, MaterialMaster, Transaction, Customer, ReelReservation,
)
from app.services.fifo_service import calculate_fifo_pallets, get_available_qty
from app.services.rack_api_client import RackApiClient, get_rack_api_config
from app.utils.barcode import parse_barcode
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/issues", tags=["Issue/Outbound"])


def _flatten_bom_items(items: List[BomItem]) -> List[dict]:
    """Flatten BOM tree into list of material requirements."""
    result = []
    def walk(item_list, parent_path=""):
        for item in item_list:
            path = f"{parent_path}/{item.material_id}" if parent_path else str(item.material_id)
            result.append({
                "material_id": item.material_id,
                "quantity": item.quantity,
                "path": path,
            })
            if item.children:
                walk(item.children, path)
    walk(items)
    return result


@router.get("")
async def list_issues(
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(IssueOrder).options(
        selectinload(IssueOrder.bom).selectinload(Bom.product_material),
        selectinload(IssueOrder.bom).selectinload(Bom.customer),
    ).order_by(IssueOrder.created_at.desc())

    if customer_id:
        query = query.where(IssueOrder.customer_id == customer_id)
    if status:
        query = query.where(IssueOrder.status == status)

    result = await db.execute(query)
    orders = result.scalars().all()

    items = []
    for order in orders:
        detail_count_result = await db.execute(
            select(func.count(IssueDetail.id)).where(IssueDetail.issue_order_id == order.id)
        )
        detail_count = detail_count_result.scalar() or 0

        product_code = None
        product_name = None
        if order.bom and order.bom.product_material:
            product_code = order.bom.product_material.code
            product_name = order.bom.product_material.name

        customer_name = None
        if order.bom and order.bom.customer:
            customer_name = order.bom.customer.name

        items.append(IssueOrderListItem(
            id=order.id,
            order_no=order.order_no,
            bom_id=order.bom_id,
            product_code=product_code,
            product_name=product_name,
            production_quantity=order.production_quantity,
            customer_id=order.customer_id,
            customer_name=customer_name,
            status=order.status,
            assigned_color=order.assigned_color,
            required_date=order.required_date,
            created_at=order.created_at,
            detail_count=detail_count,
        ))
    return items


@router.get("/{order_id}")
async def get_issue(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IssueOrder).where(IssueOrder.id == order_id).options(
            selectinload(IssueOrder.bom).selectinload(Bom.product_material),
            selectinload(IssueOrder.bom).selectinload(Bom.customer),
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    details_result = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id).options(
            selectinload(IssueDetail.material),
        )
    )
    details = details_result.scalars().all()

    product_code = order.bom.product_material.code if order.bom and order.bom.product_material else None
    product_name = order.bom.product_material.name if order.bom and order.bom.product_material else None
    customer_name = order.bom.customer.name if order.bom and order.bom.customer else None

    detail_items = []
    for d in details:
        reel_assignments = []
        if d.reel_assignments:
            try:
                ra_data = json.loads(d.reel_assignments)
                for ra in ra_data:
                    reel_assignments.append(ReelAssignment(**ra))
            except (json.JSONDecodeError, TypeError):
                pass

        detail_items.append(IssueDetailItem(
            id=d.id,
            material_id=d.material_id,
            material_code=d.material.code if d.material else None,
            material_name=d.material.name if d.material else None,
            material_unit=d.material.unit if d.material else None,
            required_qty=d.required_qty,
            assigned_qty=d.assigned_qty,
            picked_qty=d.picked_qty,
            reel_assignments=reel_assignments,
            shortage=max(0, d.required_qty - d.assigned_qty),
            status=d.status,
        ))

    return IssueOrderDetail(
        id=order.id,
        order_no=order.order_no,
        bom_id=order.bom_id,
        product_code=product_code,
        product_name=product_name,
        production_quantity=order.production_quantity,
        customer_id=order.customer_id,
        customer_name=customer_name,
        status=order.status,
        assigned_color=order.assigned_color,
        required_date=order.required_date,
        created_at=order.created_at,
        details=detail_items,
    )


@router.post("")
async def create_issue(
    data: IssueCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create issue order from BOM + production quantity."""
    bom_result = await db.execute(
        select(Bom).where(Bom.id == data.bom_id).options(
            selectinload(Bom.items).selectinload(BomItem.material),
            selectinload(Bom.items).selectinload(BomItem.children),
            selectinload(Bom.product_material),
        )
    )
    bom = bom_result.scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")

    flat_items = _flatten_bom_items(bom.items)
    material_qty = {}
    for item in flat_items:
        mid = item["material_id"]
        material_qty[mid] = material_qty.get(mid, 0) + item["quantity"]

    order_no = f"ISS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    required_date = None
    if data.required_date:
        try:
            required_date = datetime.fromisoformat(data.required_date)
        except ValueError:
            pass

    order = IssueOrder(
        order_no=order_no,
        bom_id=data.bom_id,
        customer_id=data.customer_id,
        production_quantity=data.production_quantity,
        required_date=required_date,
        status="pending",
    )
    db.add(order)
    await db.flush()

    for material_id, bom_qty in material_qty.items():
        required_qty = bom_qty * data.production_quantity
        detail = IssueDetail(
            issue_order_id=order.id,
            material_id=material_id,
            required_qty=required_qty,
            status="pending",
        )
        db.add(detail)

    await db.commit()
    await db.refresh(order)
    return await get_issue(order.id, db)


@router.post("/{order_id}/calculate", response_model=IssueCalculateResponse)
async def calculate_issue(
    order_id: int,
    data: IssueCalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Calculate FIFO reel assignment for all materials in the issue order.

    Atomic locking:
    - 只有当所有物料都 100% 分配充足（无短缺）时，才锁定料盘并标记为 assigned
    - 存在短缺时不锁定任何料盘，order 保持 pending
    - 整盘出库：每笔拣选都是一整盘
    """
    order_result = await db.execute(select(IssueOrder).where(IssueOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    if order.status != "pending":
        raise HTTPException(status_code=400, detail=f"当前状态不允许计算（当前: {order.status}），仅待计算(pending)状态可执行")

    details_result = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
    )
    details = details_result.scalars().all()

    strategy = data.strategy
    if strategy == "config":
        from app.config import settings
        strategy = settings.FIFO_STRATEGY

    now = datetime.now()
    materials_result = []
    calc_results = []  # 暂存计算结果，用于批量写入

    # ── Phase 1: 对所有物料执行 FIFO 计算 ──
    for detail in details:
        mat_result = await db.execute(
            select(MaterialMaster).where(MaterialMaster.id == detail.material_id)
        )
        mat = mat_result.scalar_one_or_none()
        if not mat:
            continue

        available = await get_available_qty(db, detail.material_id, order.customer_id)
        calc = await calculate_fifo_pallets(
            db, detail.material_id, order.customer_id, detail.required_qty, strategy
        )

        calc_reels = calc.get('reels', [])
        calc_total = calc.get('total_selected', 0)

        shortage = max(0, detail.required_qty - calc_total)

        reel_selections = [
            ReelSelection(
                reel_id=r["reel_id"],
                quantity=r["quantity"],
                last_in_time=r["last_in_time"],
                shelf_slot_id=r["shelf_slot_id"],
            )
            for r in calc_reels
        ]

        materials_result.append(MaterialCalcResult(
            material_id=detail.material_id,
            material_code=mat.code,
            material_name=mat.name,
            required_qty=detail.required_qty,
            available_qty=available,
            strategy=strategy,
            reels_selected=reel_selections,
            total_selected=calc_total,
            shortage=shortage,
        ))

        calc_results.append({
            "detail": detail,
            "mat": mat,
            "calc_reels": calc_reels,
            "calc_total": calc_total,
            "shortage": shortage,
        })

    # ── Phase 2: 检查是否所有物料都无短缺 ──
    any_shortage = any(cr["shortage"] > 0 for cr in calc_results)

    if any_shortage:
        # 缺料 — 不做任何数据库写入，仅返回计算结果
        return IssueCalculateResponse(
            issue_order_id=order_id,
            calculated_at=now,
            strategy_used=strategy,
            materials=materials_result,
        )

    # ── Phase 3: 全部齐套 — 批量创建锁定 + 写回数据库 ──
    all_reel_assignments = []
    for cr in calc_results:
        detail = cr["detail"]
        calc_reels = cr["calc_reels"]
        calc_total = cr["calc_total"]

        # 构建 reel_assignments JSON
        reel_assignments = []
        for r in calc_reels:
            reel_result = await db.execute(
                select(InventoryReel).where(InventoryReel.id == r["reel_id"])
            )
            reel = reel_result.scalar_one_or_none()
            slot_code = None
            if reel and reel.shelf_slot_id:
                slot_result = await db.execute(
                    select(ShelfSlot).where(ShelfSlot.id == reel.shelf_slot_id)
                )
                slot = slot_result.scalar_one_or_none()
                if slot:
                    slot_code = slot.code or str(slot.slot_on_board)

            ra = ReelAssignment(
                reel_id=r["reel_id"],
                reel_barcode=reel.reel_barcode if reel else None,
                shelf_slot_id=r["shelf_slot_id"],
                slot_code=slot_code,
                reel_qty=reel.quantity if reel else 0,
                original_quantity=reel.original_quantity if reel else 0,
                pick_quantity=r["quantity"],
            )
            reel_assignments.append(ra)

            # 创建料盘锁定记录（独占锁）
            reservation = ReelReservation(
                reel_id=r["reel_id"],
                issue_order_id=order_id,
                issue_detail_id=detail.id,
                reserved_qty=r["quantity"],
                status="active",
                created_at=now,
            )
            db.add(reservation)

        detail.assigned_qty = calc_total
        detail.reel_assignments = json.dumps([ra.model_dump() for ra in reel_assignments])
        detail.status = "completed"  # 全部齐套

    order.status = "assigned"
    order.assigned_at = now
    await db.commit()

    return IssueCalculateResponse(
        issue_order_id=order_id,
        calculated_at=order.assigned_at,
        strategy_used=strategy,
        materials=materials_result,
    )


# ── 储位灯颜色池 ──

# 所有可用的任务颜色（与 rack_api_client.LED_COLORS 映射）
ALL_PICKING_COLORS = ["red", "green", "yellow", "blue", "magenta", "cyan", "white"]

# 颜色名称 → CSS 色值（前端展示用）
COLOR_HEX_MAP = {
    "red": "#ff4d4f",
    "green": "#52c41a",
    "yellow": "#faad14",
    "blue": "#1677ff",
    "magenta": "#eb2f96",
    "cyan": "#13c2c2",
    "white": "#ffffff",
}


async def _get_enabled_picking_colors(db: AsyncSession) -> list:
    """获取系统设置中启用的储位灯任务颜色列表。"""
    from app.models import SystemSetting
    result = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "picking_task_colors")
    )
    row = result.scalar_one_or_none()
    if not row:
        return ALL_PICKING_COLORS[:]
    try:
        colors = json.loads(row)
        if not isinstance(colors, list):
            return ALL_PICKING_COLORS[:]
        # 只保留合法颜色
        return [c for c in colors if c in ALL_PICKING_COLORS]
    except (json.JSONDecodeError, TypeError):
        return ALL_PICKING_COLORS[:]


async def _get_colors_in_use(db: AsyncSession) -> list:
    """获取当前正在被其他发料单占用的储位灯颜色。"""
    result = await db.execute(
        select(IssueOrder.assigned_color).where(
            IssueOrder.status.in_(["picking"]),
            IssueOrder.assigned_color.isnot(None),
        )
    )
    return [row[0] for row in result.fetchall() if row[0]]


async def _pick_available_color(db: AsyncSession) -> Optional[str]:
    """从已启用的颜色池中挑选一个未被占用的颜色。
    
    Returns:
        颜色名称（如 "red"），如果所有颜色都被占用则返回 None。
    """
    enabled = await _get_enabled_picking_colors(db)
    in_use = await _get_colors_in_use(db)
    available = [c for c in enabled if c not in in_use]
    return available[0] if available else None


@router.post("/{order_id}/assign", response_model=IssueAssignResponse)
async def assign_led(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Create LED commands for assigned reels with color from available pool."""
    order_result = await db.execute(select(IssueOrder).where(IssueOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    details_result = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
    )
    details = details_result.scalars().all()

    # ── 第一步：从颜色池中分配一个可用颜色 ──
    assigned_color = await _pick_available_color(db)
    if not assigned_color:
        # 如果所有颜色都被占用，使用绿色作为保底（仍允许并发操作，但颜色可能重复）
        assigned_color = "green"
        logger.warning("No available picking color, fallback to green for order %d", order_id)
    
    # 获取颜色的整数值
    color_int = RackApiClient.LED_COLORS.get(assigned_color, 2)

    # 将颜色写入订单
    order.assigned_color = assigned_color

    commands = []
    shelf_ids = set()

    for detail in details:
        if not detail.reel_assignments:
            continue
        try:
            ra_data = json.loads(detail.reel_assignments)
        except (json.JSONDecodeError, TypeError):
            continue

        for ra in ra_data:
            slot_id = ra.get("shelf_slot_id")
            if not slot_id:
                continue

            slot_result = await db.execute(
                select(ShelfSlot).where(ShelfSlot.id == slot_id).options(
                    selectinload(ShelfSlot.shelf)
                )
            )
            slot = slot_result.scalar_one_or_none()
            if not slot or not slot.shelf:
                continue

            shelf_ids.add(slot.shelf.id)
            cmd = LedCommand(
                shelf_id=slot.shelf.id,
                slot_id=slot_id,
                issue_order_id=order_id,
                material_id=detail.material_id,
                color=assigned_color,  # 使用分配的颜色
                status="queued",
            )
            db.add(cmd)
            commands.append({
                "slot_id": slot_id,
                "material_id": detail.material_id,
                "quantity": ra.get("pick_quantity", 0),
                "color": assigned_color,
            })

    order.status = "picking"
    await db.commit()

    # ── 立即调用 RackApiClient 亮灯 ──
    # 分组按 shelf_id 批量调用
    cells_by_shelf: dict = {}
    for detail in details:
        if not detail.reel_assignments:
            continue
        try:
            ra_data = json.loads(detail.reel_assignments)
        except (json.JSONDecodeError, TypeError):
            continue
        for ra in ra_data:
            slot_id = ra.get("shelf_slot_id")
            if not slot_id:
                continue
            slot = await db.get(ShelfSlot, slot_id)
            if not slot or not slot.cell_id:
                continue
            cells_by_shelf.setdefault(slot.shelf_id, {"cells": []})
            cells_by_shelf[slot.shelf_id]["cells"].append({
                "cellId": slot.cell_id,
                "ledColor": color_int,  # 使用分配的颜色值
                "blink": False,
            })

    # 获取全局 API 配置
    api_config = await get_rack_api_config(db)
    if not api_config:
        logger.warning("Rack API not configured, skip batch light")
    else:
        for shelf_id, info in cells_by_shelf.items():
            try:
                async with RackApiClient(
                    base_url=api_config["base_url"],
                    user_id=api_config["user_id"],
                    client_id=api_config["client_id"],
                ) as client:
                    await client.light_up_cells_batch(
                        cells=info["cells"],
                        voice_text="请取料",
                    )
                logger.info("LED batch light OK: shelf=%d, cells=%d, color=%s",
                            shelf_id, len(info["cells"]), assigned_color)
            except Exception as e:
                logger.error("LED batch light failed: shelf=%d, error=%s",
                             shelf_id, e)
                # 不影响主流程，仅告警

    return IssueAssignResponse(
        assigned=True,
        led_commands_created=len(commands),
        shelf_id=list(shelf_ids)[0] if shelf_ids else 0,
        commands=commands,
        assigned_color=assigned_color,
        message=f"已生成 {len(commands)} 个LED指令，颜色：{assigned_color}",
    )


@router.post("/{order_id}/confirm-pick", response_model=IssueConfirmPickResponse)
async def confirm_pick(
    order_id: int,
    data: IssueConfirmPickRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm pick via PDA scan."""
    order_result = await db.execute(
        select(IssueOrder).where(IssueOrder.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    parsed = await parse_barcode(data.barcode, db)
    if not parsed or not parsed.material_code:
        return IssueConfirmPickResponse(
            status="error",
            picked_qty=0,
            remaining_qty=0,
            all_picked=False,
            cleared_leds=[],
            message="无效的条码格式",
        )

    material_filter = True
    if parsed.matched_material_id is not None:
        material_filter = IssueDetail.material_id == parsed.matched_material_id

    detail_result = await db.execute(
        select(IssueDetail).where(
            IssueDetail.issue_order_id == order_id,
            IssueDetail.status.in_(["pending", "picking", "partial", "completed"]),
            material_filter,
        )
    )
    detail = detail_result.scalar_one_or_none()
    if not detail:
        return IssueConfirmPickResponse(
            status="completed",
            picked_qty=0,
            remaining_qty=0,
            all_picked=False,
            cleared_leds=[],
            message="该物料需求已全部出库",
        )

    # 优先用 reel_id 查找，未提供时通过条码匹配
    pallet = None
    if data.reel_id is not None:
        pallet_result = await db.execute(
            select(InventoryReel).where(InventoryReel.id == data.reel_id)
        )
        pallet = pallet_result.scalar_one_or_none()
    else:
        # 通过条码查找料盘（支持 reel_code / customer_barcode / reel_barcode）
        barcode_str = data.barcode.strip()
        pallet_result = await db.execute(
            select(InventoryReel).where(
                (InventoryReel.reel_code == barcode_str) |
                (InventoryReel.customer_barcode == barcode_str) |
                (InventoryReel.reel_barcode == barcode_str)
            )
        )
        pallet = pallet_result.scalar_one_or_none()

    remaining_need = detail.required_qty - detail.picked_qty
    available = pallet.quantity if pallet else 0
    if available <= 0:
        return IssueConfirmPickResponse(
            status="error",
            picked_qty=0,
            remaining_qty=remaining_need,
            all_picked=False,
            cleared_leds=[],
            message="库存托盘数量不足或需求已满足",
        )

    now = datetime.now()

    pallet_id = pallet.id if pallet else None
    if pallet_id is None:
        return IssueConfirmPickResponse(
            status="error",
            picked_qty=0,
            remaining_qty=remaining_need,
            all_picked=False,
            cleared_leds=[],
            message="未找到匹配的料盘，请检查条码",
        )

    # ── 整盘出库：reel 上的所有数量全部出库（不拆盘）──
    pick_qty = available
    await db.execute(
        update(InventoryReel)
        .where(InventoryReel.id == pallet_id)
        .values(
            status="exhausted",
            quantity=0,
            last_out_time=now,
            last_out_order_id=order_id,
        )
    )

    # ── 释放该料盘的锁定（reservation）──
    await db.execute(
        update(ReelReservation)
        .where(
            ReelReservation.reel_id == pallet_id,
            ReelReservation.issue_order_id == order_id,
            ReelReservation.status == "active",
        )
        .values(status="consumed", released_at=now)
    )

    new_picked = detail.picked_qty + pick_qty
    all_picked = new_picked >= detail.required_qty
    new_status = "completed" if all_picked else "picking"
    await db.execute(
        update(IssueDetail)
        .where(IssueDetail.id == detail.id)
        .values(picked_qty=new_picked, status=new_status)
    )

    txn = Transaction(
        customer_id=order.customer_id,
        material_id=detail.material_id,
        type="out",
        quantity=pick_qty,
        balance_after=0,
        reel_id=pallet_id,
        source_type="issue",
        source_id=order_id,
        operator=data.operator,
        note=f"发料单 #{order.order_no} 确认拣料（整盘出库）",
        created_at=now,
    )
    db.add(txn)

    cleared = []
    if pallet and pallet.shelf_slot_id:
        led_result = await db.execute(
            select(LedCommand).where(
                LedCommand.issue_order_id == order_id,
                LedCommand.slot_id == pallet.shelf_slot_id,
                LedCommand.status == "queued",
            )
        )
        led_commands = led_result.scalars().all()
        for cmd in led_commands:
            cmd.status = "cleared"
            cmd.cleared_at = now
            cleared.append(cmd.slot_id)

        # ── 扫码出库后通过 RackApiClient 灭灯 ──
        slot = await db.get(ShelfSlot, pallet.shelf_slot_id)
        if slot and slot.cell_id:
            api_config = await get_rack_api_config(db)
            if api_config:
                try:
                    async with RackApiClient(
                        base_url=api_config["base_url"],
                        user_id=api_config["user_id"],
                        client_id=api_config["client_id"],
                    ) as client:
                        await client.light_up_cell(cell_id=slot.cell_id, led_color=0)  # 灭灯
                    logger.info("Clear LED OK: cell=%s", slot.cell_id)
                except Exception as e:
                    logger.warning("Clear LED failed: cell=%s, error=%s",
                                   slot.cell_id, e)

    if all_picked:
        all_details = await db.execute(
            select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
        )
        all_done = all(d.status == "completed" for d in all_details.scalars().all())
        if all_done:
            await db.execute(
                update(IssueOrder)
                .where(IssueOrder.id == order_id)
                .values(status="completed", completed_at=now)
            )

    await db.commit()

    return IssueConfirmPickResponse(
        status="ok",
        picked_qty=pick_qty,
        remaining_qty=max(0, detail.required_qty - new_picked),
        all_picked=all_picked,
        cleared_leds=cleared,
        message="出库成功" if not all_picked else "该物料需求已全部出库",
    )


@router.post("/{order_id}/cancel")
async def cancel_issue(order_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel an issue order — release all reel reservations.

    Only orders in 'pending' or 'assigned' status can be cancelled.
    """
    order_result = await db.execute(select(IssueOrder).where(IssueOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    if order.status not in ("pending", "assigned"):
        raise HTTPException(status_code=400, detail=f"当前状态不允许取消（当前: {order.status}），仅待计算或已分配可取消")

    now = datetime.now()

    # 释放所有 active 的 reservation
    await db.execute(
        update(ReelReservation)
        .where(
            ReelReservation.issue_order_id == order_id,
            ReelReservation.status == "active",
        )
        .values(status="released", released_at=now)
    )

    # 清空明细的分配信息
    await db.execute(
        update(IssueDetail)
        .where(IssueDetail.issue_order_id == order_id)
        .values(
            assigned_qty=0,
            reel_assignments=None,
            status="pending",
        )
    )

    # 恢复订单状态并清除颜色
    order.status = "pending"
    order.assigned_at = None
    order.assigned_color = None
    await db.commit()

    return {"status": "ok", "message": f"发料单 #{order.order_no} 已取消"}
