"""System settings API routes."""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from app.schemas import SystemSettingUpdate, SystemSettingResponse
from app.utils.database import get_db
from app.models import SystemSetting

router = APIRouter(prefix="/settings", tags=["System Settings"])


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
    settings = result.scalars().all()
    return [SystemSettingResponse(
        key=s.key, value=s.value,
        description=s.description, updated_at=s.updated_at,
    ) for s in settings]


@router.put("/{key}")
async def update_setting(
    key: str,
    data: SystemSettingUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        setting = SystemSetting(key=key, value=data.value, description=data.description)
        db.add(setting)
    else:
        setting.value = data.value
        if data.description is not None:
            setting.description = data.description
    await db.commit()
    await db.refresh(setting)
    return SystemSettingResponse(
        key=setting.key, value=setting.value,
        description=setting.description, updated_at=setting.updated_at,
    )


@router.get("/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="设置项不存在")
    return SystemSettingResponse(
        key=setting.key, value=setting.value,
        description=setting.description, updated_at=setting.updated_at,
    )
