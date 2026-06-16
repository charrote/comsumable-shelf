"""Issue (outbound) API routes."""

from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from app.schemas import (
    IssueCalculateRequest, IssueCalculateResponse,
    IssueAssignResponse, IssueConfirmPickRequest, IssueConfirmPickResponse,
    MaterialCalcResult, PalletSelection,
)
from app.utils.database import get_db
from app.models import IssueOrder, IssueDetail, InventoryPallet, LedCommand
from app.services.fifo_service import calculate_fifo_pallets, get_available_qty
from app.utils.barcode import parse_barcode
import json

router = APIRouter(prefix="/issues", tags=["Issue/Outbound"])


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

        pallets_selected = []
        for p in calc["pallets"]:
            pallets_selected.append(PalletSelection(**p))

        materials.append(MaterialCalcResult(
            material_id=detail.material_id,
            material_code="",
            material_name="",
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

            slot_result = await db.execute(
                select(InventoryPallet.__table__.c.shelf_slot_id).where(
                    InventoryPallet.id == pid
                )
            )
            slot_id = slot_result.scalar_one()

            cmd = LedCommand(
                issue_order_id=order_id,
                material_id=pallet.material_id,
                shelf_id=pallet.shelf_slot_id,
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
            shelf_result = await db.execute(
                select(InventoryPallet.__table__.c.shelf_id)
                .join(InventoryPallet.__table__.c.shelf_slot_id,
                      InventoryPallet.__table__.c.shelf_slot_id == 1)
            )
            shelf_id = shelf_result.scalar_one()

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

    parsed = parse_barcode(data.barcode)
    if not parsed:
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

    # Update pallet status
    await db.execute(
        update(InventoryPallet)
        .where(InventoryPallet.id == data.pallet_id)
        .values(
            status="exhausted",
            last_out_time=datetime.now(),
            last_out_order_id=order_id,
        )
    )
    await db.commit()

    # Update picked qty
    new_picked = detail.picked_qty + 1.0
    all_picked = new_picked >= detail.required_qty

    await db.execute(
        update(IssueDetail)
        .where(IssueDetail.id == detail.id)
        .values(picked_qty=new_picked, status="completed" if all_picked else "picking")
    )

    if all_picked:
        await db.execute(
            update(IssueOrder)
            .where(IssueOrder.id == order_id)
            .values(status="completed", completed_at=datetime.now())
        )

    await db.commit()

    return IssueConfirmPickResponse(
        status="ok",
        picked_qty=1.0,
        remaining_qty=max(0, detail.required_qty - new_picked),
        all_picked=all_picked,
        cleared_leds=[],
        message="出库成功" if not all_picked else "该物料需求已全部出库",
    )
