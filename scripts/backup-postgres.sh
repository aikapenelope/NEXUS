#!/usr/bin/env bash
# NEXUS PostgreSQL backup script.
# Runs pg_dump inside the nexus-postgres container, saves compressed
# backups to /opt/nexus/backups/, and prunes files older than 7 days.
#
# Install as a daily cron job on the host:
#   echo "0 3 * * * /opt/nexus/app/scripts/backup-postgres.sh >> /var/log/nexus-backup.log 2>&1" \
#     | crontab -
#
set -euo pipefail

BACKUP_DIR="/opt/nexus/backups"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/nexus_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting PostgreSQL backup..."

# Dump all nexus databases (custom format is faster but sql.gz is more portable).
docker exec nexus-postgres pg_dump \
    -U nexus \
    -d nexus \
    --no-owner \
    --no-privileges \
    | gzip > "${BACKUP_FILE}"

SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date -Iseconds)] Backup complete: ${BACKUP_FILE} (${SIZE})"

# Prune old backups
DELETED=$(find "${BACKUP_DIR}" -name "nexus_*.sql.gz" -mtime +${RETENTION_DAYS} -print -delete | wc -l)
echo "[$(date -Iseconds)] Pruned ${DELETED} backup(s) older than ${RETENTION_DAYS} days."
