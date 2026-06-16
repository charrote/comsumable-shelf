"""Inventory API routes."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query
from app.schemas import InventoryResponse, TrackingPalletResponse
from app.utils.database import get_db
from app.models import InventoryPallet, MaterialMaster, Shelf, ShelfSlot

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
