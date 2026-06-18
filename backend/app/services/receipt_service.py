"""Receipt (inbound) business service — OCR matching + material auto-create + reel creation."""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, field

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MaterialMaster, InventoryReel, ReceiptReel, Receipt, Shelf, ShelfSlot, CustomerMaterialMapping
from app.utils.barcode import parse_barcode, find_material_candidates
from app.hal.printer import print_label

logger = logging.getLogger(__name__)

# ── Decision thresholds ──────────────────────────────────────────────
EXACT_CONFIDENCE = 1.0
AUTO_PROCEED_THRESHOLD = 0.6  # confidence >= this → auto proceed
CANDIDATE_THRESHOLD = 0.3     # confidence >= this → show as candidate
# ─────────────────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    """Result of material matching from barcode."""
    action: str                     # "auto_proceed" | "pending_review" | "new_material"
    matched: bool
    material_id: Optional[int] = None
    material_code: str = ""
    material_name: str = ""
    confidence: float = 0.0
    customer_material_code: str = ""
    candidates: List[dict] = field(default_factory=list)
    message: str = ""


async def match_material_by_barcode(
    db: AsyncSession,
    barcode: str,
    customer_id: int,
) -> MatchResult:
    """Match a scanned barcode to a material master record.

    Strategy:
      0. (NEW) Check CustomerMaterialMapping for direct code resolution
      1. Exact DB match → auto_proceed
      2. High-confidence fuzzy match → auto_proceed
      3. Low-confidence → return candidates for human review
      4. No match at all → return new_material action
    """
    # Step 0: Extract raw code from barcode for mapping lookup
    parsed = await parse_barcode(barcode, None)
    raw_code = parsed.material_code or barcode

    # Step 0: Check CustomerMaterialMapping first (priority lookup)
    if customer_id:
        mapping_result = await db.execute(
            select(CustomerMaterialMapping).where(
                CustomerMaterialMapping.customer_id == customer_id,
                CustomerMaterialMapping.customer_material_code == raw_code,
                CustomerMaterialMapping.active == 1,
            )
        )
        mapping = mapping_result.scalar_one_or_none()
        if mapping:
            # Resolve to the mapped internal material
            mat_result = await db.execute(
                select(MaterialMaster).where(
                    MaterialMaster.id == mapping.internal_material_id,
                    MaterialMaster.active == 1,
                )
            )
            material = mat_result.scalar_one_or_none()
            if material:
                return MatchResult(
                    action="auto_proceed",
                    matched=True,
                    material_id=material.id,
                    material_code=material.code,
                    material_name=material.name,
                    confidence=1.0,
                    customer_material_code=raw_code,
                    message=f"通过客户映射匹配到物料 {material.code}（客户料号: {raw_code}）",
                )

    # Step 1: Parse barcode into candidates list
    candidates = await find_material_candidates(
        db, barcode, top_n=5, threshold=CANDIDATE_THRESHOLD
    )

    if not candidates:
        # No candidates at all → brand new material
        extracted_code = (await parse_barcode(barcode, None)).material_code
        return MatchResult(
            action="new_material",
            matched=False,
            customer_material_code=extracted_code or barcode,
            confidence=0.0,
            message=f"未找到匹配的物料（条码: {barcode}），请确认为新料",
        )

    best = candidates[0]
    confidence = best["confidence"]

    # Step 2: Exact match or high-confidence → auto proceed
    if confidence >= AUTO_PROCEED_THRESHOLD:
        return MatchResult(
            action="auto_proceed",
            matched=True,
            material_id=best["material_id"],
            material_code=best["code"],
            material_name=best["name"],
            confidence=confidence,
            customer_material_code=best.get("extracted_code", barcode),
            message=f"匹配到物料 {best['code']}（置信度: {confidence:.0%}）",
        )

    # Step 3: Low confidence but some candidates → pending review
    return MatchResult(
        action="pending_review",
        matched=False,
        confidence=confidence,
        customer_material_code=candidates[0].get("extracted_code", barcode),
        candidates=candidates,
        message=f"物料匹配置信度过低（{confidence:.0%}），请人工选择",
    )


