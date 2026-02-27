#!/usr/bin/env bash
# ============================================================
# PostgreSQL backup script for Barber Kombat
#
# Usage:
#   ./scripts/backup.sh              # Create backup
#   ./scripts/backup.sh --restore FILENAME  # Restore from backup
#
# Backups are stored in ./backups/ as compressed custom-format dumps.
# Keeps last 14 days of backups by default.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS=14

cd "$PROJECT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

create_backup() {
    mkdir -p "$BACKUP_DIR"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    FILENAME="barber_kombat_${TIMESTAMP}.dump"

    echo -e "${GREEN}[BACKUP]${NC} Creating backup: $FILENAME"

    docker compose exec -T db pg_dump -Fc -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-barber_kombat}" \
        > "$BACKUP_DIR/$FILENAME"

    SIZE=$(du -h "$BACKUP_DIR/$FILENAME" | cut -f1)
    echo -e "${GREEN}[BACKUP]${NC} Backup created: $FILENAME ($SIZE)"

    # Clean old backups
    DELETED=$(find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete -print | wc -l)
    if [ "$DELETED" -gt 0 ]; then
        echo -e "${GREEN}[BACKUP]${NC} Cleaned $DELETED old backups (older than $RETENTION_DAYS days)"
    fi
}

restore_backup() {
    local FILE="$1"
    if [ ! -f "$FILE" ]; then
        echo -e "${RED}[ERROR]${NC} Backup file not found: $FILE"
        exit 1
    fi

    echo -e "${RED}[WARNING]${NC} This will overwrite the current database!"
    read -p "Are you sure? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi

    echo -e "${GREEN}[RESTORE]${NC} Restoring from: $FILE"

    docker compose exec -T db pg_restore -U "${POSTGRES_USER:-postgres}" \
        -d "${POSTGRES_DB:-barber_kombat}" --clean --if-exists < "$FILE"

    echo -e "${GREEN}[RESTORE]${NC} Restore complete"
}

case "${1:-}" in
    --restore)
        if [ -z "${2:-}" ]; then
            echo "Usage: $0 --restore FILENAME"
            exit 1
        fi
        restore_backup "$2"
        ;;
    *)
        create_backup
        ;;
esac
