"""Material management API routes."""

from typing import Optional, List
from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    MaterialCreate,
    MaterialResponse,
    CustomerMaterialMappingCreate,
    CustomerMaterialMappingUpdate,
    CustomerMaterialMappingResponse,
)
from app.utils.database import get_db
from app.models import MaterialMaster, MaterialCategory, CustomerMaterialMapping, Customer

router = APIRouter(prefix="/materials", tags=["Material Management"])


@router.get("")
async def list_materials(
    customer_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(MaterialMaster)
    if customer_id:
        query = query.where(MaterialMaster.customer_id == customer_id)
    if category_id:
        query = query.where(MaterialMaster.category_id == category_id)
    if keyword:
        kw = f"%{keyword}%"
        query = query.where(
            or_(MaterialMaster.code.ilike(kw), MaterialMaster.name.ilike(kw))
        )
    query = query.where(MaterialMaster.active == 1).order_by(MaterialMaster.code)
    result = await db.execute(query)
    materials = result.scalars().all()
    return [MaterialResponse(
        id=m.id, code=m.code, name=m.name,
        spec=m.spec, unit=m.unit, qty_per_pallet=m.qty_per_pallet,
    ) for m in materials]


@router.post("")
async def create_material(
    data: MaterialCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(MaterialMaster).where(MaterialMaster.code == data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="物料编码已存在")
    material = MaterialMaster(
        code=data.code, name=data.name, spec=data.spec,
        unit=data.unit or "个",
        category_id=data.category_id, qty_per_pallet=data.qty_per_pallet,
        barcode_pattern=data.barcode_pattern, active=1,
        customer_id=1,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return MaterialResponse(
        id=material.id, code=material.code, name=material.name,
        spec=material.spec, unit=material.unit,
        qty_per_pallet=material.qty_per_pallet,
    )


@router.get("/{material_id}")
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == material_id)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="物料不存在")
    return MaterialResponse(
        id=m.id, code=m.code, name=m.name,
        spec=m.spec, unit=m.unit, qty_per_pallet=m.qty_per_pallet,
    )


@router.put("/{material_id}")
async def update_material(
    material_id: int,
    data: MaterialCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == material_id)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="物料不存在")
    m.code = data.code
    m.name = data.name
    m.spec = data.spec
    m.unit = data.unit
    m.category_id = data.category_id
    m.qty_per_pallet = data.qty_per_pallet
    m.barcode_pattern = data.barcode_pattern
    await db.commit()
    await db.refresh(m)
    return MaterialResponse(
        id=m.id, code=m.code, name=m.name,
        spec=m.spec, unit=m.unit, qty_per_pallet=m.qty_per_pallet,
    )


@router.delete("/{material_id}")
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == material_id)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="物料不存在")
    m.active = 0
    await db.commit()
    return {"status": "ok", "message": "物料已禁用"}


# ═══════════════════════════════════════════════
# Customer Material Mapping
# ═══════════════════════════════════════════════

@router.get("/mappings", response_model=List[CustomerMaterialMappingResponse])
async def list_mappings(
    customer_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List customer-material mappings, optionally filtered by customer."""
    query = select(
        CustomerMaterialMapping,
        MaterialMaster.code,
        MaterialMaster.name,
        Customer.name,
    ).join(
        MaterialMaster,
        CustomerMaterialMapping.internal_material_id == MaterialMaster.id,
    ).join(
        Customer,
        CustomerMaterialMapping.customer_id == Customer.id,
    )
    if customer_id:
        query = query.where(CustomerMaterialMapping.customer_id == customer_id)
    query = query.order_by(CustomerMaterialMapping.customer_id, CustomerMaterialMapping.customer_material_code)
    result = await db.execute(query)
    rows = result.all()
    return [
        CustomerMaterialMappingResponse(
            id=row[0].id,
            customer_id=row[0].customer_id,
            customer_material_code=row[0].customer_material_code,
            internal_material_id=row[0].internal_material_id,
            internal_material_code=row[1],
            internal_material_name=row[2],
            customer_name=row[3],
            active=row[0].active,
            created_at=row[0].created_at,
        )
        for row in rows
    ]


@router.post("/mappings", response_model=CustomerMaterialMappingResponse)
async def create_mapping(
    data: CustomerMaterialMappingCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new customer-material mapping."""
    # Verify customer exists
    cust_result = await db.execute(
        select(Customer).where(Customer.id == data.customer_id)
    )
    customer = cust_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # Verify material exists
    mat_result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == data.internal_material_id)
    )
    material = mat_result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")

    # Check duplicate mapping
    dup = await db.execute(
        select(CustomerMaterialMapping).where(
            CustomerMaterialMapping.customer_id == data.customer_id,
            CustomerMaterialMapping.customer_material_code == data.customer_material_code,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"该客户的物料编码 '{data.customer_material_code}' 已存在映射",
        )

    mapping = CustomerMaterialMapping(
        customer_id=data.customer_id,
        customer_material_code=data.customer_material_code,
        internal_material_id=data.internal_material_id,
        active=1,
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)

    return CustomerMaterialMappingResponse(
        id=mapping.id,
        customer_id=mapping.customer_id,
        customer_material_code=mapping.customer_material_code,
        internal_material_id=mapping.internal_material_id,
        internal_material_code=material.code,
        internal_material_name=material.name,
        customer_name=customer.name,
        active=mapping.active,
        created_at=mapping.created_at,
    )


@router.put("/mappings/{mapping_id}", response_model=CustomerMaterialMappingResponse)
async def update_mapping(
    mapping_id: int,
    data: CustomerMaterialMappingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a customer-material mapping."""
    result = await db.execute(
        select(CustomerMaterialMapping).where(CustomerMaterialMapping.id == mapping_id)
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")

    if data.customer_material_code is not None:
        mapping.customer_material_code = data.customer_material_code
    if data.internal_material_id is not None:
        mapping.internal_material_id = data.internal_material_id
    if data.active is not None:
        mapping.active = data.active

    await db.commit()
    await db.refresh(mapping)

    # Fetch joined info for response
    mat_result = await db.execute(
        select(MaterialMaster).where(MaterialMaster.id == mapping.internal_material_id)
    )
    material = mat_result.scalar_one_or_none()
    cust_result = await db.execute(
        select(Customer).where(Customer.id == mapping.customer_id)
    )
    customer = cust_result.scalar_one_or_none()

    return CustomerMaterialMappingResponse(
        id=mapping.id,
        customer_id=mapping.customer_id,
        customer_material_code=mapping.customer_material_code,
        internal_material_id=mapping.internal_material_id,
        internal_material_code=material.code if material else "",
        internal_material_name=material.name if material else "",
        customer_name=customer.name if customer else "",
        active=mapping.active,
        created_at=mapping.created_at,
    )


@router.delete("/mappings/{mapping_id}")
async def delete_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a customer-material mapping."""
    result = await db.execute(
        select(CustomerMaterialMapping).where(CustomerMaterialMapping.id == mapping_id)
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    mapping.active = 0
    await db.commit()
    return {"status": "ok", "message": "映射已禁用"}
