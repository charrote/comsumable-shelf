"""Changelog API — PDA 版本更新日志（数据库版）。

提供 PDA 下载页和 APP 版本更新页所需的版本历史数据。
数据存储在 ``app_changelog`` 表中，替代原来的 CHANGELOG.md 文件方案。
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models import User, AppChangelog
from app.utils.database import get_db

router = APIRouter(prefix="/app", tags=["Changelog"])


# ── Schemas ────────────────────────────────────────────────────────


class ChangelogEntryIn(BaseModel):
    version: str
    notes: str
    date: Optional[str] = None


class ChangelogEntryOut(BaseModel):
    version: str
    notes: str
    date: str
    created_at: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/changelog", response_model=List[ChangelogEntryOut])
async def get_changelog(
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — 返回全部版本更新日志，按版本号降序排列。

    无需认证，PDA 下载页等公开页面可读取。
    """
    result = await db.execute(
        select(AppChangelog)
        .order_by(desc(AppChangelog.date), desc(AppChangelog.version))
    )
    rows = result.scalars().all()
    return [
        ChangelogEntryOut(
            version=r.version,
            notes=r.notes,
            date=r.date,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@router.post("/changelog", status_code=status.HTTP_201_CREATED)
async def append_changelog(
    entry: ChangelogEntryIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加一条新版本记录到更新日志。

    需要登录认证（APP 版本更新页调用）。
    版本号不能为空，更新说明不能为空。
    """
    version_str = entry.version.strip()
    notes_str = entry.notes.strip()

    if not version_str:
        raise HTTPException(status_code=400, detail="版本号不能为空")
    if not notes_str:
        raise HTTPException(status_code=400, detail="更新说明不能为空")

    entry_date = entry.date or date.today().isoformat()

    changelog = AppChangelog(
        version=version_str,
        notes=notes_str,
        date=entry_date,
    )
    db.add(changelog)
    await db.commit()
    await db.refresh(changelog)

    return {
        "message": "更新日志已添加",
        "version": version_str,
        "id": changelog.id,
    }
