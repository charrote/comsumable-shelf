"""Backup & restore service using pg_dump / pg_restore.

Backup metadata is stored in TWO places for resilience:
1. Database table `data_backups` (for runtime queries & reference)
2. Filesystem manifest `/app/backups/manifest.json` (survives DB reset)

This way, even after a full database reset or restore, the backup list
can still be recovered from the filesystem manifest.
"""

import os
import json
import subprocess
import structlog
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DataBackup

logger = structlog.get_logger()

BACKUP_DIR = Path(settings.BACKUP_DIR)
MANIFEST_PATH = BACKUP_DIR / "manifest.json"


# ═══════════════════════════════════════════════════════════════════════
#  Filesystem manifest helpers
# ═══════════════════════════════════════════════════════════════════════

def _ensure_backup_dir():
    """Ensure the backup directory exists."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _load_manifest() -> list[dict]:
    """Load backup metadata from filesystem manifest.

    Returns empty list if manifest doesn't exist or is corrupted.
    """
    if not MANIFEST_PATH.exists():
        return []
    try:
        with open(MANIFEST_PATH, "r") as f:
            data = json.load(f)
        return data.get("backups", [])
    except (json.JSONDecodeError, IOError, KeyError) as e:
        logger.warning("Failed to load backup manifest", error=str(e))
        return []


def _save_manifest(entries: list[dict]):
    """Write backup metadata to filesystem manifest."""
    _ensure_backup_dir()
    # Sort newest first
    entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    try:
        with open(MANIFEST_PATH, "w") as f:
            json.dump({"backups": entries}, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error("Failed to write backup manifest", error=str(e))


def _manifest_entry_from_backup(backup: DataBackup) -> dict:
    """Convert a DataBackup ORM object to a manifest entry dict."""
    return {
        "id": backup.id,
        "filename": backup.filename,
        "filepath": backup.filepath,
        "file_size": backup.file_size,
        "db_version": backup.db_version,
        "status": backup.status,
        "error_message": backup.error_message,
        "operator": backup.operator,
        "created_at": (
            backup.created_at.isoformat()
            if backup.created_at
            else datetime.utcnow().isoformat()
        ),
    }


def _manifest_entry_from_file(dump_path: Path) -> Optional[dict]:
    """Create a manifest entry by inspecting a .dump file on disk."""
    if not dump_path.exists() or not dump_path.is_file():
        return None
    # Parse filename: smes_backup_YYYYMMDD_HHMMSS.dump
    filename = dump_path.name
    created_at = None
    try:
        # Extract timestamp from filename
        parts = filename.replace(".dump", "").split("_")
        if len(parts) >= 3 and parts[0] == "smes" and parts[1] == "backup":
            ts_str = "_".join(parts[2:])  # YYYYMMDD_HHMMSS
            created_at = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").isoformat()
    except (ValueError, IndexError):
        pass

    file_size = dump_path.stat().st_size
    return {
        "id": None,  # orphaned — no DB record
        "filename": filename,
        "filepath": str(dump_path),
        "file_size": file_size,
        "db_version": "",
        "status": "completed",
        "error_message": "",
        "operator": "(扫描恢复)",
        "created_at": created_at or datetime.utcnow().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════
#  pg_dump / pg_restore helpers
# ═══════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════

def list_backups_from_manifest() -> list[dict]:
    """List all backup entries from filesystem manifest (survives DB reset)."""
    return _load_manifest()


def scan_orphaned_dumps() -> list[dict]:
    """Scan backup directory for .dump files not recorded in manifest.

    Returns a list of recovered manifest entries for orphaned files.
    """
    _ensure_backup_dir()
    manifest_files = {e["filename"] for e in _load_manifest()}

    orphans = []
    for f in sorted(BACKUP_DIR.iterdir()):
        if f.suffix == ".dump" and f.name not in manifest_files:
            entry = _manifest_entry_from_file(f)
            if entry:
                orphans.append(entry)

    # Persist recovered entries back to manifest
    if orphans:
        existing = _load_manifest()
        existing_filenames = {e["filename"] for e in existing}
        for o in orphans:
            if o["filename"] not in existing_filenames:
                existing.append(o)
        _save_manifest(existing)

    return orphans


async def get_db_ids_for_manifest(db: AsyncSession) -> dict[str, int]:
    """Query the database for existing backup records, keyed by filename."""
    from sqlalchemy import select
    result = await db.execute(select(DataBackup))
    records = result.scalars().all()
    return {r.filename: r.id for r in records}


async def ensure_manifest_db_sync(db: AsyncSession) -> list[DataBackup]:
    """Create DB records for manifest entries that lack a database record.

    After a database reset (e.g., sync-db.sh pull), the manifest still
    has all backup entries but the data_backups table is empty. This
    function re-creates the missing DB records from manifest data.

    Returns the list of newly created DataBackup records.
    """
    manifest = _load_manifest()
    if not manifest:
        return []

    db_ids = await get_db_ids_for_manifest(db)
    new_records = []

    for entry in manifest:
        fname = entry.get("filename", "")
        if fname in db_ids:
            continue  # already has a DB record

        created_at = None
        if entry.get("created_at"):
            try:
                created_at = datetime.fromisoformat(entry["created_at"])
            except (ValueError, TypeError):
                pass

        backup = DataBackup(
            filename=fname,
            filepath=entry.get("filepath", ""),
            file_size=entry.get("file_size", 0),
            db_version=entry.get("db_version", ""),
            status=entry.get("status", "completed"),
            error_message=entry.get("error_message", ""),
            operator=entry.get("operator", ""),
            created_at=created_at,
        )
        db.add(backup)
        new_records.append(backup)

    if new_records:
        await db.flush()
        # Update manifest with real DB ids
        for b in new_records:
            _append_to_manifest(_manifest_entry_from_backup(b))
        await db.commit()

    return new_records


async def create_backup(db: AsyncSession, operator: str = "") -> DataBackup:
    """Create a database backup and record it in the database + manifest."""
    _ensure_backup_dir()

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
            # Update manifest too
            _append_to_manifest(_manifest_entry_from_backup(backup))
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

    # Persist to filesystem manifest (survives DB reset)
    _append_to_manifest(_manifest_entry_from_backup(backup))

    return backup


def _append_to_manifest(entry: dict):
    """Add or update an entry in the manifest file."""
    entries = _load_manifest()
    # Replace existing entry with same filename, or append
    entries = [e for e in entries if e["filename"] != entry["filename"]]
    entries.append(entry)
    _save_manifest(entries)


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
    """Delete the backup file from disk and update manifest."""
    try:
        if os.path.exists(backup.filepath):
            os.remove(backup.filepath)
            logger.info("Backup file deleted", filepath=backup.filepath)

        # Also remove from manifest
        entries = _load_manifest()
        entries = [e for e in entries if e["filename"] != backup.filename]
        _save_manifest(entries)
    except Exception as e:
        logger.error("Failed to delete backup file", filepath=backup.filepath, error=str(e))
