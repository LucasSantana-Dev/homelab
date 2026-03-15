#!/usr/bin/env bash
# Reduce Minecraft server heap from 4G to 2G when no players are online.
# Safe to run automatically; aborts if players are present.

set -euo pipefail

CRAFTVARIA_DIR="/home/luk-server/Craftvaria"
ENV_FILE="${CRAFTVARIA_DIR}/.env"
CONTAINER="craftvaria-minecraft"
TARGET_MEMORY="2G"

if ! docker inspect "${CONTAINER}" --format '{{.State.Status}}' 2>/dev/null | grep -q running; then
  echo "Container ${CONTAINER} is not running; nothing to do"
  exit 0
fi

PLAYERS=$(docker exec "${CONTAINER}" rcon-cli list 2>/dev/null | grep -Eo 'There are [0-9]+' | grep -Eo '[0-9]+' || echo "0")
if [[ "${PLAYERS}" -gt 0 ]]; then
  echo "SKIP: ${PLAYERS} player(s) online — will not restart now"
  exit 0
fi

CURRENT=$(grep "^MINECRAFT_MEMORY=" "${ENV_FILE}" | cut -d= -f2-)
if [[ "${CURRENT}" == "${TARGET_MEMORY}" ]]; then
  echo "Already at ${TARGET_MEMORY}; nothing to do"
  exit 0
fi

echo "Reducing Minecraft heap: ${CURRENT} → ${TARGET_MEMORY}"
sed -i "s/^MINECRAFT_MEMORY=.*/MINECRAFT_MEMORY=${TARGET_MEMORY}/" "${ENV_FILE}"
docker compose -f "${CRAFTVARIA_DIR}/docker-compose.yml" \
  --env-file "${CRAFTVARIA_DIR}/.env" \
  restart minecraft 2>&1 || docker restart "${CONTAINER}" 2>&1

echo "Done. New heap: ${TARGET_MEMORY}"
