"""XR point counter API routes."""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from app.schemas import (
    XrUploadRequest, XrUploadResponse,
    XrMatchRequest, XrRestockRequest,
)
from app.utils.database import get_db
from app.services.xr_service import handle_xr_upload, confirm_restock
from app.models import XrBatch

router = APIRouter(prefix="/xr", tags=["XR Point Counter"])


@router.get("")
async def list_xr_batches(
    db: AsyncSession = Depends(get_db),
):
    """List all XR batches."""
    result = await db.execute(
        select(XrBatch).order_by(XrBatch.scanned_at.desc())
    )
    batches = result.scalars().all()
    return [
        {
            "id": b.id,
            "device_id": b.device_id,
            "material_code": b.material_code,
            "counted_qty": b.counted_qty,
            "scanned_at": b.scanned_at.isoformat() if b.scanned_at else None,
            "operator": b.operator,
            "matched_pallet_id": b.matched_pallet_id,
            "status": b.status,
            "match_key": b.match_key,
        }
        for b in batches
    ]


@router.post("/upload", response_model=XrUploadResponse)
async def xr_upload(
    data: XrUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Process XR point counter data upload."""
    result = await handle_xr_upload(
        db,
        reel_id=data.reel_id,
        counted_qty=data.qty,
        device_id=None,
        printer_ip=data.printer_ip,
        printer_port=data.printer_port,
    )
    return XrUploadResponse(**result)


@router.post("/{batch_id}/match")
async def xr_manual_match(
    batch_id: int,
    data: XrMatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually match XR batch with inventory pallet."""
    from app.models import XrBatch
    batch_result = await db.execute(
        select(XrBatch).where(XrBatch.id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="XR批次不存在")

    await db.execute(
        XrBatch.__table__.update()
        .where(XrBatch.id == batch_id)
        .values(
            matched_pallet_id=data.inventory_pallet_id,
            status="matched",
        )
    )
    await db.commit()

    return {"status": "ok", "matched": True}


@router.post("/{batch_id}/confirm-restock")
async def xr_confirm_restock(
    batch_id: int,
    data: XrRestockRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm restock after XR match."""
    batch_result = await db.execute(
        select(XrBatch).where(XrBatch.id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if not batch or batch.matched_pallet_id is None:
        raise HTTPException(status_code=400, detail="XR批次未配对")

    await confirm_restock(
        db,
        pallet_id=batch.matched_pallet_id,
        shelf_slot_id=data.shelf_slot_id,
        counted_qty=batch.counted_qty,
    )

    return {
        "status": "ok",
        "inventory_pallet_id": batch.matched_pallet_id,
        "message": "退库完成, 物料盘已上架至储位 " + str(data.shelf_slot_id),
    }
