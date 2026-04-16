#!/bin/bash

set -euo pipefail

LUCKY_DIR="${LUCKY_DIR:-/home/luk-server/Lucky}"
BACKUP_DIR="${BACKUP_DIR:-/home/luk-server/homelab/backups/lucky}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

if [[ -f "$HOMELAB_DIR/.env" ]]; then
    LUCKY_DB_NAME=$(grep -E "^LUCKY_DB_NAME=" "$HOMELAB_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '\r' || echo "")
    LUCKY_DB_USER=$(grep -E "^LUCKY_DB_USER=" "$HOMELAB_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '\r' || echo "")
    LUCKY_DB_PASSWORD=$(grep -E "^LUCKY_DB_PASSWORD=" "$HOMELAB_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '\r' || echo "")
fi

DB_NAME="${LUCKY_DB_NAME:-discordbot}"
DB_USER="${LUCKY_DB_USER:-discordbot}"
DB_PASSWORD="${LUCKY_DB_PASSWORD:-}"
CONTAINER="${LUCKY_DB_CONTAINER:-lucky-postgres}"

if [[ -z "$DB_PASSWORD" ]]; then
    echo "ERROR: LUCKY_DB_PASSWORD is not set. Define it in $HOMELAB_DIR/.env or export it before running." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

usage() {
    cat <<'EOF'
Usage: ./recover-lucky-db.sh [--backup-only | --full-recovery | --help]

Modes:
  --backup-only    Create DB backup and exit.
  --full-recovery  Force schema recovery + migration baseline.
  (no flag)        Auto mode: backup when healthy; recover only if tables are missing.
  --help           Show this help message.
EOF
}

check_tables() {
    docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "\dt" 2>/dev/null | grep -c '|' || echo 0
}

backup_db() {
    local backup_file="$BACKUP_DIR/$DB_NAME-$(date +%Y%m%d-%H%M%S).sql"
    docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" > "$backup_file"
    echo "Backup saved: $backup_file"
    echo "$backup_file"
}

apply_schema() {
    echo "Applying Prisma schema via db push..."
    docker run --rm \
        --network lucky_lucky-network \
        -v "$LUCKY_DIR:/app" \
        -w /app \
        -e DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@postgres:5432/$DB_NAME" \
        node:22-alpine \
        sh -c 'node_modules/.bin/prisma db push --config prisma/prisma.config.ts' 2>&1

    echo "Baselining all existing migrations..."
    while IFS= read -r migration; do
        docker run --rm \
            --network lucky_lucky-network \
            -v "$LUCKY_DIR:/app" \
            -w /app \
            -e DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@postgres:5432/$DB_NAME" \
            node:22-alpine \
            sh -c "node_modules/.bin/prisma migrate resolve --applied $migration --config prisma/prisma.config.ts" 2>&1 | grep -v "^$"
    done < <(find "$LUCKY_DIR/prisma/migrations" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
}

echo "=== Lucky DB Recovery ==="

MODE="auto"
if [[ $# -gt 1 ]]; then
    usage
    exit 1
fi

if [[ $# -eq 1 ]]; then
    case "$1" in
        --backup-only)
            MODE="backup-only"
            ;;
        --full-recovery)
            MODE="full-recovery"
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option '$1'"
            usage
            exit 1
            ;;
    esac
fi

echo "Checking table count..."
TABLE_COUNT=$(check_tables)
echo "Tables found: $TABLE_COUNT"

if [[ "$MODE" == "backup-only" ]]; then
    echo "Running backup only..."
    backup_db
    exit 0
fi

if [[ "$MODE" == "full-recovery" ]]; then
    echo "Running forced full recovery..."
    if ! docker exec "$CONTAINER" pg_isready -U "$DB_USER" > /dev/null 2>&1; then
        echo "ERROR: postgres is not running. Start it first."
        exit 1
    fi
    apply_schema
    echo "Forced full recovery completed."
    exit 0
fi

if [[ "$TABLE_COUNT" -gt 5 ]]; then
    echo "Tables exist ($TABLE_COUNT), backing up..."
    backup_db
    echo "No recovery needed."
    exit 0
fi

echo "Tables missing! Starting recovery..."

# Check if postgres is running
if ! docker exec "$CONTAINER" pg_isready -U "$DB_USER" > /dev/null 2>&1; then
    echo "ERROR: postgres is not running. Start it first."
    exit 1
fi

apply_schema

echo ""
echo "Verifying recovery..."
TABLE_COUNT=$(check_tables)
echo "Tables after recovery: $TABLE_COUNT"

if [[ "$TABLE_COUNT" -gt 5 ]]; then
    echo "Recovery successful!"
    docker restart lucky-backend 2>/dev/null || true
    echo "lucky-backend restarted."
else
    echo "ERROR: Recovery failed - still $TABLE_COUNT tables."
    exit 1
fi
