"""Role management & permission assignment API routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.schemas import (
    RoleCreate, RoleUpdate, RoleResponse, RoleDetailResponse,
    PermissionResponse, PermissionGroup, RolePermissionUpdate,
)
from app.utils.database import get_db
from app.models import Role, Permission, RolePermission, User
from app.api.deps import get_current_user, require_permission

router = APIRouter(prefix="/roles", tags=["Role Management"])


# ── Role CRUD ──

@router.get("", response_model=List[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all roles."""
    result = await db.execute(
        select(Role).where(Role.active == 1).order_by(Role.id)
    )
    roles = result.scalars().all()

    # Get permission count and user count for each role
    responses = []
    for role in roles:
        perm_count_result = await db.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        )
        perm_count_val = len(perm_count_result.scalars().all())

        user_count_result = await db.execute(
            select(User).where(User.role_id == role.id, User.active == 1)
        )
        user_count_val = len(user_count_result.scalars().all())

        responses.append(RoleResponse(
            id=role.id,
            name=role.name,
            code=role.code,
            description=role.description or "",
            is_system=role.is_system,
            active=role.active,
            created_at=role.created_at,
            permission_count=perm_count_val,
            user_count=user_count_val,
        ))
    return responses


@router.get("/{role_id}", response_model=RoleDetailResponse)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get role detail with permissions."""
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    # Get permission codes and IDs
    perm_result = await db.execute(
        select(RolePermission).where(RolePermission.role_id == role_id)
    )
    rps = perm_result.scalars().all()

    permission_ids = []
    permission_codes = []
    for rp in rps:
        perm = await db.get(Permission, rp.permission_id)
        if perm:
            permission_ids.append(perm.id)
            permission_codes.append(perm.code)

    user_count_result = await db.execute(
        select(User).where(User.role_id == role_id, User.active == 1)
    )
    user_count_val = len(user_count_result.scalars().all())

    return RoleDetailResponse(
        id=role.id,
        name=role.name,
        code=role.code,
        description=role.description or "",
        is_system=role.is_system,
        active=role.active,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=permission_codes,
        permission_ids=permission_ids,
        user_count=user_count_val,
    )


@router.post("", response_model=RoleResponse)
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:create")),
):
    """Create a new role."""
    # Check for duplicate code
    existing = await db.execute(
        select(Role).where(Role.code == data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="角色编码已存在")

    role = Role(
        name=data.name,
        code=data.code,
        description=data.description or "",
        is_system=0,
        active=1,
    )
    db.add(role)
    await db.flush()

    # Assign permissions
    for perm_id in data.permission_ids:
        db.add(RolePermission(role_id=role.id, permission_id=perm_id))
    await db.commit()
    await db.refresh(role)

    return RoleResponse(
        id=role.id,
        name=role.name,
        code=role.code,
        description=role.description or "",
        is_system=role.is_system,
        active=role.active,
        created_at=role.created_at,
        permission_count=len(data.permission_ids),
        user_count=0,
    )


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:update")),
):
    """Update a role."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system and data.active is not None and data.active == 0:
        raise HTTPException(status_code=400, detail="系统内置角色不能禁用")

    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.active is not None:
        role.active = data.active

    # Update permissions if provided
    if data.permission_ids is not None:
        # Remove existing permissions
        await db.execute(
            delete(RolePermission).where(RolePermission.role_id == role_id)
        )
        # Add new permissions
        for perm_id in data.permission_ids:
            db.add(RolePermission(role_id=role_id, permission_id=perm_id))

    await db.commit()
    await db.refresh(role)

    # Get permission count
    perm_result = await db.execute(
        select(RolePermission).where(RolePermission.role_id == role_id)
    )
    perm_count = len(perm_result.scalars().all())

    return RoleResponse(
        id=role.id,
        name=role.name,
        code=role.code,
        description=role.description or "",
        is_system=role.is_system,
        active=role.active,
        created_at=role.created_at,
        permission_count=perm_count,
        user_count=0,
    )


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:delete")),
):
    """Delete a role (soft-delete by setting active=0)."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不能删除")

    # Check if any users are using this role
    user_result = await db.execute(
        select(User).where(User.role_id == role_id, User.active == 1)
    )
    if user_result.scalars().first():
        raise HTTPException(status_code=400, detail="该角色下存在启用中的用户，无法删除")

    role.active = 0
    await db.commit()
    return {"status": "ok", "message": "角色已禁用"}


# ── Permissions ──

@router.get("/permissions/all", response_model=List[PermissionGroup])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all permissions grouped by module."""
    result = await db.execute(
        select(Permission).order_by(Permission.module, Permission.id)
    )
    permissions = result.scalars().all()

    # Group by module
    groups: dict = {}
    for p in permissions:
        if p.module not in groups:
            groups[p.module] = []
        groups[p.module].append(PermissionResponse(
            id=p.id,
            code=p.code,
            name=p.name,
            module=p.module,
            description=p.description or "",
        ))

    return [
        PermissionGroup(module=module, permissions=perms)
        for module, perms in groups.items()
    ]


@router.get("/permissions/flat", response_model=List[PermissionResponse])
async def list_permissions_flat(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all permissions in flat format."""
    result = await db.execute(
        select(Permission).order_by(Permission.module, Permission.id)
    )
    permissions = result.scalars().all()
    return [
        PermissionResponse(
            id=p.id,
            code=p.code,
            name=p.name,
            module=p.module,
            description=p.description or "",
        )
        for p in permissions
    ]


# ── Role-Permission Assignment ──

@router.put("/{role_id}/permissions")
async def update_role_permissions(
    role_id: int,
    data: RolePermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:update")),
):
    """Update permissions for a role."""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    # Remove existing permissions
    await db.execute(
        delete(RolePermission).where(RolePermission.role_id == role_id)
    )

    # Add new permissions
    for perm_id in data.permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=perm_id))

    await db.commit()
    return {"status": "ok", "message": "角色权限已更新"}
