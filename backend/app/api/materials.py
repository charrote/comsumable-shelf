"""Material management API routes."""

from typing import Optional, List
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import MaterialCreate, MaterialResponse
from app.utils.database import get_db
from app.models import MaterialMaster, MaterialCategory

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
