"""Reusable dependencies for permission checking."""

from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Role, Permission, RolePermission
from app.utils.database import get_db

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from JWT token."""
    from app.services.auth_service import decode_access_token

    payload = decode_access_token(credentials.credentials)
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


def require_permission(permission_code: str):
    """
    Dependency factory: returns a dependency that checks if the current user's
    role has the specified permission.

    Usage:
        @router.get("/users")
        async def list_users(current_user = Depends(require_permission("user:read"))):
            ...
    """
    async def _check_permission(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Admin always has all permissions
        if current_user.role == "admin":
            return current_user

        # If user has role_id, check via role_permissions
        if current_user.role_id:
            # Find the permission by code
            perm_result = await db.execute(
                select(Permission).where(Permission.code == permission_code)
            )
            permission = perm_result.scalar_one_or_none()
            if not permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足: 缺少 {permission_code}",
                )

            # Check if role has this permission
            rp_result = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == current_user.role_id,
                    RolePermission.permission_id == permission.id,
                )
            )
            if rp_result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足: 缺少 {permission_code}",
                )
        else:
            # Legacy role-based check
            # Map legacy roles to basic permissions
            role_permissions = {
                "admin": ["*"],
                "supervisor": [
                    "dashboard:read",
                    "material:read", "material:create", "material:update",
                    "shelf:read", "shelf:create", "shelf:update",
                    "inventory:read", "inventory:update", "inventory:export",
                    "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
                    "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
                    "xr:read", "xr:upload", "xr:match",
                    "bom:read", "bom:create", "bom:update",
                    "report:read",
                    "customer:read",
                    "supplier:read", "supplier:create", "supplier:update",
                    "barcode:read",
                ],
                "operator": [
                    "dashboard:read",
                    "material:read",
                    "shelf:read",
                    "inventory:read", "inventory:update", "inventory:export",
                    "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
                    "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
                    "xr:read", "xr:upload", "xr:match",
                    "bom:read",
                    "report:read",
                ],
                "readonly": [
                    "dashboard:read",
                    "material:read",
                    "shelf:read",
                    "inventory:read",
                    "receipt:read",
                    "issue:read",
                    "xr:read",
                    "bom:read",
                    "report:read",
                    "customer:read",
                    "supplier:read",
                    "settings:read",
                    "barcode:read",
                ],
            }
            perms = role_permissions.get(current_user.role, [])
            if "*" not in perms and permission_code not in perms:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足: 缺少 {permission_code}",
                )

        return current_user

    return _check_permission


async def get_user_permissions(
    user: User,
    db: AsyncSession,
) -> list[str]:
    """Get all permission codes for a user."""
    if user.role == "admin":
        # Return all permissions
        result = await db.execute(select(Permission))
        return [p.code for p in result.scalars().all()]

    if user.role_id:
        result = await db.execute(
            select(RolePermission).where(RolePermission.role_id == user.role_id)
        )
        rps = result.scalars().all()
        permission_codes = []
        for rp in rps:
            perm = await db.get(Permission, rp.permission_id)
            if perm:
                permission_codes.append(perm.code)
        return permission_codes
    else:
        # Legacy role
        legacy_map = {
            "supervisor": [
                "dashboard:read",
                "material:read", "material:create", "material:update",
                "shelf:read", "shelf:create", "shelf:update",
                "inventory:read", "inventory:update", "inventory:export", "inventory:direct-out",
                "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
                "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
                "xr:read", "xr:upload", "xr:match",
                "bom:read", "bom:create", "bom:update",
                "report:read",
                "settings:read",
                "customer:read",
                "supplier:read", "supplier:create", "supplier:update",
                "barcode:read",
                "user:read",
                "app-download:read",
                "backup:read",
            ],
            "operator": [
                "dashboard:read",
                "material:read",
                "shelf:read",
                "inventory:read", "inventory:update", "inventory:export",
                "receipt:read", "receipt:create", "receipt:scan", "receipt:manual-entry",
                "issue:read", "issue:create", "issue:update", "issue:assign", "issue:pick",
                "xr:read", "xr:upload", "xr:match",
                "bom:read",
                "report:read",
            ],
            "readonly": [
                "dashboard:read",
                "material:read",
                "shelf:read",
                "inventory:read",
                "receipt:read",
                "issue:read",
                "xr:read",
                "bom:read",
                "report:read",
                "customer:read",
                "supplier:read",
                "settings:read",
                "barcode:read",
                "app-download:read",
                "backup:read",
            ],
        }
        return legacy_map.get(user.role, [])
