#!/usr/bin/env bash
# Daily PostgreSQL backup. Run from a cron job (host cron, Render Cron Job,
# or Railway scheduled service). Requires DATABASE_URL and a destination.
#
# Usage: BACKUP_DIR=/backups ./scripts/backup.sh
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y-%m-%d_%H%M)
FILE="$BACKUP_DIR/mfm_billing_$STAMP.sql.gz"

pg_dump "$DATABASE_URL" | gzip > "$FILE"
echo "Backup written: $FILE ($(du -h "$FILE" | cut -f1))"

# prune old backups
find "$BACKUP_DIR" -name 'mfm_billing_*.sql.gz' -mtime +"$KEEP_DAYS" -delete

# Off-server copy strongly recommended, e.g.:
#   rclone copy "$FILE" remote:mfm-backups/
#   aws s3 cp "$FILE" s3://my-bucket/mfm-backups/
