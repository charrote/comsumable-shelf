#!/bin/bash
# PostgreSQL 自动备份脚本
# 每天凌晨 3:00 执行，保留最近 7 天备份

set -euo pipefail

BACKUP_DIR="/home/ubuntu/dev/comsumable-shelf/backups"
DB_CONTAINER="consumable-shelf-db"
DB_NAME="smes"
DB_USER="postgres"
RETENTION_DAYS=7
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

mkdir -p "$BACKUP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backup: ${DB_NAME}" >> "$LOG_FILE"

docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" 2>> "$LOG_FILE" | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup completed: ${BACKUP_FILE} (${FILE_SIZE})" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup FAILED!" >> "$LOG_FILE"
    exit 1
fi

# 删除 7 天前的备份
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaned up backups older than ${RETENTION_DAYS} days" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
