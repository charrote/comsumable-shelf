"""BOM API routes."""

from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.schemas import (
    BomUploadResponse, BomDetailResponse,
    BomGenerateIssueRequest,
)
from app.utils.database import get_db
from app.models import BomHeader, BomDetail, IssueOrder, IssueDetail
from app.config import settings
import openpyxl
import os

router = APIRouter(prefix="/bom", tags=["BOM"])


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

    return BomUploadResponse(
        bom_header_id=bom_header.id,
        bom_name=bom_header.bom_name,
        parsed=True,
        total_items=total_items,
        unique_materials=len(unique_materials),
        alternates_found=alternates_found,
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
        bom_details.append(BomDetailResponse(
            id=d.id,
            material_code=d.material_code,
            material_name=d.material_code,  # Will be looked up in full implementation
            quantity=d.quantity,
            unit=d.unit,
            alternate_code=d.alternate_code,
            alternate_name=d.alternate_code,
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

    # Create issue order
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    order_no = f"IS-{date_str}-001"
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
        issue_detail = IssueDetail(
            issue_order_id=order.id,
            material_id=1,  # Will be resolved from material_code
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
