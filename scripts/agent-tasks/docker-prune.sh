#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/docker-prune-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting Docker prune..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

before_images=$(docker system df --format '{{json .}}' | jq -r 'select(.Type=="Images") | .Reclaimable' 2>/dev/null || echo "?")
before_build=$(docker system df --format '{{json .}}' | jq -r 'select(.Type=="Build Cache") | .Reclaimable' 2>/dev/null || echo "?")

docker image prune -f 2>/dev/null
docker builder prune -f --keep-storage 2gb 2>/dev/null
docker volume prune -f 2>/dev/null

after_images=$(docker system df --format '{{json .}}' | jq -r 'select(.Type=="Images") | .Reclaimable' 2>/dev/null || echo "?")
after_build=$(docker system df --format '{{json .}}' | jq -r 'select(.Type=="Build Cache") | .Reclaimable' 2>/dev/null || echo "?")

BODY="Images reclaimable: ${before_images} → ${after_images}
Build cache reclaimable: ${before_build} → ${after_build}"

echo "$BODY"
$NOTIFY --title "🗑️ Docker Prune" --body "$BODY" --urgency info || true
echo "[$(date)] Docker prune complete."
