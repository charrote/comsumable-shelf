"""Authentication API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import verify_password, create_access_token, decode_access_token
from app.utils.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_user(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from JWT token."""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


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


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        customer_id=user.customer_id,
        customer_name=user.customer_name,
    )
