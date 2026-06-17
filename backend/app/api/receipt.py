"""Receipt (inbound) API routes."""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from app.schemas import (
    ReceiptCreate, ReceiptScanRequest, ReceiptScanResponse,
    ReceiptAssignSlotRequest, ReceiptDetailResponse
)
from app.utils.database import get_db
from app.models import Receipt, ReceiptPallet, InventoryPallet, MaterialMaster, Shelf, ShelfSlot
from app.utils.barcode import parse_barcode

router = APIRouter(prefix="/receipts", tags=["Receipt/Inbound"])


@router.post("", response_model=ReceiptDetailResponse)
async def create_receipt(
    data: ReceiptCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new receipt order."""
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    seq = (
        await db.execute(
            select(func.coalesce(func.max(Receipt.receipt_no), "0"))
            .where(Receipt.receipt_no.like(f"RC-{date_str}-%"))
        )
    ).scalar_one()
    if seq and seq != "0":
        last_seq = int(seq.split("-")[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1
    receipt_no = f"RC-{date_str}-{new_seq:03d}"

    receipt = Receipt(
        receipt_no=receipt_no,
        type=data.type,
        created_by=data.operator,
        status="draft",
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)

    return ReceiptDetailResponse(
        id=receipt.id,
        receipt_no=receipt.receipt_no,
        customer_id=0,
        created_at=receipt.created_at,
        operator=data.operator,
        status=receipt.status,
    )


@router.post("/{receipt_id}/scan", response_model=ReceiptScanResponse)
async def scan_receipt(
    receipt_id: int,
    data: ReceiptScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Scan barcode for inbound."""
    barcode = data.barcode
    parsed = await parse_barcode(barcode, db)
    if not parsed or not parsed.material_code:
        return ReceiptScanResponse(
            status="error",
            action="error",
            message="无效的条码格式",
        )
    material_code = parsed.material_code
    qty = 50.0  # default quantity

    # Find material
    result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.code == material_code)
    )
    material = result.scalar_one_or_none()
    if not material:
        return ReceiptScanResponse(
            status="error",
            action="error",
            message=f"物料 {material_code} 不存在",
        )

    # Check for duplicate
    batch_val = parsed.extra.get("batch", "") if parsed.extra else ""
    existing = await db.execute(
        select(InventoryPallet).where(
            InventoryPallet.material_id == material.id,
            InventoryPallet.customer_code == batch_val,
            InventoryPallet.status.in_(["on_shelf", "tracking"]),
        )
    )
    dup = existing.scalar_one_or_none()
    if dup:
        return ReceiptScanResponse(
            status="duplicate",
            action="duplicate",
            duplicate_flag=True,
            matched_pallet_id=dup.id,
            warning="该编码已存在",
            message="该编码已存在, 库存盘 #" + str(dup.id) + ", 已拦截",
        )

    # Create inventory pallet
    now = datetime.now()
    pallet = InventoryPallet(
        material_id=material.id,
        quantity=qty,
        original_quantity=qty,
        pallet_barcode=barcode,
        customer_code=batch_val,
        first_in_time=now,
        last_in_time=now,
        inbound_type="new",
        customer_id=material.customer_id,
    )
    db.add(pallet)
    await db.commit()
    await db.refresh(pallet)

    # Create receipt pallet record
    rp = ReceiptPallet(
        receipt_id=receipt_id,
        material_id=material.id,
        quantity=qty,
        barcode=barcode,
        operator=data.operator,
        inventory_pallet_id=pallet.id,
    )
    db.add(rp)
    await db.commit()

    # Auto-assign slot if available
    assigned_slot = None
    slot_result = await db.execute(
        select(
            Shelf.id,
            ShelfSlot.id,
            ShelfSlot.global_index,
        )
        .join(ShelfSlot, Shelf.id == ShelfSlot.shelf_id)
        .where(
            Shelf.active == 1,
            ~ShelfSlot.id.in_(
                select(InventoryPallet.shelf_slot_id)
                .where(InventoryPallet.status == "on_shelf")
            ),
        )
        .limit(1)
    )
    row = slot_result.first()
    if row:
        assigned_slot = row[2]
        await db.execute(
            InventoryPallet.__table__.update()
            .where(InventoryPallet.id == pallet.id)
            .values(shelf_slot_id=row[1])
        )
        await db.commit()

    return ReceiptScanResponse(
        status="ok",
        action="first_in",
        inventory_pallet_id=pallet.id,
        assigned_slot=assigned_slot,
        duplicate_flag=False,
        message=f"入库成功, 数量 {qty} 盘",
    )
