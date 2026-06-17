"""Receipt (inbound) API routes."""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    ReceiptCreate, ReceiptScanRequest, ReceiptScanResponse,
    ReceiptAssignSlotRequest, ReceiptDetailResponse
)
from app.utils.database import get_db
from app.models import Receipt, ReceiptPallet, InventoryPallet, MaterialMaster, Shelf, ShelfSlot, Transaction
from app.utils.barcode import parse_barcode

router = APIRouter(prefix="/receipts", tags=["Receipt/Inbound"])


@router.get("")
async def list_receipts(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List receipt orders."""
    query = select(Receipt).order_by(Receipt.created_at.desc())
    if status:
        query = query.where(Receipt.status == status)
    result = await db.execute(query)
    receipts = result.scalars().all()
    return {
        "data": [
            {
                "id": r.id,
                "receipt_no": r.receipt_no,
                "customer_id": r.customer_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "operator": r.created_by or "",
                "status": r.status,
                "type": r.type,
            }
            for r in receipts
        ]
    }


@router.get("/{receipt_id}")
async def get_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get receipt order detail."""
    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")

    items_result = await db.execute(
        select(ReceiptPallet).where(ReceiptPallet.receipt_id == receipt_id)
    )
    items = items_result.scalars().all()

    return ReceiptDetailResponse(
        id=receipt.id,
        receipt_no=receipt.receipt_no,
        customer_id=receipt.customer_id,
        created_at=receipt.created_at,
        operator=receipt.created_by or "",
        status=receipt.status,
        items=[
            {
                "id": item.id,
                "material_id": item.material_id,
                "quantity": item.quantity,
                "barcode": item.barcode,
                "inventory_pallet_id": item.inventory_pallet_id,
            }
            for item in items
        ],
    )


@router.put("/{receipt_id}/confirm")
async def confirm_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Confirm receipt — transition from draft to confirmed."""
    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")
    if receipt.status != "draft":
        raise HTTPException(status_code=400, detail=f"入库单状态为 {receipt.status}，无法确认")

    await db.execute(
        update(Receipt).where(Receipt.id == receipt_id).values(status="confirmed")
    )
    await db.commit()
    return {"status": "ok", "message": "入库单已确认", "receipt_id": receipt_id}


@router.put("/{receipt_id}/complete")
async def complete_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Complete receipt — transition from confirmed to completed."""
    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")
    if receipt.status != "confirmed":
        raise HTTPException(status_code=400, detail=f"入库单状态为 {receipt.status}，无法完成")

    await db.execute(
        update(Receipt).where(Receipt.id == receipt_id).values(status="completed")
    )
    await db.commit()
    return {"status": "ok", "message": "入库单已完成", "receipt_id": receipt_id}


@router.put("/{receipt_id}/assign-slot")
async def assign_receipt_slot(
    receipt_id: int,
    data: ReceiptAssignSlotRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually assign a shelf slot to a receipt pallet item."""
    # Verify receipt exists
    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")

    # Verify receipt pallet (detail) exists and belongs to this receipt
    detail_result = await db.execute(
        select(ReceiptPallet).where(
            ReceiptPallet.id == data.receipt_detail_id,
            ReceiptPallet.receipt_id == receipt_id,
        )
    )
    detail = detail_result.scalar_one_or_none()
    if not detail:
        raise HTTPException(status_code=404, detail="入库明细不存在")

    # Verify shelf slot exists
    slot_result = await db.execute(
        select(ShelfSlot).where(ShelfSlot.id == data.shelf_slot_id)
    )
    slot = slot_result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="储位不存在")

    # Check slot is not already occupied
    occupied = await db.execute(
        select(InventoryPallet).where(
            InventoryPallet.shelf_slot_id == data.shelf_slot_id,
            InventoryPallet.status == "on_shelf",
        )
    )
    if occupied.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该储位已被占用")

    # Check that the inventory pallet exists
    if not detail.inventory_pallet_id:
        raise HTTPException(status_code=400, detail="该入库明细尚未关联库存托盘，请先扫码入库")

    # Assign slot to inventory pallet
    await db.execute(
        InventoryPallet.__table__.update()
        .where(InventoryPallet.id == detail.inventory_pallet_id)
        .values(shelf_slot_id=data.shelf_slot_id)
    )

    # Also update receipt pallet slot reference
    await db.execute(
        ReceiptPallet.__table__.update()
        .where(ReceiptPallet.id == detail.id)
        .values(shelf_slot_id=data.shelf_slot_id)
    )

    await db.commit()

    return {
        "status": "ok",
        "message": f"储位已分配: slot #{data.shelf_slot_id}",
        "receipt_detail_id": data.receipt_detail_id,
        "shelf_slot_id": data.shelf_slot_id,
        "inventory_pallet_id": detail.inventory_pallet_id,
    }


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
        customer_id=data.customer_id,
        created_by=data.operator,
        status="draft",
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)

    return ReceiptDetailResponse(
        id=receipt.id,
        receipt_no=receipt.receipt_no,
        customer_id=receipt.customer_id,
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
    qty = data.qty if data.qty is not None else 1.0

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
