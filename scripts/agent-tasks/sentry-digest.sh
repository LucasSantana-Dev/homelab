#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/sentry-digest-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting Sentry digest..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

if [[ -z "${SENTRY_AUTH_TOKEN:-}" ]]; then
    echo "[$(date)] BLOCKED: SENTRY_AUTH_TOKEN not set in secrets — add it to agent-box.secrets.yaml.age"
    exit 0
fi

ORG="lucassantana-dev"
PROJECT="lucky"
SINCE=$(date -d '24 hours ago' --iso-8601=seconds)

ISSUES=$(curl -s \
    -H "Authorization: Bearer ${SENTRY_AUTH_TOKEN}" \
    "https://sentry.io/api/0/projects/${ORG}/${PROJECT}/issues/?query=is%3Aunresolved&sort=date&limit=10" \
    2>/dev/null) || ISSUES="[]"

NEW_COUNT=$(echo "$ISSUES" | jq --arg since "$SINCE" '[.[] | select(.firstSeen > $since)] | length' 2>/dev/null || echo "0")

if [[ "$NEW_COUNT" -gt 0 ]]; then
    SUMMARY=$(echo "$ISSUES" | jq -r --arg since "$SINCE" \
        '.[] | select(.firstSeen > $since) | "• \(.title) (\(.count) events)"' 2>/dev/null | head -5)
    $NOTIFY --title "🐛 Sentry: ${NEW_COUNT} New Issue(s)" --body "$SUMMARY" --urgency warn || true
    echo "[$(date)] Discord notified: $NEW_COUNT new issues."
else
    echo "[$(date)] No new Sentry issues in last 24h."
fi
echo "[$(date)] Sentry digest complete."
