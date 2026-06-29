"""User management API routes."""

from typing import Optional, List
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.utils.database import get_db
from app.models import User, Role
from app.services.auth_service import get_password_hash
from app.schemas import UserResponse
from app.api.deps import get_current_user, require_permission

router = APIRouter(prefix="/users", tags=["User Management"])


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"
    role_id: Optional[int] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    role_id: Optional[int] = None
    active: Optional[int] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None


class UserDetailResponse(UserResponse):
    """Enhanced user response with role info."""
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    active: int = 1
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


@router.get("", response_model=List[UserDetailResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:read")),
):
    """List all users."""
    result = await db.execute(
        select(User).order_by(User.username)
    )
    users = result.scalars().all()

    responses = []
    for u in users:
        role_name = None
        if u.role_id:
            role_result = await db.execute(select(Role).where(Role.id == u.role_id))
            role = role_result.scalar_one_or_none()
            if role:
                role_name = role.name
        responses.append(UserDetailResponse(
            id=u.id,
            username=u.username,
            role=u.role,
            role_id=u.role_id,
            role_name=role_name,
            customer_id=u.customer_id,
            customer_name=u.customer_name,
            active=u.active,
            created_at=u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else None,
            last_login_at=u.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if u.last_login_at else None,
        ))
    return responses


@router.post("")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:create")),
):
    """Create a new user."""
    existing = await db.execute(
        select(User).where(User.username == data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # If role_id is provided, validate it
    role_name_to_use = data.role
    role_id_to_use = data.role_id
    if role_id_to_use:
        role_result = await db.execute(select(Role).where(Role.id == role_id_to_use))
        role = role_result.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=400, detail="角色不存在")
        role_name_to_use = role.code
    elif data.role:
        # Find role by code
        role_result = await db.execute(
            select(Role).where(Role.code == data.role)
        )
        role = role_result.scalar_one_or_none()
        if role:
            role_id_to_use = role.id

    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        role=role_name_to_use,
        role_id=role_id_to_use,
        customer_id=data.customer_id,
        customer_name=data.customer_name,
        active=1,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    role_name = None
    if user.role_id:
        role_result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()
        if role:
            role_name = role.name

    return UserDetailResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        role_id=user.role_id,
        role_name=role_name,
        customer_id=user.customer_id,
        customer_name=user.customer_name,
        active=user.active,
    )


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:update")),
):
    """Update a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    is_builtin_admin = user.role == "admin" or user.username == "admin"

    if data.active is not None and data.active == 0 and is_builtin_admin:
        raise HTTPException(status_code=400, detail="内置管理员不能禁用")

    if data.username is not None:
        user.username = data.username
    if data.password is not None:
        user.password_hash = get_password_hash(data.password)
    if data.role_id is not None:
        # Validate role
        role_result = await db.execute(select(Role).where(Role.id == data.role_id))
        role = role_result.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=400, detail="角色不存在")
        user.role_id = data.role_id
        user.role = role.code
    elif data.role is not None:
        user.role = data.role
        # Also try to find matching role_id
        role_result = await db.execute(
            select(Role).where(Role.code == data.role)
        )
        role = role_result.scalar_one_or_none()
        if role:
            user.role_id = role.id
    if data.active is not None:
        user.active = data.active
    if data.customer_id is not None:
        user.customer_id = data.customer_id
    if data.customer_name is not None:
        user.customer_name = data.customer_name

    await db.commit()
    return {"status": "ok", "message": "用户已更新"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:delete")),
):
    """Soft-delete a user (set active=0)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    if user.role == "admin" or user.username == "admin":
        raise HTTPException(status_code=400, detail="内置管理员不能禁用")
    user.active = 0
    await db.commit()
    return {"status": "ok", "message": "用户已禁用"}
