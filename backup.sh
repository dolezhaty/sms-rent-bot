#!/bin/bash
# backup.sh - creates a timestamped copy of the SQLite DB
DB_PATH="$(dirname "$0")/shopDB.sqlite"
BACKUP_DIR="$(dirname "$0")/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
cp "$DB_PATH" "$BACKUP_DIR/shopDB_${TIMESTAMP}.sqlite"
# remove backups older than 30 days
find "$BACKUP_DIR" -name "*.sqlite" -mtime +30 -delete
echo "Backup created: $BACKUP_DIR/shopDB_${TIMESTAMP}.sqlite"
