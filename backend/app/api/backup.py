"""Database backup & restore API routes."""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.schemas import BackupResponse, BackupCreateResponse, BackupRestoreResponse
from app.utils.database import get_db
from app.models import DataBackup, User
from app.api.auth import get_current_user
from app.services.backup_service import create_backup, restore_backup, delete_backup_file

router = APIRouter(prefix="/backups", tags=["Data Backup"])


@router.get("", response_model=list[BackupResponse])
async def list_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all backup records, ordered by creation time descending."""
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

    # Delete the physical file
    delete_backup_file(backup)

    # Delete the database record
    await db.delete(backup)
    await db.commit()

    return {"status": "ok", "message": f"备份 '{backup.filename}' 已删除"}
