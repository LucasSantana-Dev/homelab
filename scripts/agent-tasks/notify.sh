#!/usr/bin/env bash
# Post a Discord embed notification.
# Usage: notify.sh --title "..." --body "..." [--urgency info|warn|alert] [--dry-run]
set -euo pipefail

TITLE=""
BODY=""
URGENCY="info"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --title)    TITLE="$2";    shift 2 ;;
        --body)     BODY="$2";     shift 2 ;;
        --urgency)  URGENCY="$2";  shift 2 ;;
        --dry-run)  DRY_RUN=true;  shift ;;
        *) shift ;;
    esac
done

WEBHOOK="${AGENT_DISCORD_WEBHOOK:-}"
if [[ -z "$WEBHOOK" ]]; then
    echo "notify.sh: AGENT_DISCORD_WEBHOOK not set, skipping" >&2
    exit 0
fi

case "$URGENCY" in
    alert) COLOR=15548997 ;;  # red
    warn)  COLOR=16776960 ;;  # yellow
    *)     COLOR=5763719  ;;  # green
esac

# Truncate body to Discord embed limit (4096 chars)
BODY="${BODY:0:4000}"

PAYLOAD=$(printf '{"embeds":[{"title":"%s","description":"%s","color":%d,"footer":{"text":"agent-box • %s"}}]}' \
    "$(echo "$TITLE" | sed 's/"/\\"/g')" \
    "$(echo "$BODY"  | sed 's/"/\\"/g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//')" \
    "$COLOR" \
    "$(date '+%Y-%m-%d %H:%M')")

if [[ "$DRY_RUN" == true ]]; then
    echo "notify.sh: [dry-run] payload:"
    echo "$PAYLOAD"
    exit 0
fi

FAIL_LOG="/home/luk-server/agent-logs/notifications-failed.log"

# 3 attempts with exponential backoff (2s, 4s)
for ATTEMPT in 1 2 3; do
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$WEBHOOK" 2>/dev/null) || HTTP="000"

    if [[ "$HTTP" == "204" ]]; then
        echo "notify.sh: Discord notified (${URGENCY})"
        exit 0
    elif [[ "$HTTP" == "429" || "$HTTP" == "5"* ]]; then
        echo "notify.sh: HTTP $HTTP on attempt $ATTEMPT, retrying..." >&2
        [[ $ATTEMPT -lt 3 ]] && sleep $((ATTEMPT * 2))
    else
        break
    fi
done

echo "notify.sh: Discord notification failed (HTTP $HTTP)" >&2
echo "$(date '+%Y-%m-%d %H:%M:%S') HTTP=$HTTP title='$TITLE'" >> "$FAIL_LOG" 2>/dev/null || true
