"""XR point counter integration service.

Handles XR point machine data upload and pallet matching.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import XrBatch, InventoryReel, Transaction, MaterialMaster
from app.hal.printer import print_label


async def handle_xr_upload(
    db: AsyncSession,
    reel_id: str,
    counted_qty: float,
    device_id: Optional[str] = None,
    printer_ip: Optional[str] = None,
    printer_port: Optional[int] = None,
) -> dict:
    """Process XR point machine data upload.
    
    Args:
        db: Database session
        reel_id: Reel/barcode ID from XR device
        counted_qty: Counted quantity
        device_id: XR device identifier
        printer_ip: Label printer IP (from browser config)
        printer_port: Label printer port (from browser config)
        
    Returns:
        Dict with success status and action details
    """
    # Find material by reel_id (full barcode as material code)
    result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.code == reel_id)
    )
    material = result.scalar_one_or_none()

    if not material:
        return {
            "success": False,
            "code": -1,
            "message": f"物料 {reel_id} 不存在",
        }

    # Create XR batch record
    xr_batch = XrBatch(
        device_id=device_id,
        material_code=reel_id,
        counted_qty=counted_qty,
        match_key=f"{reel_id}_{datetime.now().isoformat()}",
    )
    db.add(xr_batch)
    await db.commit()
    await db.refresh(xr_batch)

    # Auto-match with tracking pallets
    match_result = await auto_match_xr(
        db,
        xr_batch.id,
        material.id,
        material.customer_id,
    )

    if match_result.get("matched"):
        xr_batch.matched_reel_id = match_result["reel_id"]
        xr_batch.status = "matched"
        await db.commit()

        # Print label after successful count
        if printer_ip and printer_port:
            await print_label(
                host=printer_ip,
                port=printer_port,
                material_code=material.code,
                material_name=material.name,
                quantity=counted_qty,
            )

        return {
            "success": True,
            "code": 0,
            "message": "配对成功",
            "action": "confirm_restock",
            "reel_id": match_result["reel_id"],
        }
    else:
        xr_batch.status = "pending_match"
        await db.commit()

        return {
            "success": False,
            "code": -1,
            "message": "未找到匹配的库存盘，需要人工配对",
            "action": "manual_review",
            "xr_batch_id": xr_batch.id,
        }


async def auto_match_xr(
    db: AsyncSession,
    xr_batch_id: int,
    material_id: int,
    customer_id: int,
) -> dict:
    """Auto-match XR batch with tracking inventory pallets.
    
    Logic: Find tracking pallets for the same material within ±5 seconds
    of the XR scan time.
    """
    window_seconds = settings.XR_MATCH_WINDOW_SECONDS

    # Find tracking pallets for this material
    result = await db.execute(
        select(InventoryReel)
        .where(
            InventoryReel.material_id == material_id,
            InventoryReel.customer_id == customer_id,
            InventoryReel.status == "tracking",
            InventoryReel.quantity > 0,
        )
        .order_by(InventoryReel.last_out_time.desc())
    )
    rows = result.scalars().all()

    # Find the closest match within time window
    now = datetime.now()
    best_match = None
    best_delta = float("inf")

    for pallet in rows:
        last_out_time = pallet.last_out_time
        if last_out_time is None:
            continue
        delta = abs((now - last_out_time).total_seconds())
        if delta <= window_seconds and delta < best_delta:
            best_delta = delta
            best_match = pallet

    if best_match:
        # Update pallet status
        await db.execute(
            update(InventoryReel)
            .where(InventoryReel.id == best_match.id)
            .values(status="ready_restock")
        )
        await db.commit()

        return {
            "matched": True,
            "reel_id": best_match.id,
            "time_delta": best_delta,
        }
    else:
        return {"matched": False}


async def confirm_restock(
    db: AsyncSession,
    reel_id: int,
    shelf_slot_id: int,
    counted_qty: float,
):
    """Confirm restocking a pallet after XR count.
    
    Updates inventory and creates restock transaction.
    """
    # Update pallet
    await db.execute(
        update(InventoryReel)
        .where(InventoryReel.id == pallet_id)
        .values(
            quantity=counted_qty,
            original_quantity=counted_qty,
            status="on_shelf",
            shelf_slot_id=shelf_slot_id,
            last_in_time=datetime.now(),
            inbound_type="restock",
        )
    )

    # Create restock transaction
    pallet = (
        await db.execute(
            select(InventoryReel).where(InventoryReel.id == pallet_id)
        )
    ).scalar_one()

    from app.models import Transaction
    txn = Transaction(
        customer_id=pallet.customer_id,
        material_id=pallet.material_id,
        type="restock",
        quantity=counted_qty,
        balance_after=counted_qty,
        reel_id=pallet_id,
        source_type="xr_transfer",
    )
    db.add(txn)
    await db.commit()
