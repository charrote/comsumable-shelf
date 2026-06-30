"""Receipt (inbound) API routes."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, func, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    ReceiptCreate, ReceiptScanRequest, ReceiptScanResponse,
    ReceiptAssignSlotRequest, ReceiptDetailResponse, MaterialCandidate,
    ReprintLabelRequest, ReprintLabelResponse,
    BarcodePreviewResponse, BarcodePreviewItem,
    ManualEntryRequest,
)
from app.utils.database import get_db
from app.utils.barcode import parse_barcode, extract_supplier_info
from app.models import Receipt, ReceiptReel, InventoryReel, MaterialMaster, Shelf, ShelfSlot, Transaction
from app.api.barcode_definition import parse_barcode_with_definitions

router = APIRouter(prefix="/receipts", tags=["Receipt/Inbound"])


@router.get("")
async def list_receipts(
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, description="模糊搜索：收料单号、采购单号"),
    db: AsyncSession = Depends(get_db),
):
    """List receipt orders with item count."""
    query = select(
        Receipt,
        func.count(ReceiptReel.id).label("items_count"),
    ).outerjoin(
        ReceiptReel, ReceiptReel.receipt_id == Receipt.id
    ).group_by(Receipt.id).order_by(Receipt.created_at.desc())

    if status:
        query = query.where(Receipt.status == status)
    if keyword:
        query = query.where(
            Receipt.receipt_no.ilike(f"%{keyword}%")
            | Receipt.purchase_order_no.ilike(f"%{keyword}%")
        )
    result = await db.execute(query)
    rows = result.all()
    return {
        "data": [
            {
                "id": r.Receipt.id,
                "receipt_no": r.Receipt.receipt_no,
                "purchase_order_no": r.Receipt.purchase_order_no or "",
                "customer_id": r.Receipt.customer_id,
                "created_at": r.Receipt.created_at.isoformat() if r.Receipt.created_at else None,
                "operator": r.Receipt.created_by or "",
                "status": r.Receipt.status,
                "type": r.Receipt.type,
                "items_count": r.items_count,
            }
            for r in rows
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
        select(
            ReceiptReel,
            MaterialMaster.code,
            MaterialMaster.name,
            MaterialMaster.unit,
        )
        .join(MaterialMaster, ReceiptReel.material_id == MaterialMaster.id, isouter=True)
        .where(ReceiptReel.receipt_id == receipt_id)
    )
    rows = items_result.all()

    # Get inventory info for each item: reel_code + customer_barcode (original raw barcode)
    reel_ids = [row.ReceiptReel.reel_id for row in rows if row.ReceiptReel.reel_id]
    inv_map = {}  # inv_id -> {reel_code, customer_barcode}
    if reel_ids:
        inv_result = await db.execute(
            select(
                InventoryReel.id,
                InventoryReel.reel_code,
                InventoryReel.customer_barcode,
            ).where(InventoryReel.id.in_(reel_ids))
        )
        for inv_row in inv_result.all():
            inv_map[inv_row[0]] = {
                "reel_code": inv_row[1] or "",
                "customer_barcode": inv_row[2] or "",
            }

    return ReceiptDetailResponse(
        id=receipt.id,
        receipt_no=receipt.receipt_no,
        purchase_order_no=receipt.purchase_order_no or "",
        customer_id=receipt.customer_id,
        created_at=receipt.created_at,
        operator=receipt.created_by or "",
        status=receipt.status,
        items=[
            {
                "id": row.ReceiptReel.id,
                "material_id": row.ReceiptReel.material_id,
                "material_code": row[1] or "",
                "material_name": row[2] or "",
                "material_unit": row[3] or "盘",
                "quantity": row.ReceiptReel.quantity,
                "barcode": row.ReceiptReel.barcode,
                "customer_barcode": inv_map.get(row.ReceiptReel.reel_id, {}).get("customer_barcode", ""),
                "customer_material_code": row.ReceiptReel.customer_material_code,
                "reel_id": row.ReceiptReel.reel_id,
                "reel_code": inv_map.get(row.ReceiptReel.reel_id, {}).get("reel_code", ""),
                "internal_label_printed": row.ReceiptReel.internal_label_printed == 1,
                "label_printed_at": row.ReceiptReel.label_printed_at.isoformat() if row.ReceiptReel.label_printed_at else None,
            }
            for row in rows
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
        purchase_order_no=data.purchase_order_no,
        status="draft",
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)

    return ReceiptDetailResponse(
        id=receipt.id,
        receipt_no=receipt.receipt_no,
        purchase_order_no=receipt.purchase_order_no or "",
        customer_id=receipt.customer_id,
        created_at=receipt.created_at,
        operator=data.operator,
        status=receipt.status,
    )


@router.delete("/{receipt_id}")
async def delete_receipt(
    receipt_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a draft receipt (only draft status allowed)."""
    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")
    if receipt.status != "draft":
        raise HTTPException(status_code=400, detail=f"仅草稿状态的入库单可删除（当前: {receipt.status}）")

    # Delete related receipt_reels first
    await db.execute(sa_delete(ReceiptReel).where(ReceiptReel.receipt_id == receipt_id))
    await db.execute(sa_delete(Receipt).where(Receipt.id == receipt_id))
    await db.commit()
    return {"status": "ok", "message": "入库单已删除", "receipt_id": receipt_id}


