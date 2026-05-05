#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/container-health-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting container health check..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

# Containers intentionally stopped — do not alert on these
SKIP_PATTERN="craftvaria"

ISSUES=""

while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    state=$(echo "$line" | awk '{print $2}')
    health=$(echo "$line" | awk '{print $3}')

    [[ "$name" =~ $SKIP_PATTERN ]] && continue

    if [[ "$state" == "exited" ]] || [[ "$health" == "unhealthy" ]]; then
        ISSUES="${ISSUES}• ${name}: ${state}/${health}\n"
        echo "ISSUE: $name state=$state health=$health"
    fi
done < <(docker ps -a --format '{{.Names}} {{.State}} {{.Status}}' | \
    awk '{st=$2; h="ok"; if ($0 ~ /unhealthy/) h="unhealthy"; print $1, st, h}')

if [[ -n "$ISSUES" ]]; then
    BODY=$(printf '%b' "$ISSUES")
    $NOTIFY --title "🔴 Container Health Issues" --body "$BODY" --urgency alert || true
    echo "[$(date)] Discord alerted on container issues."
else
    echo "[$(date)] All containers healthy."
fi
echo "[$(date)] Container health check complete."
