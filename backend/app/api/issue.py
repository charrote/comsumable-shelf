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
    Bom, BomItem, MaterialMaster, Transaction, Customer,
)
from app.services.fifo_service import calculate_fifo_pallets, get_available_qty
from app.utils.barcode import parse_barcode
import json

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
    """Calculate FIFO reel assignment for all materials in the issue order."""
    order_result = await db.execute(select(IssueOrder).where(IssueOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    details_result = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
    )
    details = details_result.scalars().all()

    strategy = data.strategy
    if strategy == "config":
        from app.config import settings
        strategy = settings.FIFO_STRATEGY

    materials_result = []

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

        # calc is a dict with keys: reels, total_selected, shortage
        calc_reels = calc.get('reels', []) if isinstance(calc, dict) else getattr(calc, 'reels', [])
        calc_total = calc.get('total_selected', 0) if isinstance(calc, dict) else getattr(calc, 'total_selected', 0)

        reel_selections = [
            ReelSelection(
                reel_id=r["reel_id"],
                quantity=r["quantity"],
                last_in_time=r["last_in_time"],
                shelf_slot_id=r["shelf_slot_id"],
            )
            for r in calc_reels
        ]

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
                    slot_code = f"S{slot.shelf_id}-{slot.side}{slot.slot_on_board}"

            reel_assignments.append(ReelAssignment(
                reel_id=r["reel_id"],
                reel_barcode=reel.reel_barcode if reel else None,
                shelf_slot_id=r["shelf_slot_id"],
                slot_code=slot_code,
                reel_qty=reel.quantity if reel else 0,
                original_quantity=reel.original_quantity if reel else 0,
                pick_quantity=r["quantity"],
            ))

        detail.assigned_qty = calc_total
        detail.reel_assignments = json.dumps([ra.model_dump() for ra in reel_assignments])
        detail.status = "completed" if calc_total >= detail.required_qty else "partial"

        materials_result.append(MaterialCalcResult(
            material_id=detail.material_id,
            material_code=mat.code,
            material_name=mat.name,
            required_qty=detail.required_qty,
            available_qty=available,
            strategy=strategy,
            reels_selected=reel_selections,
            total_selected=calc_total,
            shortage=max(0, detail.required_qty - calc_total),
        ))

    order.status = "assigned"
    order.assigned_at = datetime.now()
    await db.commit()

    return IssueCalculateResponse(
        issue_order_id=order_id,
        calculated_at=order.assigned_at,
        strategy_used=strategy,
        materials=materials_result,
    )


@router.post("/{order_id}/assign", response_model=IssueAssignResponse)
async def assign_led(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Create LED commands for assigned reels."""
    order_result = await db.execute(select(IssueOrder).where(IssueOrder.id == order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    details_result = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
    )
    details = details_result.scalars().all()

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
                status="queued",
            )
            db.add(cmd)
            commands.append({
                "slot_id": slot_id,
                "material_id": detail.material_id,
                "quantity": ra.get("pick_quantity", 0),
            })

    order.status = "picking"
    await db.commit()

    return IssueAssignResponse(
        assigned=True,
        led_commands_created=len(commands),
        shelf_id=list(shelf_ids)[0] if shelf_ids else 0,
        commands=commands,
        message=f"已生成 {len(commands)} 个LED指令",
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

    pallet_result = await db.execute(
        select(InventoryReel).where(InventoryReel.id == data.reel_id)
    )
    pallet = pallet_result.scalar_one_or_none()

    remaining_need = detail.required_qty - detail.picked_qty
    available = pallet.quantity if pallet else 0
    pick_qty = min(available, remaining_need)
    if pick_qty <= 0:
        return IssueConfirmPickResponse(
            status="error",
            picked_qty=0,
            remaining_qty=remaining_need,
            all_picked=False,
            cleared_leds=[],
            message="库存托盘数量不足或需求已满足",
        )

    now = datetime.now()

    if pick_qty < available:
        await db.execute(
            update(InventoryReel)
            .where(InventoryReel.id == data.reel_id)
            .values(
                quantity=available - pick_qty,
                last_out_time=now,
                last_out_order_id=order_id,
            )
        )
    else:
        await db.execute(
            update(InventoryReel)
            .where(InventoryReel.id == data.reel_id)
            .values(
                status="exhausted",
                quantity=0,
                last_out_time=now,
                last_out_order_id=order_id,
            )
        )

    new_picked = detail.picked_qty + pick_qty
    all_picked = new_picked >= detail.required_qty
    await db.execute(
        update(IssueDetail)
        .where(IssueDetail.id == detail.id)
        .values(picked_qty=new_picked, status="completed" if all_picked else "picking")
    )

    txn = Transaction(
        customer_id=order.customer_id,
        material_id=detail.material_id,
        type="out",
        quantity=pick_qty,
        balance_after=available - pick_qty,
        reel_id=pallet.id if pallet else None,
        source_type="issue",
        source_id=order_id,
        operator=data.operator,
        note=f"发料单 #{order.order_no} 确认拣料",
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