@router.post("/batch-delete")
async def batch_delete_receipts(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Batch delete draft receipts."""
    ids: List[int] = data.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要删除的入库单")

    # Verify all are draft
    result = await db.execute(
        select(Receipt).where(Receipt.id.in_(ids))
    )
    receipts = result.scalars().all()
    non_draft = [r.id for r in receipts if r.status != "draft"]
    if non_draft:
        raise HTTPException(
            status_code=400,
            detail=f"以下入库单不是草稿状态，无法删除: {non_draft}"
        )

    for r in receipts:
        await db.execute(sa_delete(ReceiptReel).where(ReceiptReel.receipt_id == r.id))
        await db.execute(sa_delete(Receipt).where(Receipt.id == r.id))
    await db.commit()
    return {"status": "ok", "message": f"已删除 {len(ids)} 张入库单", "deleted_ids": ids}


@router.post("/{receipt_id}/items/cancel")
async def cancel_receipt_items(
    receipt_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Cancel specific receipt reel items (remove from receipt and delete inventory reels).
    Only allowed for draft receipts."""
    receipt_reel_ids: List[int] = data.get("receipt_reel_ids", [])
    if not receipt_reel_ids:
        raise HTTPException(status_code=400, detail="请选择要取消的明细")

    result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")
    if receipt.status != "draft":
        raise HTTPException(status_code=400, detail=f"仅草稿状态可取消入库（当前: {receipt.status}）")

    # Get the ReceiptReel records to find associated InventoryReel IDs
    items_result = await db.execute(
        select(ReceiptReel).where(
            ReceiptReel.id.in_(receipt_reel_ids),
            ReceiptReel.receipt_id == receipt_id,
        )
    )
    items = items_result.scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="未找到要取消的明细")

    reel_ids = [item.reel_id for item in items if item.reel_id]

    # Delete ReceiptReel records
    await db.execute(
        sa_delete(ReceiptReel).where(
            ReceiptReel.id.in_(receipt_reel_ids),
            ReceiptReel.receipt_id == receipt_id,
        )
    )

    # Delete associated InventoryReel records
    if reel_ids:
        await db.execute(
            sa_delete(InventoryReel).where(InventoryReel.id.in_(reel_ids))
        )

    await db.commit()
    return {
        "status": "ok",
        "message": f"已取消 {len(items)} 项入库",
        "cancelled_ids": receipt_reel_ids,
    }


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

    # 获取收料单以获取 customer_id
    receipt_result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = receipt_result.scalar_one_or_none()
    preview_customer_id = receipt.customer_id if receipt else 1

    # ── 0) 重复条码拦截（在条码解析之前拦截） ──
    from app.services.duplicate_check import check_duplicate_scan
    dup_check = await check_duplicate_scan(db, barcode, preview_customer_id)
    if dup_check.action == "block":
        return BarcodePreviewResponse(
            barcode=barcode, status="duplicate", confidence=0, material_code="",
            duplicate_flag=True,
            warning=dup_check.warning,
            message=dup_check.message,
        )
    is_duplicate_preview = dup_check.duplicate
    dup_warning_preview = dup_check.warning if is_duplicate_preview else None

    # ── 1) 先尝试用条码定义解析（固定格式条码优先） ──
    bd_definition, bd_fields = await parse_barcode_with_definitions(db, barcode)
    bd_material_code = bd_fields.get("material_code", "") if bd_fields else ""

    # 2) Parse barcode for material match
    parsed = await parse_barcode(barcode, db)
    supplier_info = extract_supplier_info(barcode)

    # 如果条码定义解析出了物料编码，优先使用
    if bd_material_code:
        parsed.material_code = bd_material_code

    # 3) Find material candidates (use receipt's customer_id)
    # receipt already loaded above
    from app.services.receipt_service import match_material_by_barcode
    search_code = bd_material_code if bd_material_code else barcode
    match = await match_material_by_barcode(db, search_code, preview_customer_id)

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
    # 优先使用条码定义解析出的数量/批次/日期
    bd_batch_no = bd_fields.get("batch_no", "") if bd_fields else ""
    bd_date_code = bd_fields.get("date_code", "") if bd_fields else ""
    bd_qty_str = bd_fields.get("quantity", "") if bd_fields else ""
    qty = supplier_info.get("quantity") or data.qty or 1.0
    if bd_qty_str and qty == 1.0:
        try:
            qty = float(bd_qty_str)
        except (ValueError, TypeError):
            pass

    # 4) Build extracted fields list for display
    extracted_fields = []

    # 优先使用条码定义解析出的字段
    if bd_fields:
        for key, label in [
            ("material_code", "物料编码"),
            ("material_name", "物料名称"),
            ("spec", "规格型号"),
            ("unit", "单位"),
            ("qty_per_pallet", "每盘数量"),
            ("quantity", "数量"),
            ("batch_no", "批次号"),
            ("date_code", "生产日期/周期"),
            ("customer_material_code", "客户物料编码"),
        ]:
            if key in bd_fields and bd_fields[key]:
                extracted_fields.append(BarcodePreviewItem(
                    field=key, label=label, value=bd_fields[key], editable=True
                ))

    # 5) Get material info — 优先使用 match 结果（基于条码定义精准提取的物料编码）
    material_unit = "盘"
    material_spec = ""
    if match.material_id:
        material_id = match.material_id
        material_code = match.material_code
        material_name = match.material_name
        # 从主数据获取规格和单位
        mat_result = await db.execute(
            select(MaterialMaster).where(MaterialMaster.id == material_id)
        )
        mat = mat_result.scalar_one_or_none()
        if mat:
            material_spec = mat.spec or ""
            material_unit = mat.unit or "盘"
    else:
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
                material_spec = mat.spec or ""
                material_unit = mat.unit or "盘"

    # 补充条码定义未覆盖的字段（此时已拿到物料主数据，优先填充）
    existing_keys = {item.field for item in extracted_fields}
    field_map = [
        ("material_code", "物料编码", parsed.material_code or barcode),
        ("quantity", "数量", str(qty)),
        ("batch_no", "批次号", bd_batch_no or supplier_info.get("batch_no") or ""),
        ("date_code", "生产日期/周期", bd_date_code or supplier_info.get("date_code") or ""),
        ("spec", "规格型号", material_spec or supplier_info.get("spec") or ""),
        ("unit", "单位", material_unit),
        ("supplier_code", "供应商编码", supplier_info.get("supplier_code") or ""),
    ]
    # 定义字段已在下拉列表中预先配置，因此定义中的 unit/spec 已在第 4 步写入
    # 后备字段不再重复写入，但确保关键字段不含空值
    for key, label, value in field_map:
        if value and key not in existing_keys:
            extracted_fields.append(BarcodePreviewItem(
                field=key, label=label, value=value, editable=True
            ))

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
        unit=material_unit,
        batch_no=bd_batch_no or supplier_info.get("batch_no") or "",
        date_code=bd_date_code or supplier_info.get("date_code") or "",
        spec=material_spec or supplier_info.get("spec") or "",
        supplier_code=supplier_info.get("supplier_code") or "",
        extracted_fields=extracted_fields,
        candidates=candidates,
        duplicate_flag=is_duplicate_preview,
        warning=dup_warning_preview,
        message=match.message or f"解析完成，置信度 {parsed.confidence:.0%}",
    )


