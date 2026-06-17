"""Customer management API routes."""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.utils.database import get_db
from app.models import Customer

router = APIRouter(prefix="/customers", tags=["Customer Management"])


class CustomerCreate(BaseModel):
    name: str
    code: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None


class CustomerResponse(BaseModel):
    id: int
    name: str
    code: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    active: int = 1


@router.get("", response_model=List[CustomerResponse])
async def list_customers(db: AsyncSession = Depends(get_db)):
    """List all customers."""
    result = await db.execute(select(Customer).where(Customer.active == 1).order_by(Customer.id))
    customers = result.scalars().all()
    return [CustomerResponse(
        id=c.id, name=c.name, code=c.code,
        contact_name=c.contact_name, contact_phone=c.contact_phone,
        address=c.address, active=c.active,
    ) for c in customers]


@router.post("", response_model=CustomerResponse)
async def create_customer(data: CustomerCreate, db: AsyncSession = Depends(get_db)):
    """Create a new customer."""
    existing = await db.execute(select(Customer).where(Customer.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="客户编码已存在")

    customer = Customer(
        name=data.name,
        code=data.code,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        address=data.address,
        active=1,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse(
        id=customer.id, name=customer.name, code=customer.code,
        contact_name=customer.contact_name, contact_phone=customer.contact_phone,
        address=customer.address, active=customer.active,
    )


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
    """Update a customer."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    if data.code != customer.code:
        existing = await db.execute(select(Customer).where(Customer.code == data.code))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="客户编码已存在")

    customer.name = data.name
    customer.code = data.code
    customer.contact_name = data.contact_name
    customer.contact_phone = data.contact_phone
    customer.address = data.address
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse(
        id=customer.id, name=customer.name, code=customer.code,
        contact_name=customer.contact_name, contact_phone=customer.contact_phone,
        address=customer.address, active=customer.active,
    )


@router.delete("/{customer_id}")
async def delete_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    """Soft delete a customer."""
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    customer.active = 0
    await db.commit()
    return {"status": "ok", "message": "客户已删除", "customer_id": customer_id}