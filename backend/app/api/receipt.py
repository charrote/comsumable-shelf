"""Receipt (inbound) API routes."""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    ReceiptCreate, ReceiptScanRequest, ReceiptScanResponse,
    ReceiptAssignSlotRequest, ReceiptDetailResponse, MaterialCandidate,
    ReprintLabelRequest, ReprintLabelResponse,
    BarcodePreviewResponse, BarcodePreviewItem,
)
from app.utils.database import get_db
from app.utils.barcode import parse_barcode, extract_supplier_info
from app.models import Receipt, ReceiptReel, InventoryReel, MaterialMaster, Shelf, ShelfSlot, Transaction

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
        select(ReceiptReel).where(ReceiptReel.receipt_id == receipt_id)
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
                "customer_material_code": item.customer_material_code,
                "reel_id": item.reel_id,
                "internal_label_printed": item.internal_label_printed == 1,
                "label_printed_at": item.label_printed_at.isoformat() if item.label_printed_at else None,
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
        select(ReceiptReel).where(
            ReceiptReel.id == data.receipt_detail_id,
            ReceiptReel.receipt_id == receipt_id,
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

    # Check slot capacity (use global default if slot has no specific cap)
    pallet_qty = detail.quantity
    effective_cap = slot.max_quantity
    if effective_cap is None:
        from app.models import SystemSetting
        cap_row = await db.execute(
            select(SystemSetting.value).where(SystemSetting.key == "default_slot_capacity")
        )
        raw_global = cap_row.scalar_one_or_none()
        if raw_global and raw_global.strip():
            try:
                effective_cap = float(raw_global)
            except (ValueError, TypeError):
                effective_cap = None
    if effective_cap is not None and pallet_qty > effective_cap:
        raise HTTPException(
            status_code=400,
            detail=f"库存数量 {pallet_qty} 超过储位容量 {effective_cap}",
        )

    # Check slot is not already occupied
    occupied = await db.execute(
        select(InventoryReel).where(
            InventoryReel.shelf_slot_id == data.shelf_slot_id,
            InventoryReel.status == "on_shelf",
        )
    )
    if occupied.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该储位已被占用")

    # Check that the inventory pallet exists
    if not detail.reel_id:
        raise HTTPException(status_code=400, detail="该入库明细尚未关联库存托盘，请先扫码入库")

    # Assign slot to inventory pallet
    await db.execute(
        InventoryReel.__table__.update()
        .where(InventoryReel.id == detail.reel_id)
        .values(shelf_slot_id=data.shelf_slot_id)
    )

    # Also update receipt pallet slot reference
    await db.execute(
        ReceiptReel.__table__.update()
        .where(ReceiptReel.id == detail.id)
        .values(shelf_slot_id=data.shelf_slot_id)
    )

    await db.commit()

    return {
        "status": "ok",
        "message": f"储位已分配: slot #{data.shelf_slot_id}",
        "receipt_detail_id": data.receipt_detail_id,
        "shelf_slot_id": data.shelf_slot_id,
        "reel_id": detail.reel_id,
    }


@router.post("/{receipt_id}/reprint", response_model=ReprintLabelResponse)
async def reprint_label(
    receipt_id: int,
    data: ReprintLabelRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reprint internal label for a specific receipt reel.

    Retrieves the ReceiptReel record and associated material info,
    then sends ZPL to the configured printer.
    """
    # Verify receipt
    receipt_result = await db.execute(
        select(Receipt).where(Receipt.id == receipt_id)
    )
    receipt = receipt_result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")

    # Verify receipt pallet
    rp_result = await db.execute(
        select(ReceiptReel).where(
            ReceiptReel.id == data.receipt_reel_id,
            ReceiptReel.receipt_id == receipt_id,
        )
    )
    rp = rp_result.scalar_one_or_none()
    if not rp:
        raise HTTPException(status_code=404, detail="入库明细不存在")

    # Get material info
    mat_result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == rp.material_id)
    )
    material = mat_result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="关联物料不存在")

    # Get inventory reel for reel_barcode
    inv_result = await db.execute(
        select(InventoryReel).where(InventoryReel.id == rp.reel_id)
    )
    inv = inv_result.scalar_one_or_none()

    # Resolve printer — request param > system setting > config default
    from app.config import settings
    from app.hal.printer import print_label as send_label

    printer_ip = data.printer_ip or settings.LABEL_PRINTER_IP
    printer_port = data.printer_port or settings.LABEL_PRINTER_PORT

    if not printer_ip:
        return ReprintLabelResponse(
            status="error",
            printed=False,
            message="未配置打印机 IP，请在系统设置中配置 LABEL_PRINTER_IP",
            receipt_reel_id=data.receipt_reel_id,
        )

    label_ok = await send_label(
        host=printer_ip,
        port=printer_port or 9100,
        material_code=material.code,
        material_name=material.name,
        quantity=rp.quantity,
        customer_material_code=rp.customer_material_code or "",
        reel_barcode=str(inv.id) if inv else "",
    )

    if label_ok:
        now = datetime.utcnow()
        await db.execute(
            ReceiptReel.__table__.update()
            .where(ReceiptReel.id == rp.id)
            .values(internal_label_printed=1, label_printed_at=now)
        )
        await db.commit()
        return ReprintLabelResponse(
            status="ok",
            printed=True,
            message="标签已重新打印",
            receipt_reel_id=data.receipt_reel_id,
        )
    else:
        return ReprintLabelResponse(
            status="error",
            printed=False,
            message="标签打印失败，请检查打印机连接（{printer_ip}:{printer_port}）",
            receipt_reel_id=data.receipt_reel_id,
        )


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


@router.post("/{receipt_id}/scan-preview", response_model=BarcodePreviewResponse)
async def scan_preview(
    receipt_id: int,
    data: ReceiptScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Scan barcode and preview parsed info before confirming.

    Parses supplier barcode, extracts material code/quantity/batch/date,
    finds matching material candidates, returns all for user confirmation.
    """
    barcode = data.barcode.strip()
    if not barcode:
        return BarcodePreviewResponse(
            barcode=barcode, status="error", confidence=0, material_code="",
            message="条码不能为空"
        )

    # 1) Parse barcode for material match
    parsed = await parse_barcode(barcode, db)
    supplier_info = extract_supplier_info(barcode)

    # 2) Find material candidates
    from app.services.receipt_service import match_material_by_barcode
    match = await match_material_by_barcode(db, barcode, 1)

    candidates = []
    if match.candidates:
        candidates = [
            MaterialCandidate(
                material_id=c["material_id"],
                code=c["code"],
                name=c["name"],
                confidence=c["confidence"],
                extracted_code=c.get("extracted_code", ""),
            )
            for c in match.candidates
        ]

    # 3) Determine quantity from barcode or default
    qty = supplier_info.get("quantity") or data.qty or 1.0

    # 4) Build extracted fields list for display
    extracted_fields = []
    field_map = [
        ("material_code", "物料编码", parsed.material_code or barcode),
        ("quantity", "数量", str(qty)),
        ("unit", "单位", "盘"),
        ("batch_no", "批次号", supplier_info.get("batch_no") or ""),
        ("date_code", "生产日期/周期", supplier_info.get("date_code") or ""),
        ("spec", "规格", supplier_info.get("spec") or ""),
        ("supplier_code", "供应商编码", supplier_info.get("supplier_code") or ""),
    ]
    for key, label, value in field_map:
        if value:
            extracted_fields.append(BarcodePreviewItem(
                field=key, label=label, value=value, editable=True
            ))

    # 5) Get material info
    material_code = parsed.material_code or barcode
    material_name = ""
    material_id = parsed.matched_material_id
    if material_id:
        mat_result = await db.execute(
            select(MaterialMaster).where(MaterialMaster.id == material_id)
        )
        mat = mat_result.scalar_one_or_none()
        if mat:
            material_code = mat.code
            material_name = mat.name

    status = "ok" if match.action == "auto_proceed" else "pending_review" if match.candidates else "new_material"
    if match.action == "new_material":
        status = "new_material"

    return BarcodePreviewResponse(
        barcode=barcode,
        status=status,
        confidence=parsed.confidence or match.confidence,
        material_code=material_code,
        material_name=material_name,
        material_id=material_id,
        quantity=qty,
        unit="盘",
        batch_no=supplier_info.get("batch_no") or "",
        date_code=supplier_info.get("date_code") or "",
        spec=supplier_info.get("spec") or "",
        supplier_code=supplier_info.get("supplier_code") or "",
        extracted_fields=extracted_fields,
        candidates=candidates,
        message=match.message or f"解析完成，置信度 {parsed.confidence:.0%}",
    )


@router.post("/{receipt_id}/scan", response_model=ReceiptScanResponse)
async def scan_receipt(
    receipt_id: int,
    data: ReceiptScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Scan barcode for inbound with intelligent material matching.

    Flow:
      1. Parse barcode → search material master
      2. If exact/high-confidence match → auto proceed (creates InventoryReel + ReceiptReel)
      3. If low-confidence → return candidate list for human review
      4. If no match → return new_material action
      5. Human can re-call with manual_material_id or is_new_material to confirm
    """
    qty = data.qty if data.qty is not None else 1.0
    barcode = data.barcode.strip()
    if not barcode:
        return ReceiptScanResponse(status="error", action="error", message="条码不能为空")

    # ── Verify receipt exists ──
    receipt_result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = receipt_result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")

    # ═══════════════════════════════════════════════════════════════════
    # PATH A: Human review confirmation (second pass)
    # ═══════════════════════════════════════════════════════════════════
    if data.manual_material_id is not None or data.is_new_material:
        return await _handle_human_confirmation(db, receipt_id, data, qty)

    # ═══════════════════════════════════════════════════════════════════
    # PATH B: First scan — auto matching
    # ═══════════════════════════════════════════════════════════════════
    # Check duplicate (behavior controlled by system setting)
    from app.services.duplicate_check import check_duplicate_scan
    dup_check = await check_duplicate_scan(db, barcode, receipt.customer_id)
    if dup_check.action == "block":
        return ReceiptScanResponse(
            status="duplicate",
            action="duplicate",
            duplicate_flag=True,
            reel_id=dup_check.existing_reel_id,
            warning=dup_check.warning,
            message=dup_check.message,
        )
    # warn mode: continue but carry duplicate_flag + warning
    is_duplicate = dup_check.duplicate
    dup_warning = dup_check.warning if is_duplicate else None

    # Match material via intelligent service
    from app.services.receipt_service import match_material_by_barcode
    match = await match_material_by_barcode(db, barcode, receipt.customer_id)

    if match.action == "auto_proceed" and match.material_id:
        # High-confidence → auto create reel
        from app.utils.barcode import extract_supplier_info
        from app.services.receipt_service import finalize_receipt_reel
        supplier_info = extract_supplier_info(barcode)
        result = await finalize_receipt_reel(
            db=db,
            receipt_id=receipt_id,
            material_id=match.material_id,
            barcode=barcode,
            quantity=qty,
            operator=data.operator,
            customer_id=receipt.customer_id,
            customer_material_code=match.customer_material_code,
            customer_barcode=barcode,
            ocr_confidence=match.confidence,
            manual_intervention=0,
            auto_assign_slot=True,
            printer_ip=data.printer_ip,
            printer_port=data.printer_port,
            batch_no=data.batch_no or supplier_info.get("batch_no"),
            date_code=data.date_code or supplier_info.get("date_code"),
        )
        return ReceiptScanResponse(
            status="ok",
            action="first_in",
            reel_id=result["reel_id"],
            assigned_slot=result["assigned_slot"],
            quantity=result["quantity"],
            material_id=match.material_id,
            material_code=match.material_code,
            material_name=match.material_name,
            confidence=match.confidence,
            label_printed=result.get("label_printed", False),
            duplicate_flag=is_duplicate,
            warning=dup_warning,
            message=match.message or f"入库成功，数量 {qty} 盘",
        )

    elif match.action == "pending_review":
        # Low-confidence → return candidates for human review
        return ReceiptScanResponse(
            status="pending_review",
            action="pending_review",
            candidates=[
                MaterialCandidate(
                    material_id=c["material_id"],
                    code=c["code"],
                    name=c["name"],
                    confidence=c["confidence"],
                    extracted_code=c.get("extracted_code", ""),
                )
                for c in match.candidates
            ],
            customer_material_code=match.customer_material_code,
            message=match.message or "匹配置信度过低，请人工选择物料",
        )

    else:
        # No match at all → treat as new material
        return ReceiptScanResponse(
            status="pending_review",
            action="new_material",
            customer_material_code=match.customer_material_code or barcode,
            message=match.message or f"未找到匹配物料，请确认为新料",
        )


async def _handle_human_confirmation(
    db: AsyncSession,
    receipt_id: int,
    data: ReceiptScanRequest,
    qty: float,
) -> ReceiptScanResponse:
    """PATH A: Handle second-pass scan after human review selection.

    Called when the operator has either:
      - Selected an existing material from candidates (manual_material_id)
      - Confirmed this is a new material (is_new_material)
    """
    from app.services.receipt_service import finalize_receipt_reel, auto_create_material
    barcode = data.barcode.strip()

    # Get receipt for customer_id
    receipt_result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = receipt_result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")

    material_id = None
    material_code = ""
    material_name = ""
    confidence = 1.0
    manual_flag = 0

    if data.is_new_material:
        # ── Operator confirmed as new material → auto-create ──
        new_code = (data.new_material_code or barcode).strip()
        new_name = (data.new_material_name or new_code).strip()
        material = await auto_create_material(
            db,
            code=new_code,
            name=new_name,
            customer_id=receipt.customer_id,
            customer_material_code=data.barcode,
        )
        material_id = material.id
        material_code = material.code
        material_name = material.name
        manual_flag = 2  # manual_intervention = confirmed as new
    else:
        # ── Operator selected existing material ──
        material_id = data.manual_material_id
        mat_result = await db.execute(
            select(MaterialMaster).where(MaterialMaster.id == material_id)
        )
        material = mat_result.scalar_one_or_none()
        if not material:
            raise HTTPException(status_code=404, detail="选中的物料不存在")
        material_code = material.code
        material_name = material.name
        manual_flag = 1  # manual_intervention = selected existing

    # Extract batch/date info from barcode
    from app.utils.barcode import extract_supplier_info
    supplier_info = extract_supplier_info(barcode)

    # Create InventoryReel + ReceiptReel
    result = await finalize_receipt_reel(
        db=db,
        receipt_id=receipt_id,
        material_id=material_id,
        barcode=barcode,
        quantity=qty,
        operator=data.operator,
        customer_id=receipt.customer_id,
        customer_material_code=data.barcode,
        customer_barcode=barcode,
        ocr_confidence=confidence,
        manual_intervention=manual_flag,
        auto_assign_slot=True,
        printer_ip=data.printer_ip,
        printer_port=data.printer_port,
        batch_no=data.batch_no or supplier_info.get("batch_no"),
        date_code=data.date_code or supplier_info.get("date_code"),
    )

    action_label = "new_material" if data.is_new_material else "first_in"
    status_label = "ok"
    message = f"入库成功（{'新料' if data.is_new_material else '人工选择'}），数量 {qty} 盘"

    return ReceiptScanResponse(
        status=status_label,
        action=action_label,
        reel_id=result["reel_id"],
        assigned_slot=result["assigned_slot"],
        quantity=result["quantity"],
        material_id=material_id,
        material_code=material_code,
        material_name=material_name,
        confidence=confidence,
        label_printed=result.get("label_printed", False),
        message=message,
    )
