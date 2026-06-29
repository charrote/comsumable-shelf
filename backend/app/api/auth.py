"""Authentication API routes."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import verify_password, create_access_token
from app.utils.database import get_db
from app.models import User
from app.api.deps import get_current_user, get_user_permissions


class UserPermissionsResponse(UserResponse):
    """User info with permissions."""
    role_id: Optional[int] = None
    permissions: List[str] = []


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """User login."""
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token({"sub": user.username, "role": user.role})

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    return TokenResponse(
        access_token=token,
        expires_in=3600,
    )


@router.get("/me", response_model=UserPermissionsResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info with permissions."""
    permissions = await get_user_permissions(user, db)
    return UserPermissionsResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        role_id=user.role_id,
        customer_id=user.customer_id,
        customer_name=user.customer_name,
        permissions=permissions,
    )


@router.get("/permissions", response_model=List[str])
async def get_my_permissions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's permission codes."""
    return await get_user_permissions(user, db)
