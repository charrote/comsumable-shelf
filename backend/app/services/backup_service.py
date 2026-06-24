"""Backup & restore service using pg_dump / pg_restore."""

import os
import subprocess
import structlog
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DataBackup

logger = structlog.get_logger()

BACKUP_DIR = Path(settings.BACKUP_DIR)


def ensure_backup_dir():
    """Ensure the backup directory exists."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _get_db_conn_params() -> dict:
    """Extract connection parameters from settings for pg_dump/pg_restore."""
    return {
        "host": settings.BACKUP_DB_HOST,
        "port": str(settings.BACKUP_DB_PORT),
        "dbname": settings.BACKUP_DB_NAME,
        "user": settings.BACKUP_DB_USER,
        "password": settings.BACKUP_DB_PASSWORD,
    }


def _pg_dump(backup_path: str, conn: dict) -> subprocess.CompletedProcess:
    """Execute pg_dump to create a custom-format dump."""
    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]
    cmd = [
        "pg_dump",
        "-h", conn["host"],
        "-p", conn["port"],
        "-U", conn["user"],
        "-d", conn["dbname"],
        "-F", "c",          # custom format (compressed, supports parallel restore)
        "-f", backup_path,
        "--no-owner",       # avoid owner issues across environments
        "--no-acl",         # skip ACLs
        "-v",
    ]
    logger.info("Running pg_dump", cmd=" ".join(cmd[:8]) + " ...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    return result


def _pg_restore(backup_path: str, conn: dict) -> subprocess.CompletedProcess:
    """Execute pg_restore to restore from a custom-format dump."""
    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]
    cmd = [
        "pg_restore",
        "-h", conn["host"],
        "-p", conn["port"],
        "-U", conn["user"],
        "-d", conn["dbname"],
        "-F", "c",
        "--clean",          # clean (drop) existing objects before restore
        "--if-exists",      # use IF EXISTS for drop commands
        "--no-owner",       # skip owner restoration
        "--no-acl",
        "-v",
        backup_path,
    ]
    logger.info("Running pg_restore", cmd=" ".join(cmd[:9]) + " ...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    return result


async def create_backup(db: AsyncSession, operator: str = "") -> DataBackup:
    """Create a database backup and record it in the database."""
    ensure_backup_dir()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"smes_backup_{timestamp}.dump"
    backup_path = str(BACKUP_DIR / filename)

    conn = _get_db_conn_params()

    # Create the backup record first (status = running)
    backup = DataBackup(
        filename=filename,
        filepath=backup_path,
        file_size=0,
        status="running",
        operator=operator,
    )
    db.add(backup)
    await db.flush()
    backup_id = backup.id

    try:
        # Run pg_dump
        result = _pg_dump(backup_path, conn)

        if result.returncode != 0:
            error_msg = result.stderr[:1000] if result.stderr else "Unknown pg_dump error"
            logger.error("pg_dump failed", returncode=result.returncode, stderr=result.stderr)
            backup.status = "failed"
            backup.error_message = error_msg
            await db.flush()
            return backup

        # Get file size
        file_size = os.path.getsize(backup_path) if os.path.exists(backup_path) else 0
        backup.file_size = file_size
        backup.status = "completed"
        backup.db_version = settings.APP_VERSION
        logger.info("Backup created", backup_id=backup_id, filename=filename, size=file_size)
    except subprocess.TimeoutExpired:
        error_msg = "pg_dump timed out after 300 seconds"
        logger.error(error_msg)
        backup.status = "failed"
        backup.error_message = error_msg
    except FileNotFoundError:
        error_msg = "pg_dump not found. Is PostgreSQL client installed?"
        logger.error(error_msg)
        backup.status = "failed"
        backup.error_message = error_msg
    except Exception as e:
        error_msg = str(e)[:1000]
        logger.error("Backup failed", error=error_msg)
        backup.status = "failed"
        backup.error_message = error_msg

    await db.flush()
    return backup


async def restore_backup(backup_id: int, db: AsyncSession) -> dict:
    """Restore the database from a backup record."""
    # Fetch the backup record
    result = await db.execute(
        select(DataBackup).where(DataBackup.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise FileNotFoundError(f"备份记录不存在 (id={backup_id})")

    if backup.status != "completed":
        raise ValueError(f"备份状态不是 'completed'，无法恢复 (当前状态: {backup.status})")

    backup_path = backup.filepath
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"备份文件不存在: {backup_path}")

    conn = _get_db_conn_params()

    try:
        # Run pg_restore
        result = _pg_restore(backup_path, conn)

        if result.returncode != 0:
            error_msg = result.stderr[:1000] if result.stderr else "Unknown pg_restore error"
            logger.error("pg_restore failed", returncode=result.returncode, stderr=result.stderr)
            return {
                "status": "failed",
                "backup_id": backup.id,
                "filename": backup.filename,
                "message": f"恢复失败: {error_msg}",
            }

        logger.info("Database restored successfully", backup_id=backup_id, filename=backup.filename)
        return {
            "status": "completed",
            "backup_id": backup.id,
            "filename": backup.filename,
            "message": f"数据库已成功从备份 '{backup.filename}' 恢复",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "backup_id": backup.id,
            "filename": backup.filename,
            "message": "恢复超时（600秒）",
        }
    except FileNotFoundError:
        return {
            "status": "failed",
            "backup_id": backup.id,
            "filename": backup.filename,
            "message": "pg_restore 未安装，请确认 PostgreSQL 客户端已安装",
        }
    except Exception as e:
        return {
            "status": "failed",
            "backup_id": backup.id,
            "filename": backup.filename,
            "message": f"恢复异常: {str(e)[:500]}",
        }


def delete_backup_file(backup: DataBackup) -> None:
    """Delete the backup file from disk."""
    try:
        if os.path.exists(backup.filepath):
            os.remove(backup.filepath)
            logger.info("Backup file deleted", filepath=backup.filepath)
    except Exception as e:
        logger.error("Failed to delete backup file", filepath=backup.filepath, error=str(e))
