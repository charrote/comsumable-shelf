"""Database backup & restore API routes.

Backup metadata is stored both in the database AND in a filesystem
manifest (/app/backups/manifest.json). The manifest serves as the
primary source for listing — it survives database resets so the
backup list is never lost.
"""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (
    BackupResponse,
    BackupCreateResponse,
    BackupRestoreResponse,
)
from app.utils.database import get_db
from app.models import DataBackup, User
from app.api.auth import get_current_user
from app.services.backup_service import (
    create_backup,
    restore_backup,
    delete_backup_file,
    list_backups_from_manifest,
    scan_orphaned_dumps,
    ensure_manifest_db_sync,
)

router = APIRouter(prefix="/backups", tags=["Data Backup"])


# ────────────────────────────────────────────────────────────
#  Helper: build BackupResponse from a manifest entry
# ────────────────────────────────────────────────────────────

def _from_manifest_entry(entry: dict) -> dict:
    """Convert a manifest entry dict to a BackupResponse-compatible dict."""
    from datetime import datetime
    created_at = None
    if entry.get("created_at"):
        try:
            created_at = datetime.fromisoformat(entry["created_at"])
        except (ValueError, TypeError):
            created_at = None
    return {
        "id": entry.get("id") or 0,
        "filename": entry.get("filename", ""),
        "filepath": entry.get("filepath", ""),
        "file_size": entry.get("file_size", 0),
        "db_version": entry.get("db_version", ""),
        "status": entry.get("status", "completed"),
        "error_message": entry.get("error_message", ""),
        "operator": entry.get("operator", ""),
        "created_at": created_at,
    }


# ────────────────────────────────────────────────────────────
#  Endpoints
# ────────────────────────────────────────────────────────────

@router.get("", response_model=list[BackupResponse])
async def list_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all backup records.

    Primary source: filesystem manifest (survives DB reset).
    Falls back to DB query if manifest is empty.
    """
    # 1) Try manifest first — this always works even after DB reset
    manifest_entries = list_backups_from_manifest()

    if manifest_entries:
        # Merge with DB records where possible (to get real DB ids)
        try:
            result = await db.execute(
                select(DataBackup).order_by(desc(DataBackup.created_at))
            )
            db_backups = result.scalars().all()
            db_lookup = {b.filename: b for b in db_backups}

            merged = []
            for entry in manifest_entries:
                item = _from_manifest_entry(entry)
                filename = entry.get("filename", "")
                if filename in db_lookup:
                    db_b = db_lookup[filename]
                    # Prefer real DB id over manifest's possibly-stale id
                    item["id"] = db_b.id
                    item["file_size"] = db_b.file_size
                    item["db_version"] = db_b.db_version
                    item["status"] = db_b.status
                    item["error_message"] = db_b.error_message
                    item["operator"] = db_b.operator or item["operator"]
                merged.append(item)

            return merged
        except Exception as e:
            # DB might be down — return manifest data as-is
            logger = __import__("structlog").get_logger()
            logger.warning("Failed to merge with DB, using manifest only", error=str(e))
            return [_from_manifest_entry(e) for e in manifest_entries]

    # 2) Fallback: read from database directly
    result = await db.execute(
        select(DataBackup).order_by(desc(DataBackup.created_at))
    )
    backups = result.scalars().all()
    return [
        BackupResponse(
            id=b.id,
            filename=b.filename,
            filepath=b.filepath,
            file_size=b.file_size,
            db_version=b.db_version,
            status=b.status,
            error_message=b.error_message,
            operator=b.operator,
            created_at=b.created_at,
        )
        for b in backups
    ]


@router.post("/rescan", response_model=list[BackupResponse])
async def rescan_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan and repair backup metadata.

    Handles two recovery scenarios:
    1. Orphaned .dump files on disk with no manifest entry
    2. Manifest entries with no corresponding database record
       (e.g., after sync-db.sh reset or pg_restore --clean)

    Rebuilds both the manifest and database records to match the
    actual files on disk.
    """
    # --- Case 1: dump files without manifest entries ---
    file_orphans = scan_orphaned_dumps()

    # --- Case 2: manifest entries without DB records ---
    db_missing = await ensure_manifest_db_sync(db)

    total_found = len(file_orphans) + len(db_missing)

    # Return full merged list
    manifest_entries = list_backups_from_manifest()
    if not manifest_entries:
        return []

    try:
        result = await db.execute(
            select(DataBackup).order_by(desc(DataBackup.created_at))
        )
        db_backups = result.scalars().all()
        db_lookup = {b.filename: b for b in db_backups}
        merged = []
        for entry in manifest_entries:
            item = _from_manifest_entry(entry)
            filename = entry.get("filename", "")
            if filename in db_lookup:
                db_b = db_lookup[filename]
                item["id"] = db_b.id
                item["file_size"] = db_b.file_size
                item["db_version"] = db_b.db_version
                item["status"] = db_b.status
                item["operator"] = db_b.operator or item["operator"]
            merged.append(item)
        return merged
    except Exception:
        return [_from_manifest_entry(e) for e in manifest_entries]


@router.post("", response_model=BackupCreateResponse)
async def create_backup_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new database backup."""
    try:
        backup = await create_backup(db, operator=current_user.username)
        await db.commit()
        await db.refresh(backup)
        return BackupCreateResponse(
            id=backup.id,
            filename=backup.filename,
            filepath=backup.filepath,
            file_size=backup.file_size,
            status=backup.status,
            message="备份完成" if backup.status == "completed" else f"备份失败: {backup.error_message}",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建备份失败: {str(e)}")


@router.get("/{backup_id}", response_model=BackupResponse)
async def get_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single backup record."""
    result = await db.execute(
        select(DataBackup).where(DataBackup.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(status_code=404, detail="备份记录不存在")
    return BackupResponse(
        id=backup.id,
        filename=backup.filename,
        filepath=backup.filepath,
        file_size=backup.file_size,
        db_version=backup.db_version,
        status=backup.status,
        error_message=backup.error_message,
        operator=backup.operator,
        created_at=backup.created_at,
    )


@router.post("/{backup_id}/restore", response_model=BackupRestoreResponse)
async def restore_backup_endpoint(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore the database from a backup. Requires admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行数据恢复操作")

    try:
        result = await restore_backup(backup_id, db)
        return BackupRestoreResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a backup record and its file."""
    result = await db.execute(
        select(DataBackup).where(DataBackup.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(status_code=404, detail="备份记录不存在")

    # Delete the physical file (also updates manifest)
    delete_backup_file(backup)

    # Delete the database record
    await db.delete(backup)
    await db.commit()

    return {"status": "ok", "message": f"备份 '{backup.filename}' 已删除"}