async def auto_create_material(
    db: AsyncSession,
    code: str,
    name: Optional[str] = None,
    customer_id: int = 1,
    customer_material_code: Optional[str] = None,
) -> MaterialMaster:
    """Auto-create a new MaterialMaster record when scanning unknown barcode.

    Args:
        code: Material code (from barcode or human input)
        name: Material name (falls back to code if not provided)
        customer_id: Owning customer
        customer_material_code: Original customer material code from label

    Returns:
        The newly created MaterialMaster instance.
    """
    material = MaterialMaster(
        code=code,
        name=name or code,
        customer_id=customer_id,
        unit="盘",
        active=1,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    logger.info("Auto-created MaterialMaster: id=%d code=%s", material.id, code)
    return material


async def finalize_receipt_reel(
    db: AsyncSession,
    receipt_id: int,
    material_id: int,
    barcode: str,
    quantity: float,
    operator: str,
    customer_id: int,
    customer_material_code: str = "",
    customer_barcode: str = "",
    ocr_confidence: float = 0.0,
    manual_intervention: int = 0,
    auto_assign_slot: bool = True,
    printer_ip: Optional[str] = None,
    printer_port: Optional[int] = None,
) -> dict:
    """Create InventoryReel + ReceiptReel records and optionally print label.

    This is the shared finalizer called by all scan paths (auto / human-review / new-material).

    Returns:
        dict with pallet_id, assigned_slot, etc.
    """
    now = datetime.now()

    # ── 1. Create InventoryReel ──
    pallet = InventoryReel(
        material_id=material_id,
        quantity=quantity,
        original_quantity=quantity,
        reel_barcode=barcode,
        customer_code=customer_material_code,
        customer_material_code=customer_material_code,
        customer_barcode=customer_barcode or barcode,
        first_in_time=now,
        last_in_time=now,
        inbound_type="new",
        customer_id=customer_id,
    )
    db.add(pallet)
    await db.commit()
    await db.refresh(pallet)

    # ── 2. Create ReceiptReel ──
    rp = ReceiptReel(
        receipt_id=receipt_id,
        material_id=material_id,
        quantity=quantity,
        barcode=barcode,
        customer_material_code=customer_material_code,
        ocr_confidence=ocr_confidence,
        manual_intervention=manual_intervention,
        operator=operator,
        reel_id=pallet.id,
    )
    db.add(rp)
    await db.commit()

    # ── 3. Auto-assign empty slot (optional) ──
    assigned_slot = None
    if auto_assign_slot:
        assigned_slot = await _auto_assign_slot(db, pallet, quantity)

    # ── 4. Print internal label (optional) ──
    printed = False
    if printer_ip and printer_port:
        mat = await db.execute(
            select(MaterialMaster).where(MaterialMaster.id == material_id)
        )
        material = mat.scalar_one_or_none()
        if material:
            label_ok = await print_label(
                host=printer_ip,
                port=printer_port,
                material_code=material.code,
                material_name=material.name,
                quantity=quantity,
                customer_material_code=customer_material_code,
                reel_barcode=str(pallet.id),
            )
            if label_ok:
                rp.internal_label_printed = 1
                rp.label_printed_at = datetime.now()
                await db.commit()
                printed = True

    return {
        "reel_id": pallet.id,
        "assigned_slot": assigned_slot,
        "quantity": quantity,
        "label_printed": printed,
    }


async def _auto_assign_slot(
    db: AsyncSession,
    pallet: InventoryReel,
    quantity: float,
) -> Optional[int]:
    """Find and assign the first available empty slot.

    Capacity priority (first non-None wins):
        1. ``ShelfSlot.max_quantity`` (per-slot)
        2. ``SystemSetting('default_slot_capacity')`` (global fallback)
    """
    from app.models import SystemSetting

    # Read global default capacity (empty string = no limit)
    cap_row = await db.execute(
        select(SystemSetting.value).where(SystemSetting.key == "default_slot_capacity")
    )
    raw_global = cap_row.scalar_one_or_none()
    global_capacity: Optional[float] = None
    if raw_global and raw_global.strip():
        try:
            global_capacity = float(raw_global)
        except (ValueError, TypeError):
            global_capacity = None

    slot_result = await db.execute(
        select(
            Shelf.id,
            ShelfSlot.id,
            ShelfSlot.global_index,
            ShelfSlot.max_quantity,
        )
        .join(ShelfSlot, Shelf.id == ShelfSlot.shelf_id)
        .where(
            Shelf.active == 1,
            ~ShelfSlot.id.in_(
                select(InventoryReel.shelf_slot_id)
                .where(
                    InventoryReel.status == "on_shelf",
                    InventoryReel.shelf_slot_id.isnot(None),
                )
            ),
        )
        .limit(10)
    )
    rows = slot_result.all()
    for row in rows:
        shelf_id, slot_db_id, global_idx, max_qty = row
        effective_cap = max_qty if max_qty is not None else global_capacity
        if effective_cap is not None and quantity > effective_cap:
            continue
        assigned_slot = global_idx
        await db.execute(
            InventoryReel.__table__.update()
            .where(InventoryReel.id == pallet.id)
            .values(shelf_slot_id=slot_db_id)
        )
        await db.commit()
        return assigned_slot
    return None
