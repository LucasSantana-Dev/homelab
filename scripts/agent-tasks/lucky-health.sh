#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/lucky-health-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting Lucky health check..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

HEALTH_URL="https://lucky-api.lucassantana.tech/api/health"
HTTP_CODE=$(curl -s -o /tmp/lucky-health-response.json -w "%{http_code}" \
    --max-time 15 --retry 2 --retry-delay 3 \
    -H "Accept: application/json" \
    "$HEALTH_URL" 2>/dev/null) || HTTP_CODE="000"

RESPONSE=$(cat /tmp/lucky-health-response.json 2>/dev/null || echo "{}")
rm -f /tmp/lucky-health-response.json

echo "[$(date)] Health check: HTTP $HTTP_CODE"
echo "Response: $RESPONSE"

if [[ "$HTTP_CODE" == "200" ]]; then
    echo "[$(date)] Lucky healthy — no notification."
else
    if [[ "$HTTP_CODE" == "000" ]]; then
        DETAIL="Unreachable (connection timeout/refused)"
    else
        DETAIL="HTTP $HTTP_CODE — ${RESPONSE:0:200}"
    fi
    $NOTIFY --title "🔴 Lucky API Down" --body "$DETAIL" --urgency alert || true
    echo "[$(date)] Discord alerted."
fi
echo "[$(date)] Lucky health check complete."
