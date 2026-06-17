"""BOM API routes."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.schemas import (
    BomCreateRequest, BomUpdateRequest, BomListItem, BomDetailResponse,
    BomItemSchema, BomAlternativeSchema, BomUploadResponse, BomGenerateIssueRequest,
)
from app.utils.database import get_db
from app.models import Bom, BomItem, BomAlternative, MaterialMaster, Customer
from app.config import settings
import openpyxl
from openpyxl import Workbook
from fastapi.responses import StreamingResponse
import os
import io
from urllib.parse import quote

router = APIRouter(prefix="/bom", tags=["BOM"])


@router.get("/template")
async def download_bom_template():
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM模板"
    headers = ["产品编码", "物料编码", "数量", "单位", "父级物料编码", "替代物料编码", "替代优先级", "替代百分比"]
    ws.append(headers)
    ws.append(["PROD-001", "MAT-001", 10, "盘", "", "", "", ""])
    ws.append(["PROD-001", "MAT-002", 5, "个", "MAT-001", "", "", ""])
    ws.append(["PROD-001", "MAT-003", 2, "套", "MAT-001", "MAT-004", 1, 100])
    widths = [15, 15, 10, 10, 18, 18, 12, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('BOM导入模板.xlsx')}"},
    )


@router.get("", response_model=List[BomListItem])
async def list_boms(
    customer_id: Optional[int] = None,
    product_code: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Bom).options(
        selectinload(Bom.product_material),
        selectinload(Bom.customer),
    )
    if customer_id is not None:
        query = query.where(Bom.customer_id == customer_id)
    if product_code:
        query = query.join(MaterialMaster, Bom.product_material_id == MaterialMaster.id).where(
            MaterialMaster.code.ilike(f"%{product_code}%")
        )
    if status:
        query = query.where(Bom.status == status)
    query = query.order_by(Bom.created_at.desc())
    result = await db.execute(query)
    boms = result.scalars().all()

    items = []
    for bom in boms:
        item_count_result = await db.execute(
            select(func.count(BomItem.id)).where(BomItem.bom_id == bom.id)
        )
        item_count = item_count_result.scalar() or 0
        items.append(BomListItem(
            id=bom.id,
            customer_id=bom.customer_id,
            customer_name=bom.customer.name if bom.customer else None,
            product_material_id=bom.product_material_id,
            product_code=bom.product_material.code if bom.product_material else None,
            product_name=bom.product_material.name if bom.product_material else None,
            version=bom.version,
            status=bom.status,
            description=bom.description,
            item_count=item_count,
            created_at=bom.created_at,
            updated_at=bom.updated_at,
        ))
    return items


@router.post("", response_model=BomDetailResponse)
async def create_bom(
    data: BomCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(MaterialMaster, data.product_material_id)
    if not product:
        raise HTTPException(status_code=400, detail="产品物料不存在")
    existing = await db.execute(
        select(Bom).where(
            Bom.customer_id == data.customer_id,
            Bom.product_material_id == data.product_material_id,
            Bom.version == data.version,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"版本 {data.version} 已存在")
    bom = Bom(
        customer_id=data.customer_id,
        product_material_id=data.product_material_id,
        version=data.version,
        status="draft",
        description=data.description,
    )
    db.add(bom)
    await db.commit()
    await db.refresh(bom)
    return await _get_bom_detail(db, bom.id)


@router.get("/{bom_id}", response_model=BomDetailResponse)
async def get_bom(bom_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_bom_detail(db, bom_id)


async def _get_bom_detail(db: AsyncSession, bom_id: int) -> BomDetailResponse:
    result = await db.execute(
        select(Bom).where(Bom.id == bom_id).options(
            selectinload(Bom.product_material),
            selectinload(Bom.customer),
        )
    )
    bom = result.scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")

    items_result = await db.execute(
        select(BomItem).where(BomItem.bom_id == bom_id).options(
            selectinload(BomItem.material),
            selectinload(BomItem.alternatives).selectinload(BomAlternative.alternative_material),
        )
    )
    all_items = items_result.scalars().all()

    def build_tree(parent_id: Optional[int]) -> List[BomItemSchema]:
        children = []
        for item in all_items:
            if item.parent_id == parent_id:
                alternatives = [
                    BomAlternativeSchema(
                        id=alt.id,
                        alternative_material_id=alt.alternative_material_id,
                        alternative_material_code=alt.alternative_material.code if alt.alternative_material else None,
                        alternative_material_name=alt.alternative_material.name if alt.alternative_material else None,
                        priority=alt.priority,
                        percentage=alt.percentage,
                    )
                    for alt in sorted(item.alternatives, key=lambda a: a.priority)
                ]
                child = BomItemSchema(
                    id=item.id,
                    parent_id=item.parent_id,
                    material_id=item.material_id,
                    material_code=item.material.code if item.material else None,
                    material_name=item.material.name if item.material else None,
                    material_unit=item.material.unit if item.material else None,
                    quantity=item.quantity,
                    position=item.position,
                    remark=item.remark,
                    alternatives=alternatives,
                    children=build_tree(item.id),
                )
                children.append(child)
        return sorted(children, key=lambda x: x.position)

    return BomDetailResponse(
        id=bom.id,
        customer_id=bom.customer_id,
        customer_name=bom.customer.name if bom.customer else None,
        product_material_id=bom.product_material_id,
        product_code=bom.product_material.code if bom.product_material else None,
        product_name=bom.product_material.name if bom.product_material else None,
        version=bom.version,
        status=bom.status,
        description=bom.description,
        items=build_tree(None),
        created_at=bom.created_at,
        updated_at=bom.updated_at,
    )


@router.put("/{bom_id}", response_model=BomDetailResponse)
async def update_bom(
    bom_id: int,
    data: BomUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    bom = await db.get(Bom, bom_id)
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")
    if data.version is not None:
        bom.version = data.version
    if data.status is not None:
        bom.status = data.status
    if data.description is not None:
        bom.description = data.description
    await db.commit()
    await db.refresh(bom)
    return await _get_bom_detail(db, bom_id)


@router.delete("/{bom_id}")
async def delete_bom(bom_id: int, db: AsyncSession = Depends(get_db)):
    bom = await db.get(Bom, bom_id)
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")
    await db.delete(bom)
    await db.commit()
    return {"message": "BOM已删除"}


@router.post("/{bom_id}/items", response_model=BomItemSchema)
async def add_bom_item(
    bom_id: int,
    data: BomItemSchema,
    db: AsyncSession = Depends(get_db),
):
    bom = await db.get(Bom, bom_id)
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")
    if data.parent_id:
        parent = await db.get(BomItem, data.parent_id)
        if not parent or parent.bom_id != bom_id:
            raise HTTPException(status_code=400, detail="父级物料不存在或不属于此BOM")

    item = BomItem(
        bom_id=bom_id,
        parent_id=data.parent_id,
        material_id=data.material_id,
        quantity=data.quantity,
        position=data.position,
        remark=data.remark,
    )
    db.add(item)
    await db.flush()

    for alt in data.alternatives:
        bom_alt = BomAlternative(
            bom_item_id=item.id,
            alternative_material_id=alt.alternative_material_id,
            priority=alt.priority,
            percentage=alt.percentage,
        )
        db.add(bom_alt)
    await db.commit()
    await db.refresh(item)

    return await _get_item_schema(db, item.id)


async def _get_item_schema(db: AsyncSession, item_id: int) -> BomItemSchema:
    result = await db.execute(
        select(BomItem).where(BomItem.id == item_id).options(
            selectinload(BomItem.material),
            selectinload(BomItem.alternatives).selectinload(BomAlternative.alternative_material),
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="BOM明细不存在")

    alternatives = [
        BomAlternativeSchema(
            id=alt.id,
            alternative_material_id=alt.alternative_material_id,
            alternative_material_code=alt.alternative_material.code if alt.alternative_material else None,
            alternative_material_name=alt.alternative_material.name if alt.alternative_material else None,
            priority=alt.priority,
            percentage=alt.percentage,
        )
        for alt in sorted(item.alternatives, key=lambda a: a.priority)
    ]
    return BomItemSchema(
        id=item.id,
        parent_id=item.parent_id,
        material_id=item.material_id,
        material_code=item.material.code if item.material else None,
        material_name=item.material.name if item.material else None,
        material_unit=item.material.unit if item.material else None,
        quantity=item.quantity,
        position=item.position,
        remark=item.remark,
        alternatives=alternatives,
        children=[],
    )


@router.put("/{bom_id}/items/{item_id}", response_model=BomItemSchema)
async def update_bom_item(
    bom_id: int,
    item_id: int,
    data: BomItemSchema,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(BomItem, item_id)
    if not item or item.bom_id != bom_id:
        raise HTTPException(status_code=404, detail="BOM明细不存在")

    item.material_id = data.material_id
    item.quantity = data.quantity
    item.position = data.position
    item.remark = data.remark
    if data.parent_id:
        parent = await db.get(BomItem, data.parent_id)
        if not parent or parent.bom_id != bom_id:
            raise HTTPException(status_code=400, detail="父级物料不存在")
    item.parent_id = data.parent_id

    await db.execute(delete(BomAlternative).where(BomAlternative.bom_item_id == item_id))
    for alt in data.alternatives:
        bom_alt = BomAlternative(
            bom_item_id=item_id,
            alternative_material_id=alt.alternative_material_id,
            priority=alt.priority,
            percentage=alt.percentage,
        )
        db.add(bom_alt)
    await db.commit()
    return await _get_item_schema(db, item_id)


@router.delete("/{bom_id}/items/{item_id}")
async def delete_bom_item(
    bom_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(BomItem, item_id)
    if not item or item.bom_id != bom_id:
        raise HTTPException(status_code=404, detail="BOM明细不存在")
    await db.delete(item)
    await db.commit()
    return {"message": "BOM明细已删除"}


@router.post("/upload", response_model=BomUploadResponse)
async def upload_bom(
    file: UploadFile = File(...),
    customer_code: str = None,
    version: str = "1.0",
    db: AsyncSession = Depends(get_db),
):
    if not customer_code:
        raise HTTPException(status_code=400, detail="客户编码不能为空")

    customer_result = await db.execute(select(Customer).where(Customer.code == customer_code))
    customer = customer_result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=400, detail="客户不存在")

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "bom")
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb.active

    rows_data = []
    product_codes = set()
    material_codes = set()
    alternates_found = 0

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or len(row) < 3:
            continue
        product_code = str(row[0] or "").strip()
        material_code = str(row[1] or "").strip()
        quantity = float(row[2] or 0)
        unit = str(row[3] or "盘").strip() if len(row) > 3 else "盘"
        parent_code = str(row[4] or "").strip() if len(row) > 4 else ""
        alt_code = str(row[5] or "").strip() if len(row) > 5 else ""
        alt_priority = int(row[6] or 1) if len(row) > 6 else 1
        alt_percentage = float(row[7] or 100) if len(row) > 7 else 100.0

        if not product_code or not material_code or quantity <= 0:
            continue

        product_codes.add(product_code)
        material_codes.add(material_code)
        if alt_code:
            alternates_found += 1
            material_codes.add(alt_code)

        rows_data.append({
            "product_code": product_code,
            "material_code": material_code,
            "quantity": quantity,
            "unit": unit,
            "parent_code": parent_code,
            "alt_code": alt_code,
            "alt_priority": alt_priority,
            "alt_percentage": alt_percentage,
        })

    auto_created = 0
    all_codes = product_codes | material_codes
    for code in all_codes:
        existing = await db.execute(
            select(MaterialMaster).where(
                MaterialMaster.customer_id == customer.id,
                MaterialMaster.code == code,
            )
        )
        if not existing.scalar_one_or_none():
            mat = MaterialMaster(
                customer_id=customer.id,
                code=code,
                name=code,
                unit="盘",
                active=1,
            )
            db.add(mat)
            auto_created += 1
    await db.flush()

    material_cache = {}
    for code in all_codes:
        result = await db.execute(
            select(MaterialMaster).where(
                MaterialMaster.customer_id == customer.id,
                MaterialMaster.code == code,
            )
        )
        mat = result.scalar_one_or_none()
        if mat:
            material_cache[code] = mat

    created_boms = {}
    item_code_to_id = {}

    for product_code in product_codes:
        product_mat = material_cache.get(product_code)
        if not product_mat:
            continue
        existing = await db.execute(
            select(Bom).where(
                Bom.customer_id == customer.id,
                Bom.product_material_id == product_mat.id,
                Bom.version == version,
            )
        )
        bom = existing.scalar_one_or_none()
        if not bom:
            bom = Bom(
                customer_id=customer.id,
                product_material_id=product_mat.id,
                version=version,
                status="draft",
            )
            db.add(bom)
            await db.flush()
        created_boms[product_code] = bom

    for row in rows_data:
        product_code = row["product_code"]
        bom = created_boms.get(product_code)
        if not bom:
            continue

        material = material_cache.get(row["material_code"])
        if not material:
            continue

        parent_id = None
        if row["parent_code"]:
            parent_id = item_code_to_id.get((product_code, row["parent_code"]))

        item = BomItem(
            bom_id=bom.id,
            parent_id=parent_id,
            material_id=material.id,
            quantity=row["quantity"],
            position=0,
        )
        db.add(item)
        await db.flush()
        item_code_to_id[(product_code, row["material_code"])] = item.id

        if row["alt_code"]:
            alt_material = material_cache.get(row["alt_code"])
            if alt_material:
                bom_alt = BomAlternative(
                    bom_item_id=item.id,
                    alternative_material_id=alt_material.id,
                    priority=row["alt_priority"],
                    percentage=row["alt_percentage"],
                )
                db.add(bom_alt)

    await db.commit()

    first_product = next(iter(product_codes), "")
    first_bom = created_boms.get(first_product)

    return BomUploadResponse(
        bom_id=first_bom.id if first_bom else 0,
        product_code=first_product,
        version=version,
        parsed=True,
        total_items=len(rows_data),
        unique_materials=len(material_codes),
        alternates_found=alternates_found,
        auto_created_count=auto_created,
    )


@router.post("/{bom_id}/generate-issue")
async def generate_issue_from_bom(
    bom_id: int,
    data: BomGenerateIssueRequest,
    db: AsyncSession = Depends(get_db),
):
    bom = await db.get(Bom, bom_id)
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")
    return {"message": "功能开发中", "bom_id": bom_id}
