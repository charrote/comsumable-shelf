"""Issue (outbound) API routes."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    IssueCalculateRequest, IssueCalculateResponse,
    IssueAssignResponse, IssueConfirmPickRequest, IssueConfirmPickResponse,
    MaterialCalcResult, PalletSelection,
)
from app.utils.database import get_db
from app.models import IssueOrder, IssueDetail, InventoryPallet, LedCommand, ShelfSlot, Shelf, BomHeader, MaterialMaster
from app.services.fifo_service import calculate_fifo_pallets, get_available_qty
from app.utils.barcode import parse_barcode
import json

router = APIRouter(prefix="/issues", tags=["Issue/Outbound"])


@router.get("")
async def list_issues(
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List issue orders."""
    query = select(
        IssueOrder.id,
        IssueOrder.order_no,
        IssueOrder.bom_header_id,
        IssueOrder.customer_id,
        IssueOrder.required_date,
        IssueOrder.status,
        IssueOrder.created_at,
        IssueOrder.assigned_at,
        IssueOrder.completed_at,
        BomHeader.bom_name,
    ).outerjoin(
        BomHeader, IssueOrder.bom_header_id == BomHeader.id
    ).order_by(IssueOrder.created_at.desc())

    if customer_id:
        query = query.where(IssueOrder.customer_id == customer_id)
    if status:
        query = query.where(IssueOrder.status == status)

    result = await db.execute(query)
    rows = result.all()
    issues = []
    for row in rows:
        detail_count = await db.execute(
            select(func.count()).select_from(IssueDetail)
            .where(IssueDetail.issue_order_id == row.id)
        )
        total_materials = detail_count.scalar_one()
        issues.append({
            "id": row.id,
            "order_no": row.order_no,
            "bom_header_id": row.bom_header_id,
            "bom_name": row.bom_name or "",
            "customer_id": row.customer_id,
            "required_date": row.required_date.isoformat() if row.required_date else None,
            "status": row.status,
            "total_materials": total_materials,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return {"data": issues}


@router.get("/{order_id}")
async def get_issue(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get issue order detail."""
    result = await db.execute(
        select(
            IssueOrder.id,
            IssueOrder.order_no,
            IssueOrder.bom_header_id,
            IssueOrder.customer_id,
            IssueOrder.required_date,
            IssueOrder.status,
            IssueOrder.created_at,
            IssueOrder.assigned_at,
            IssueOrder.completed_at,
        ).where(IssueOrder.id == order_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="发料单不存在")

    details_result = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
    )
    details = details_result.scalars().all()

    return {
        "id": row.id,
        "order_no": row.order_no,
        "bom_header_id": row.bom_header_id,
        "customer_id": row.customer_id,
        "required_date": row.required_date.isoformat() if row.required_date else None,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "details": [
            {
                "id": d.id,
                "material_id": d.material_id,
                "required_qty": d.required_qty,
                "picked_qty": d.picked_qty,
                "pallet_ids": d.pallet_ids,
                "pick_strategy": d.pick_strategy,
                "status": d.status,
            }
            for d in details
        ],
    }


@router.post("/{order_id}/calculate", response_model=IssueCalculateResponse)
async def calculate_issue(
    order_id: int,
    data: IssueCalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Calculate FIFO pallet selection for an issue order."""
    order_result = await db.execute(
        select(IssueOrder).where(IssueOrder.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    await db.execute(
        update(IssueOrder).where(IssueOrder.id == order_id).values(status="calculating")
    )
    await db.commit()

    details_result = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
    )
    details = details_result.scalars().all()

    materials = []
    for detail in details:
        available = await get_available_qty(
            db, detail.material_id, order.customer_id
        )
        if available == 0:
            continue

        calc = await calculate_fifo_pallets(
            db, detail.material_id, order.customer_id,
            detail.required_qty, data.strategy
        )

        mat_result = await db.execute(
            select(MaterialMaster).where(MaterialMaster.id == detail.material_id)
        )
        mat = mat_result.scalar_one_or_none()
        material_code = mat.code if mat else ""
        material_name = mat.name if mat else ""

        pallets_selected = []
        for p in calc["pallets"]:
            pallets_selected.append(PalletSelection(**p))

        materials.append(MaterialCalcResult(
            material_id=detail.material_id,
            material_code=material_code,
            material_name=material_name,
            required_qty=detail.required_qty,
            available_qty=available,
            strategy=calc["strategy_used"],
            pallets_selected=pallets_selected,
            total_selected=calc["total_selected"],
            shortage=calc["shortage"],
        ))

    await db.execute(
        update(IssueOrder).where(IssueOrder.id == order_id).values(status="calculated")
    )
    await db.commit()

    return IssueCalculateResponse(
        issue_order_id=order_id,
        calculated_at=datetime.now(),
        strategy_used=calc["strategy_used"],
        materials=materials,
    )


@router.post("/{order_id}/assign", response_model=IssueAssignResponse)
async def assign_led(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Assign LED commands for an issue order."""
    order_result = await db.execute(
        select(IssueOrder).where(IssueOrder.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="发料单不存在")

    details = await db.execute(
        select(IssueDetail).where(IssueDetail.issue_order_id == order_id)
    )
    details = details.scalars().all()

    all_commands = []
    shelf_id = None

    for detail in details:
        if not detail.pallet_ids:
            continue
        pallet_ids = json.loads(detail.pallet_ids)
        if not pallet_ids:
            continue

        for pid in pallet_ids:
            pallet_result = await db.execute(
                select(InventoryPallet).where(InventoryPallet.id == pid)
            )
            pallet = pallet_result.scalar_one_or_none()
            if not pallet or not pallet.shelf_slot_id:
                continue

            slot_id = pallet.shelf_slot_id

            shelf_result = await db.execute(
                select(ShelfSlot.shelf_id).where(ShelfSlot.id == slot_id)
            )
            shelf_row = shelf_result.scalar_one_or_none()
            if not shelf_row:
                continue
            current_shelf_id = shelf_row

            cmd = LedCommand(
                issue_order_id=order_id,
                material_id=pallet.material_id,
                shelf_id=current_shelf_id,
                slot_id=slot_id,
                color="green",
                duration=0,
                status="queued",
            )
            db.add(cmd)
            all_commands.append({
                "command_id": cmd.id,
                "slot_id": slot_id,
                "color": "green",
                "status": "queued",
            })

        if not shelf_id and pallet and pallet.shelf_slot_id:
            slot_row = await db.execute(
                select(ShelfSlot.shelf_id).where(ShelfSlot.id == pallet.shelf_slot_id)
            )
            shelf_id = slot_row.scalar_one()

    if all_commands:
        await db.execute(
            update(IssueOrder).where(IssueOrder.id == order_id).values(
                status="assigned",
                assigned_at=datetime.now(),
            )
        )
        await db.commit()

    return IssueAssignResponse(
        assigned=True,
        led_commands_created=len(all_commands),
        shelf_id=shelf_id or 0,
        commands=all_commands,
        message="亮灯指令已下发至料架",
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

    # Check duplicate pick
    detail_result = await db.execute(
        select(IssueDetail).where(
            IssueDetail.issue_order_id == order_id,
            IssueDetail.status.in_(["pending", "picking"]),
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

    # Look up pallet to get actual quantity
    pallet_result = await db.execute(
        select(InventoryPallet).where(InventoryPallet.id == data.pallet_id)
    )
    pallet = pallet_result.scalar_one_or_none()
    pick_qty = pallet.quantity if pallet else 1.0

    # Update pallet status
    await db.execute(
        update(InventoryPallet)
        .where(InventoryPallet.id == data.pallet_id)
        .values(
            status="exhausted",
            quantity=0,
            last_out_time=datetime.now(),
            last_out_order_id=order_id,
        )
    )

    # Update picked qty
    new_picked = detail.picked_qty + pick_qty
    all_picked = new_picked >= detail.required_qty

    await db.execute(
        update(IssueDetail)
        .where(IssueDetail.id == detail.id)
        .values(picked_qty=new_picked, status="completed" if all_picked else "picking")
    )

    # Clear LED commands for this pallet's slot
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
            cmd.cleared_at = datetime.now()
            cleared.append(cmd.slot_id)

    if all_picked:
        await db.execute(
            update(IssueOrder)
            .where(IssueOrder.id == order_id)
            .values(status="completed", completed_at=datetime.now())
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
