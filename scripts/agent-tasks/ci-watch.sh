#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/ci-watch-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting CI watch..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

REPOS="LucasSantana-Dev/Lucky LucasSantana-Dev/homelab"
ALL_FAILING=""

for REPO in $REPOS; do
    SHORT="${REPO#*/}"

    # Last 3 runs on main
    RUNS=$(run_on_agent "gh run list --repo $REPO --branch main --limit 3 --json status,conclusion,name,headBranch") || RUNS="[]"
    FAILING_RUNS=$(echo "$RUNS" | jq -r '.[] | select(.conclusion == "failure") | "CI_FAILING: \(.name) on \(.headBranch)"' 2>/dev/null || true)

    # Open PR check-rollup
    PR_FAILURES=$(run_on_agent "gh pr list --repo $REPO --state open --json number,title,statusCheckRollup --limit 10") || PR_FAILURES="[]"
    FAILING_PRS=$(echo "$PR_FAILURES" | jq -r '
        .[] | . as $pr |
        (.statusCheckRollup // []) |
        map(select(.conclusion == "FAILURE" or .state == "FAILURE")) |
        select(length > 0) |
        "CI_FAILING: PR #\($pr.number) \($pr.title)"
    ' 2>/dev/null || true)

    COMBINED=$(printf '%s\n%s' "$FAILING_RUNS" "$FAILING_PRS" | grep -v '^$' || true)

    if [[ -z "$COMBINED" ]]; then
        echo "[$SHORT] CI_HEALTHY"
    else
        echo "[$SHORT] $COMBINED"
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            ALL_FAILING="${ALL_FAILING}• [${SHORT}] ${line#CI_FAILING: }
"
        done <<< "$COMBINED"
    fi
done

ALL_FAILING="${ALL_FAILING%$'\n'}"

if [[ -n "$ALL_FAILING" ]]; then
    $NOTIFY --title "🔴 CI Failures" --body "$ALL_FAILING" --urgency alert || true
    echo "[$(date)] Discord alerted on CI failures."
else
    echo "[$(date)] CI healthy across all repos."
fi
echo "[$(date)] CI watch complete."
