"""BOM API routes."""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.schemas import (
    BomUploadResponse, BomDetailResponse, BomUpdateRequest, BomListItem,
    BomGenerateIssueRequest,
)
from app.utils.database import get_db
from app.models import BomHeader, BomDetail, IssueOrder, IssueDetail, MaterialMaster
from app.config import settings
from app.services.bom_service import ensure_materials_exist
import openpyxl
import os

router = APIRouter(prefix="/bom", tags=["BOM"])


@router.get("")
async def list_boms(
    customer_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all BOM headers with item counts."""
    query = select(
        BomHeader.id,
        BomHeader.bom_name,
        BomHeader.product_code,
        BomHeader.customer_id,
        BomHeader.parsed,
        BomHeader.parsed_at,
        BomHeader.created_at,
        func.count(BomDetail.id).label("total_items"),
    ).outerjoin(
        BomDetail, BomHeader.id == BomDetail.bom_header_id
    ).group_by(BomHeader.id).order_by(BomHeader.created_at.desc())

    if customer_id is not None:
        query = query.where(BomHeader.customer_id == customer_id)

    result = await db.execute(query)
    rows = result.all()

    return {
        "data": [
            BomListItem(
                id=row.id,
                bom_name=row.bom_name,
                product_code=row.product_code,
                customer_id=row.customer_id,
                total_items=row.total_items or 0,
                parsed=row.parsed,
                parsed_at=row.parsed_at,
                created_at=row.created_at,
            )
            for row in rows
        ]
    }


@router.put("/{bom_id}")
async def update_bom(
    bom_id: int,
    data: BomUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update BOM header properties."""
    result = await db.execute(select(BomHeader).where(BomHeader.id == bom_id))
    bom = result.scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")

    update_values = {}
    if data.bom_name is not None:
        update_values["bom_name"] = data.bom_name
    if data.product_code is not None:
        update_values["product_code"] = data.product_code
    if data.customer_id is not None:
        update_values["customer_id"] = data.customer_id

    if update_values:
        await db.execute(
            update(BomHeader).where(BomHeader.id == bom_id).values(**update_values)
        )
        await db.commit()

    return {"status": "ok", "message": "BOM已更新", "bom_id": bom_id}


@router.delete("/{bom_id}")
async def delete_bom(
    bom_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a BOM header and its details."""
    result = await db.execute(select(BomHeader).where(BomHeader.id == bom_id))
    bom = result.scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")

    # Check if BOM has related issue orders
    issue_count = await db.execute(
        select(func.count()).select_from(IssueOrder)
        .where(IssueOrder.bom_header_id == bom_id)
    )
    if issue_count.scalar_one() > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该BOM已关联 {issue_count.scalar_one()} 个发料单，无法删除。请先删除关联的发料单。"
        )

    # Delete details first, then header
    await db.execute(delete(BomDetail).where(BomDetail.bom_header_id == bom_id))
    await db.execute(delete(BomHeader).where(BomHeader.id == bom_id))
    await db.commit()

    return {"status": "ok", "message": "BOM已删除", "bom_id": bom_id}


@router.post("/upload")
async def upload_bom(
    file: UploadFile = File(...),
    customer_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload and parse BOM Excel file."""
    # Save file temporarily
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "bom")
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, file.filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Parse Excel
    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb.active

    bom_header = BomHeader(
        customer_id=customer_id,
        bom_name=file.filename,
        file_path=file_path,
        parsed=1,
        parsed_at=datetime.now(),
    )
    db.add(bom_header)
    await db.commit()
    await db.refresh(bom_header)

    total_items = 0
    unique_materials = set()
    alternates_found = 0

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Skip header row
        if len(row) < 3:
            continue
        try:
            product_code = str(row[0] or "")
            material_code = str(row[1] or "")
            quantity = float(row[2] or 0)
            unit = str(row[3] or "盘") if len(row) > 3 else "盘"
            alternate_code = str(row[4] or "") if len(row) > 4 else None

            if not material_code:
                continue

            bom_detail = BomDetail(
                bom_header_id=bom_header.id,
                material_code=material_code,
                quantity=quantity,
                unit=unit,
                alternate_code=alternate_code,
                priority=row_idx - 1,
            )
            db.add(bom_detail)
            total_items += 1
            unique_materials.add(material_code)
            if alternate_code:
                alternates_found += 1
        except (ValueError, IndexError):
            continue

    await db.commit()

    # ── Auto-create non-existing materials ──
    auto_created = 0
    if settings.BOM_AUTO_CREATE_MATERIAL and customer_id:
        auto_created = await ensure_materials_exist(
            db, unique_materials, customer_id
        )

    return BomUploadResponse(
        bom_header_id=bom_header.id,
        bom_name=bom_header.bom_name,
        parsed=True,
        total_items=total_items,
        unique_materials=len(unique_materials),
        alternates_found=alternates_found,
        auto_created_count=auto_created,
    )


@router.get("/{bom_id}")
async def get_bom(
    bom_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get BOM details."""
    header_result = await db.execute(
        select(BomHeader).where(BomHeader.id == bom_id)
    )
    header = header_result.scalar_one_or_none()
    if not header:
        raise HTTPException(status_code=404, detail="BOM不存在")

    details_result = await db.execute(
        select(BomDetail).where(BomDetail.bom_header_id == bom_id)
        .order_by(BomDetail.priority)
    )
    details = details_result.scalars().all()

    bom_details = []
    for d in details:
        mat_result = await db.execute(
            select(MaterialMaster.name).where(MaterialMaster.code == d.material_code)
        )
        mat_name = mat_result.scalar_one_or_none() or d.material_code
        alt_name = d.alternate_code
        if d.alternate_code:
            alt_result = await db.execute(
                select(MaterialMaster.name).where(MaterialMaster.code == d.alternate_code)
            )
            alt_name = alt_result.scalar_one_or_none() or d.alternate_code
        bom_details.append(BomDetailResponse(
            id=d.id,
            material_code=d.material_code,
            material_name=mat_name,
            quantity=d.quantity,
            unit=d.unit,
            alternate_code=d.alternate_code,
            alternate_name=alt_name,
        ))

    return {
        "header": {
            "id": header.id,
            "bom_name": header.bom_name,
            "product_code": header.product_code,
        },
        "details": bom_details,
    }


@router.post("/{bom_id}/generate-issue")
async def generate_issue(
    bom_id: int,
    data: BomGenerateIssueRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate issue order from BOM."""
    bom_result = await db.execute(
        select(BomHeader).where(BomHeader.id == bom_id)
    )
    bom = bom_result.scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")

    required_date = None
    if data.required_date:
        from datetime import datetime
        required_date = datetime.fromisoformat(data.required_date)

    # Create issue order with sequential numbering
    date_str = datetime.now().strftime("%Y%m%d")
    seq_result = await db.execute(
        select(func.coalesce(func.max(IssueOrder.order_no), "0"))
        .where(IssueOrder.order_no.like(f"IS-{date_str}-%"))
    )
    seq_val = seq_result.scalar_one()
    if seq_val and seq_val != "0":
        last_seq = int(seq_val.split("-")[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1
    order_no = f"IS-{date_str}-{new_seq:03d}"
    order = IssueOrder(
        order_no=order_no,
        bom_header_id=bom_id,
        customer_id=data.customer_id,
        required_date=required_date,
        status="pending",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Create issue details from BOM
    details_result = await db.execute(
        select(BomDetail).where(BomDetail.bom_header_id == bom_id)
    )
    details = details_result.scalars().all()

    for d in details:
        mat_result = await db.execute(
            select(MaterialMaster.id).where(MaterialMaster.code == d.material_code)
        )
        mat_id = mat_result.scalar_one_or_none()
        if mat_id is None:
            continue
        issue_detail = IssueDetail(
            issue_order_id=order.id,
            material_id=mat_id,
            required_qty=d.quantity,
            status="pending",
        )
        db.add(issue_detail)

    await db.commit()

    return {
        "issue_order_id": order.id,
        "order_no": order.order_no,
        "total_materials": len(details),
        "status": "pending",
    }
