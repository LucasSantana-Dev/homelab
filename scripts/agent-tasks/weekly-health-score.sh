#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/weekly-health-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting weekly health score..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

REPO="LucasSantana-Dev/Lucky"
SEVEN_DAYS_AGO=$(date -d '7 days ago' --iso-8601=seconds)

run_on_agent() {
    # shellcheck disable=SC2029
    ssh agent-box "source /etc/profile.d/agent-env.sh && $1" 2>/dev/null
}

# CI pass rate: last 14 runs on main
CI_JSON=$(run_on_agent "gh run list --repo $REPO --branch main --limit 14 --json status,conclusion,createdAt") || CI_JSON="[]"
CI_PASS=$(echo "$CI_JSON" | jq '[.[] | select(.conclusion == "success")] | length')
CI_TOTAL=$(echo "$CI_JSON" | jq 'length')
CI_FAIL=$(( CI_TOTAL - CI_PASS ))
CI_LINE="CI: ${CI_PASS}/${CI_TOTAL} runs passed"

# Merged PRs in last 7 days
MERGED_JSON=$(run_on_agent "gh pr list --repo $REPO --state merged --json mergedAt --limit 20") || MERGED_JSON="[]"
PRS_MERGED=$(echo "$MERGED_JSON" | jq --arg since "$SEVEN_DAYS_AGO" '[.[] | select(.mergedAt > $since)] | length')
PRS_MERGED_LINE="Merged: ${PRS_MERGED} this week"

# Open PRs
OPEN_JSON=$(run_on_agent "gh pr list --repo $REPO --state open --json number --limit 20") || OPEN_JSON="[]"
PRS_OPEN=$(echo "$OPEN_JSON" | jq 'length')
PRS_OPEN_LINE="Open PRs: ${PRS_OPEN}"

# Open bug issues
BUGS_JSON=$(run_on_agent "gh issue list --repo $REPO --state open --label bug --json number --limit 20") || BUGS_JSON="[]"
BUGS_OPEN=$(echo "$BUGS_JSON" | jq 'length')
BUGS_LINE="Bugs: ${BUGS_OPEN}"

echo "$CI_LINE"
echo "$PRS_MERGED_LINE"
echo "$PRS_OPEN_LINE"
echo "$BUGS_LINE"

# Health assessment — local arithmetic, no LLM needed
URGENCY="info"
if [[ "$CI_FAIL" -ge 3 ]] || [[ "$BUGS_OPEN" -ge 3 ]]; then
    ASSESSMENT="HEALTH_CRITICAL: ${CI_FAIL} CI failures, ${BUGS_OPEN} open bugs"
    URGENCY="alert"
elif [[ "$CI_FAIL" -ge 1 ]] || [[ "$BUGS_OPEN" -ge 1 ]]; then
    ASSESSMENT="HEALTH_WARN: ${CI_FAIL} CI failure(s), ${BUGS_OPEN} open bug(s)"
    URGENCY="warn"
else
    ASSESSMENT="HEALTH_GOOD: CI clean, no open bugs"
fi

echo "$ASSESSMENT"

BODY="$(printf '%s\n%s\n%s\n%s\n\n%s'     "$CI_LINE" "$PRS_MERGED_LINE" "$PRS_OPEN_LINE" "$BUGS_LINE" "$ASSESSMENT")"

$NOTIFY --title "📊 Lucky Weekly Health" --body "$BODY" --urgency "$URGENCY" || true
echo "[$(date)] Weekly health score complete."