@router.post("/{receipt_id}/manual-entry", response_model=ReceiptScanResponse)
async def manual_entry(
    receipt_id: int,
    data: ManualEntryRequest,
    db: AsyncSession = Depends(get_db),
):
    """手工录入入库 — 针对无条码标签的物料。

    流程：
      1. 生成虚拟条码 MANUAL-{receipt_id}-{seq}
      2. 按物料编码查找或自动创建物料
      3. 创建 InventoryReel + ReceiptReel
    """
    from app.services.receipt_service import finalize_receipt_reel, auto_create_material

    # ── Verify receipt exists ──
    receipt_result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = receipt_result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="入库单不存在")
    if receipt.status != "draft":
        raise HTTPException(status_code=400, detail=f"入库单状态为 {receipt.status}，无法入库")

    # ── Generate virtual barcode: MANUAL-{receipt_id}-{seq} ──
    today_str = datetime.now().strftime("%Y%m%d")
    count_result = await db.execute(
        select(func.count())
        .select_from(ReceiptReel)
        .where(
            ReceiptReel.receipt_id == receipt_id,
            ReceiptReel.barcode.like(f"MANUAL-{receipt_id}-%"),
        )
    )
    seq = (count_result.scalar() or 0) + 1
    virtual_barcode = f"MANUAL-{receipt_id}-{today_str}-{seq:03d}"

    # ── Resolve printer config ──
    from app.config import settings as app_settings
    printer_ip = data.printer_ip or app_settings.LABEL_PRINTER_IP
    printer_port = data.printer_port or app_settings.LABEL_PRINTER_PORT
    if not data.print_label:
        printer_ip = None
        printer_port = None

    # ── Find or auto-create material by code ──
    mat_result = await db.execute(
        select(MaterialMaster).where(
            MaterialMaster.code == data.material_code.strip(),
            MaterialMaster.active == 1,
        )
    )
    material = mat_result.scalar_one_or_none()

    if material:
        material_id = material.id
        material_code = material.code
        material_name = material.name
        manual_flag = 2
        confidence = 1.0
    else:
        # Auto-create new material
        code = data.material_code.strip()
        name = data.material_name.strip() or code
        material = await auto_create_material(
            db,
            code=code,
            name=name,
            customer_id=receipt.customer_id,
            customer_material_code=code,
        )
        material_id = material.id
        material_code = material.code
        material_name = material.name
        manual_flag = 2
        confidence = 1.0

    # ── Create InventoryReel + ReceiptReel ──
    result = await finalize_receipt_reel(
        db=db,
        receipt_id=receipt_id,
        material_id=material_id,
        barcode=virtual_barcode,
        quantity=data.quantity,
        operator=data.operator,
        customer_id=receipt.customer_id,
        customer_material_code=data.supplier_code or material_code,
        customer_barcode=virtual_barcode,
        ocr_confidence=confidence,
        manual_intervention=manual_flag,
        auto_assign_slot=True,
        printer_ip=printer_ip,
        printer_port=printer_port,
        batch_no=data.batch_no,
        date_code=data.date_code,
        scanned_reel_code=data.scanned_reel_code,
    )

    spec_str = data.spec or ""

    return ReceiptScanResponse(
        status="ok",
        action="first_in",
        reel_id=result["reel_id"],
        reel_code=result.get("reel_code", ""),
        assigned_slot=result["assigned_slot"],
        quantity=result["quantity"],
        material_id=material_id,
        material_code=material_code,
        material_name=material_name,
        confidence=confidence,
        label_printed=result.get("label_printed", False),
        message=f"手工录入入库成功，数量 {data.quantity} 盘（虚拟条码: {virtual_barcode}）",
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

    # ── Resolve printer config (print_label flag + system config fallback) ──
    from app.config import settings as app_settings
    printer_ip = data.printer_ip
    printer_port = data.printer_port
    if data.print_label:
        printer_ip = printer_ip or app_settings.LABEL_PRINTER_IP
        printer_port = printer_port or app_settings.LABEL_PRINTER_PORT

    # ── 0) 先尝试用条码定义解析（固定格式条码优先） ──
    bd_definition, bd_fields = await parse_barcode_with_definitions(db, barcode)
    bd_material_code = bd_fields.get("material_code", "") if bd_fields else ""
    bd_batch_no = bd_fields.get("batch_no", "") if bd_fields else ""
    bd_date_code = bd_fields.get("date_code", "") if bd_fields else ""
    bd_qty_str = bd_fields.get("quantity", "") if bd_fields else ""

    # 如果条码定义解析出了数量，覆盖默认值
    if bd_qty_str and qty == 1.0:
        try:
            qty = float(bd_qty_str)
        except (ValueError, TypeError):
            pass

    # ═══════════════════════════════════════════════════════════════════
    # PATH A: Human review confirmation (second pass)
    # ═══════════════════════════════════════════════════════════════════
    if data.manual_material_id is not None or data.is_new_material:
        return await _handle_human_confirmation(db, receipt_id, data, qty, printer_ip, printer_port,
                                                bd_batch_no=bd_batch_no, bd_date_code=bd_date_code)

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

    # Match material via intelligent service (use extracted material_code if available)
    from app.services.receipt_service import match_material_by_barcode
    search_code = bd_material_code if bd_material_code else barcode
    match = await match_material_by_barcode(db, search_code, receipt.customer_id)

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
            printer_ip=printer_ip,
            printer_port=printer_port,
            batch_no=data.batch_no or bd_batch_no or supplier_info.get("batch_no"),
            date_code=data.date_code or bd_date_code or supplier_info.get("date_code"),
            scanned_reel_code=data.scanned_reel_code,
        )
        return ReceiptScanResponse(
            status="ok",
            action="first_in",
            reel_id=result["reel_id"],
            reel_code=result.get("reel_code", ""),
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
    printer_ip: Optional[str] = None,
    printer_port: Optional[int] = None,
    bd_batch_no: str = "",
    bd_date_code: str = "",
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
        printer_ip=printer_ip,
        printer_port=printer_port,
        batch_no=data.batch_no or bd_batch_no or supplier_info.get("batch_no"),
        date_code=data.date_code or bd_date_code or supplier_info.get("date_code"),
        scanned_reel_code=data.scanned_reel_code,
    )

    action_label = "new_material" if data.is_new_material else "first_in"
    status_label = "ok"
    message = f"入库成功（{'新料' if data.is_new_material else '人工选择'}），数量 {qty} 盘"

    return ReceiptScanResponse(
        status=status_label,
        action=action_label,
        reel_id=result["reel_id"],
        reel_code=result.get("reel_code", ""),
        assigned_slot=result["assigned_slot"],
        quantity=result["quantity"],
        material_id=material_id,
        material_code=material_code,
        material_name=material_name,
        confidence=confidence,
        label_printed=result.get("label_printed", False),
        message=message,
    )
