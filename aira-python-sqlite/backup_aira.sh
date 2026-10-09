#!/bin/bash
DB_DIR="/home/azureuser/aira-bot/aira-python-sqlite"
BACKUP_DIR="$DB_DIR/backups"
mkdir -p "$BACKUP_DIR"

TS=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/aira_$TS.db"

sqlite3 "$DB_DIR/aira.db" ".backup '$DEST'"

if [ -s "$DEST" ]; then
    echo "$(date): backup OK -> $DEST" >> "$BACKUP_DIR/backup.log"
else
    echo "$(date): backup FAILED" >> "$BACKUP_DIR/backup.log"
fi

# Keep only the 2 most recent backups, delete the rest
ls -1t "$BACKUP_DIR"/aira_*.db 2>/dev/null | tail -n +3 | xargs -r rm -f
