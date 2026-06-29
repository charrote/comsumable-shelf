"""App version check API — enables PDA update detection.

The latest version info is stored in the ``system_settings`` table
under these keys:

  =====================  ============================================
  Key                    Description
  =====================  ============================================
  ``app_latest_version``  Latest available version (e.g. ``3.1.0``)
  ``app_min_version``     Minimum required version (e.g. ``3.0.0``)
  ``app_download_url``    URL to download the latest APK
  ``app_release_notes``   Release notes / changelog
  =====================  ============================================

Usage flow (PDA):
  1. Call ``GET /api/app/version`` on app start / manual check.
  2. Compare ``latest_version`` with local ``app.version``.
  3. If newer → show update dialog with release_notes + download_url.
  4. If ``min_version`` > local version → force update (block usage).
"""

from typing import Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.utils.database import get_db
from app.models import SystemSetting

router = APIRouter(prefix="/app", tags=["App Update"])


# ── Response Model ─────────────────────────────────────────────────


class AppVersionResponse(BaseModel):
    latest_version: str = ""
    min_version: str = ""
    download_url: str = ""
    release_notes: str = ""
    checked_at: Optional[str] = None


_SETTING_KEYS = {
    "app_latest_version": "latest_version",
    "app_min_version": "min_version",
    "app_download_url": "download_url",
    "app_release_notes": "release_notes",
}


@router.get("/version", response_model=AppVersionResponse)
async def get_app_version(
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — returns the latest app version info.

    No authentication required so the PDA can check on startup
    even before the user logs in.
    """
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(_SETTING_KEYS.keys()))
    )
    rows = result.scalars().all()
    settings = {r.key: r.value for r in rows}

    return AppVersionResponse(
        latest_version=settings.get("app_latest_version", ""),
        min_version=settings.get("app_min_version", ""),
        download_url=settings.get("app_download_url", ""),
        release_notes=settings.get("app_release_notes", ""),
        checked_at=datetime.utcnow().isoformat() + "Z",
    )
