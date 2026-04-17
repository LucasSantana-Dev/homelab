#!/bin/bash
set -euo pipefail

# Restic backup script for homelab
# Usage: ./restic-backup.sh
#
# Requires:
# - restic: brew install restic
# - RESTIC_REPOSITORY env var: B2 endpoint (e.g., b2:bucket-name:/path)
# - RESTIC_PASSWORD_FILE env var: Path to file containing restic repo password
# - RESTIC_PASSWORD or prompt if missing
#
# Backs up: postgres, redis, craftvaria world, caddy config, pihole config, compose files

BACKUP_DIR="${BACKUP_DIR:-.}"
COMPOSE_DIR="${COMPOSE_DIR:-.}"
CRAFTVARIA_WORLD_DIR="${CRAFTVARIA_WORLD_DIR:-appdata/craftvaria/world}"
CADDY_CONFIG_DIR="${CADDY_CONFIG_DIR:-config/caddy}"
PIHOLE_CONFIG_DIR="${PIHOLE_CONFIG_DIR:-appdata/pihole}"

# Verify environment
if [ -z "${RESTIC_REPOSITORY:-}" ]; then
  echo "Error: RESTIC_REPOSITORY not set. Example: b2:bucket-name:/path"
  exit 1
fi

if [ -z "${RESTIC_PASSWORD_FILE:-}" ] && [ -z "${RESTIC_PASSWORD:-}" ]; then
  echo "Error: RESTIC_PASSWORD_FILE or RESTIC_PASSWORD not set"
  exit 1
fi

export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "[$(date)] Starting homelab backup..."

# 1. Postgres dumps (all databases)
echo "[$(date)] Backing up Postgres databases..."
for db in postgres craftvaria lucky; do
  docker exec homelab-postgres-1 pg_dump -U postgres "$db" > "$TEMP_DIR/$db.sql" 2>/dev/null || echo "Warning: Could not dump database $db"
done

# 2. Redis BGSAVE + copy dump.rdb
echo "[$(date)] Backing up Redis..."
docker exec homelab-redis-1 redis-cli BGSAVE > /dev/null 2>&1 || echo "Warning: Redis BGSAVE failed"
docker cp homelab-redis-1:/data/dump.rdb "$TEMP_DIR/redis-dump.rdb" 2>/dev/null || echo "Warning: Could not copy Redis dump"

# 3. Craftvaria world directory
if [ -d "$CRAFTVARIA_WORLD_DIR" ]; then
  echo "[$(date)] Backing up Craftvaria world..."
  cp -r "$CRAFTVARIA_WORLD_DIR" "$TEMP_DIR/craftvaria-world"
else
  echo "Warning: Craftvaria world dir not found at $CRAFTVARIA_WORLD_DIR"
fi

# 4. Caddy config
if [ -d "$CADDY_CONFIG_DIR" ]; then
  echo "[$(date)] Backing up Caddy config..."
  cp -r "$CADDY_CONFIG_DIR" "$TEMP_DIR/caddy-config"
else
  echo "Warning: Caddy config dir not found at $CADDY_CONFIG_DIR"
fi

# 5. Pi-hole config
if [ -d "$PIHOLE_CONFIG_DIR" ]; then
  echo "[$(date)] Backing up Pi-hole config..."
  cp -r "$PIHOLE_CONFIG_DIR" "$TEMP_DIR/pihole-config"
else
  echo "Warning: Pi-hole config dir not found at $PIHOLE_CONFIG_DIR"
fi

# 6. Docker Compose files
echo "[$(date)] Backing up Docker Compose files..."
cp -r "$COMPOSE_DIR"/compose "$TEMP_DIR/compose-files" 2>/dev/null || echo "Warning: Could not copy compose files"
cp "$COMPOSE_DIR/docker-compose.yml" "$TEMP_DIR/" 2>/dev/null || echo "Warning: Could not copy docker-compose.yml"

# 7. .env files (if present; add to .sops.yaml encrypted)
if [ -f "$COMPOSE_DIR/.env" ]; then
  cp "$COMPOSE_DIR/.env" "$TEMP_DIR/.env-backup" 2>/dev/null || echo "Warning: Could not copy .env"
fi

# 8. Restic backup
echo "[$(date)] Running restic backup..."
restic backup "$TEMP_DIR" \
  --exclude=".git" \
  --exclude="node_modules" \
  --exclude="*.log" \
  --exclude="tmp/" \
  -o b2.connections=10

# 9. Prune old snapshots (keep last 7 daily, 4 weekly, 12 monthly)
echo "[$(date)] Pruning old snapshots..."
restic forget \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 12 \
  --prune

echo "[$(date)] Backup completed successfully"
