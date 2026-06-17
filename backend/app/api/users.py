"""User management API routes."""

from typing import Optional, List
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.utils.database import get_db
from app.models import User
from app.services.auth_service import get_password_hash
from app.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["User Management"])


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    active: Optional[int] = None


@router.get("")
async def list_users(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.username)
    )
    users = result.scalars().all()
    return [UserResponse(
        id=u.id, username=u.username, role=u.role,
        customer_id=u.customer_id, customer_name=u.customer_name,
    ) for u in users]


@router.post("")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(User).where(User.username == data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        role=data.role,
        customer_id=data.customer_id,
        customer_name=data.customer_name,
        active=1,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        customer_id=user.customer_id, customer_name=user.customer_name,
    )


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if data.username is not None:
        user.username = data.username
    if data.password is not None:
        user.password_hash = get_password_hash(data.password)
    if data.role is not None:
        user.role = data.role
    if data.active is not None:
        user.active = data.active
    await db.commit()
    return {"status": "ok", "message": "用户已更新"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.active = 0
    await db.commit()
    return {"status": "ok", "message": "用户已禁用"}
