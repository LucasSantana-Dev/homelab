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
HOMEASSISTANT_CONFIG_DIR="${HOMEASSISTANT_CONFIG_DIR:-config/homeassistant/config}"
GATUS_CONFIG_DIR="${GATUS_CONFIG_DIR:-config/gatus}"
HOMEPAGE_CONFIG_DIR="${HOMEPAGE_CONFIG_DIR:-config/homepage}"
ALERTMANAGER_DATA_DIR="${ALERTMANAGER_DATA_DIR:-appdata/alertmanager}"
GATUS_VOLUME="${GATUS_VOLUME:-/var/lib/docker/volumes/homelab_gatus_data/_data}"
PORTAINER_VOLUME="${PORTAINER_VOLUME:-/var/lib/docker/volumes/homelab_portainer_data/_data}"
GRAFANA_VOLUME="${GRAFANA_VOLUME:-/var/lib/docker/volumes/compose_grafana_data/_data}"

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


# 6.5. Home Assistant config (post-k3s migration)
if [ -d "$HOMEASSISTANT_CONFIG_DIR" ]; then
  echo "[$(date)] Backing up Home Assistant config..."
  cp -r "$HOMEASSISTANT_CONFIG_DIR" "$TEMP_DIR/homeassistant-config" 2>/dev/null || sudo cp -r "$HOMEASSISTANT_CONFIG_DIR" "$TEMP_DIR/homeassistant-config" || echo "Warning: HA config copy failed"
else
  echo "Warning: Home Assistant config dir not found at $HOMEASSISTANT_CONFIG_DIR"
fi

# 6.6. Gatus config + data
if [ -d "$GATUS_CONFIG_DIR" ]; then
  cp -r "$GATUS_CONFIG_DIR" "$TEMP_DIR/gatus-config" 2>/dev/null || echo "Warning: gatus config copy failed"
else
  echo "Warning: Gatus config dir not found at $GATUS_CONFIG_DIR"
fi
if [ -d "$GATUS_VOLUME" ]; then
  echo "[$(date)] Backing up Gatus data..."
  sudo cp -r "$GATUS_VOLUME" "$TEMP_DIR/gatus-data" 2>/dev/null || echo "Warning: gatus volume copy failed"
else
  echo "Warning: Gatus docker volume not found at $GATUS_VOLUME"
fi

# 6.7. Homepage config
if [ -d "$HOMEPAGE_CONFIG_DIR" ]; then
  cp -r "$HOMEPAGE_CONFIG_DIR" "$TEMP_DIR/homepage-config" 2>/dev/null || echo "Warning: homepage config copy failed"
else
  echo "Warning: Homepage config dir not found at $HOMEPAGE_CONFIG_DIR"
fi

# 6.8. Portainer data (admin db, endpoints, stacks)
if [ -d "$PORTAINER_VOLUME" ]; then
  echo "[$(date)] Backing up Portainer data..."
  sudo cp -r "$PORTAINER_VOLUME" "$TEMP_DIR/portainer-data" 2>/dev/null || echo "Warning: portainer volume copy failed"
else
  echo "Warning: Portainer docker volume not found at $PORTAINER_VOLUME"
fi

# 6.9. Grafana data (dashboards + sqlite db, post-k3s migration)
if [ -d "$GRAFANA_VOLUME" ]; then
  echo "[$(date)] Backing up Grafana data..."
  sudo cp -r "$GRAFANA_VOLUME" "$TEMP_DIR/grafana-data" 2>/dev/null || echo "Warning: grafana volume copy failed"
else
  echo "Warning: Grafana docker volume not found at $GRAFANA_VOLUME"
fi

# 6.10. Alertmanager appdata (silence DB)
if [ -d "$ALERTMANAGER_DATA_DIR" ]; then
  sudo cp -r "$ALERTMANAGER_DATA_DIR" "$TEMP_DIR/alertmanager-data" 2>/dev/null || echo "Warning: alertmanager appdata copy failed"
else
  echo "Warning: Alertmanager data dir not found at $ALERTMANAGER_DATA_DIR"
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
