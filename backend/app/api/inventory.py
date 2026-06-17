"""Inventory API routes."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query, HTTPException
from app.schemas import (
    InventoryResponse,
    TrackingPalletResponse,
    InventoryUpdateRequest,
    InventoryUpdateResponse,
)
from app.utils.database import get_db
from app.models import InventoryPallet, MaterialMaster, Shelf, ShelfSlot, Transaction

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("")
async def get_inventory(
    customer_id: Optional[int] = Query(None),
    material_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Query inventory pallets."""
    query = select(
        InventoryPallet,
        MaterialMaster.code.label("material_code"),
        Shelf.code.label("shelf_code"),
    ).join(
        MaterialMaster, InventoryPallet.material_id == MaterialMaster.id
    ).outerjoin(
        ShelfSlot, InventoryPallet.shelf_slot_id == ShelfSlot.id
    ).outerjoin(
        Shelf, ShelfSlot.shelf_id == Shelf.id
    )

    if customer_id:
        query = query.where(InventoryPallet.customer_id == customer_id)
    if material_id:
        query = query.where(InventoryPallet.material_id == material_id)

    result = await db.execute(query)
    rows = result.all()

    pallets = []
    total_qty = 0
    exhausted = 0

    for row in rows:
        pallet = row[0]
        total_qty += pallet.quantity
        if pallet.status == "exhausted":
            exhausted += 1
        pallets.append({
            "pallet_id": pallet.id,
            "material_code": row[1],
            "quantity": pallet.quantity,
            "original_quantity": pallet.original_quantity,
            "shelf_slot_id": pallet.shelf_slot_id,
            "shelf_code": row[2],
            "first_in_time": pallet.first_in_time,
            "last_in_time": pallet.last_in_time,
            "status": pallet.status,
        })

    return InventoryResponse(
        pallets=pallets,
        summary={
            "total_pallets": len(pallets),
            "total_quantity": total_qty,
            "exhausted_pallets": exhausted,
        },
    )


@router.get("/tracking")
async def get_tracking_inventory(
    db: AsyncSession = Depends(get_db),
):
    """Get tracking inventory (returned items waiting for restock)."""
    result = await db.execute(
        select(InventoryPallet, MaterialMaster.code.label("material_code"))
        .join(MaterialMaster, InventoryPallet.material_id == MaterialMaster.id)
        .where(InventoryPallet.status == "tracking")
    )
    rows = result.all()

    pallets = []
    for pallet, code in rows:
        pallets.append(TrackingPalletResponse(
            pallet_id=pallet.id,
            material_code=code,
            quantity=pallet.quantity,
            last_out_time=pallet.last_out_time,
            status=pallet.status,
        ))

    return {"pallets": pallets}


@router.put("/{pallet_id}", response_model=InventoryUpdateResponse)
async def update_inventory_pallet(
    pallet_id: int,
    data: InventoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update inventory pallet fields (quantity, status, shelf_slot_id).

    Supports partial update — only provided fields are modified.
    Records a Transaction entry when quantity or status changes.
    """
    # 1. Verify pallet exists
    result = await db.execute(
        select(InventoryPallet).where(InventoryPallet.id == pallet_id)
    )
    pallet = result.scalar_one_or_none()
    if not pallet:
        raise HTTPException(status_code=404, detail="库存托盘不存在")

    updated_fields = []
    old_quantity = pallet.quantity
    old_status = pallet.status

    # 2. Update quantity (if provided)
    if data.quantity is not None:
        pallet.quantity = data.quantity
        updated_fields.append("quantity")

    # 3. Update status (if provided)
    if data.status is not None:
        valid_statuses = {"on_shelf", "in_use", "tracking", "exhausted"}
        if data.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"无效的状态值: {data.status}，有效值: {', '.join(sorted(valid_statuses))}",
            )
        pallet.status = data.status
        updated_fields.append("status")

    # 4. Update shelf_slot_id (if provided)
    if data.shelf_slot_id is not None:
        # Verify the slot exists
        slot_result = await db.execute(
            select(ShelfSlot).where(ShelfSlot.id == data.shelf_slot_id)
        )
        if not slot_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="储位不存在")

        # Check slot is not already occupied by a DIFFERENT pallet
        occupied = await db.execute(
            select(InventoryPallet).where(
                InventoryPallet.shelf_slot_id == data.shelf_slot_id,
                InventoryPallet.id != pallet_id,
                InventoryPallet.status == "on_shelf",
            )
        )
        if occupied.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该储位已被其它库存托盘占用")
        pallet.shelf_slot_id = data.shelf_slot_id
        updated_fields.append("shelf_slot_id")
    elif data.shelf_slot_id is None and "shelf_slot_id" in data.model_fields_set:
        # Explicitly set to null (unbind from slot)
        pallet.shelf_slot_id = None
        updated_fields.append("shelf_slot_id")

    # 5. Record transaction if quantity or status changed
    if data.quantity is not None or data.status is not None:
        now = datetime.utcnow()
        # Compute quantity diff for transaction
        qty_diff = data.quantity - old_quantity if data.quantity is not None else 0
        txn = Transaction(
            customer_id=pallet.customer_id,
            material_id=pallet.material_id,
            type="reverse" if qty_diff > 0 else "out" if qty_diff < 0 else "reverse",
            quantity=abs(qty_diff) if qty_diff != 0 else 0,
            balance_after=data.quantity if data.quantity is not None else old_quantity,
            inventory_pallet_id=pallet.id,
            source_type="manual_adjust",
            note=data.note or f"手动调整: {', '.join(updated_fields)}",
            created_at=now,
        )
        db.add(txn)

    pallet.updated_at = datetime.utcnow()
    await db.commit()

    return InventoryUpdateResponse(
        status="ok",
        pallet_id=pallet_id,
        updated_fields=updated_fields,
        message=f"库存托盘 #{pallet_id} 已更新: {', '.join(updated_fields) if updated_fields else '无变更'}",
    )
