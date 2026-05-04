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
PROJECTS="openclaw-sandbox lucky"
SINCE=$(date -d '24 hours ago' --iso-8601=seconds)

ALL_NEW=0
ALL_SUMMARY=""

for PROJECT in $PROJECTS; do
    ISSUES=$(curl -s \
        -H "Authorization: Bearer ${SENTRY_AUTH_TOKEN}" \
        "https://sentry.io/api/0/projects/${ORG}/${PROJECT}/issues/?query=is%3Aunresolved&sort=date&limit=10" \
        2>/dev/null) || ISSUES="[]"

    NEW_COUNT=$(echo "$ISSUES" | jq --arg since "$SINCE" '[.[] | select(.firstSeen > $since)] | length' 2>/dev/null || echo "0")
    echo "[$PROJECT] $NEW_COUNT new issue(s)"

    if [[ "$NEW_COUNT" -gt 0 ]]; then
        SUMMARY=$(echo "$ISSUES" | jq -r --arg since "$SINCE" \
            '.[] | select(.firstSeen > $since) | "• \(.title) (\(.count) events)"' 2>/dev/null | head -3)
        ALL_NEW=$(( ALL_NEW + NEW_COUNT ))
        ALL_SUMMARY="${ALL_SUMMARY}[${PROJECT}]\n${SUMMARY}\n"
    fi
done

if [[ "$ALL_NEW" -gt 0 ]]; then
    BODY=$(printf '%b' "$ALL_SUMMARY")
    $NOTIFY --title "🐛 Sentry: ${ALL_NEW} New Issue(s)" --body "$BODY" --urgency warn || true
    echo "[$(date)] Discord notified: $ALL_NEW new issues."
else
    echo "[$(date)] No new Sentry issues in last 24h."
fi
echo "[$(date)] Sentry digest complete."
