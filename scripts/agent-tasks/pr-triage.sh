#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/pr-triage-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting PR triage..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

REPOS="LucasSantana-Dev/Lucky LucasSantana-Dev/homelab"
ALL_READY=""
ALL_STALE=""
STALE_DAYS=14

for REPO in $REPOS; do
    SHORT="${REPO#*/}"

    PRS=$(run_on_agent "gh pr list --repo $REPO --state open --json number,title,isDraft,createdAt,statusCheckRollup,reviewDecision --limit 20") || PRS="[]"

    PR_COUNT=$(echo "$PRS" | jq 'length' 2>/dev/null || echo "0")
    if [[ "$PR_COUNT" == "0" ]]; then
        echo "[$SHORT] NO_OPEN_PRS"
        continue
    fi

    NOW_EPOCH=$(date +%s)
    while IFS= read -r pr_json; do
        number=$(echo "$pr_json" | jq -r '.number')
        title=$(echo "$pr_json" | jq -r '.title')
        is_draft=$(echo "$pr_json" | jq -r '.isDraft')
        created=$(echo "$pr_json" | jq -r '.createdAt')
        review=$(echo "$pr_json" | jq -r '.reviewDecision // ""')

        [[ "$is_draft" == "true" ]] && continue

        created_epoch=$(date -d "$created" +%s 2>/dev/null) || created_epoch=0
        age_days=$(( (NOW_EPOCH - created_epoch) / 86400 ))

        # Count check failures from statusCheckRollup
        failures=$(echo "$pr_json" | jq '[(.statusCheckRollup // []) | .[] | select(.conclusion == "FAILURE" or .state == "FAILURE")] | length' 2>/dev/null || echo "0")
        pending=$(echo "$pr_json" | jq '[(.statusCheckRollup // []) | .[] | select(.status == "IN_PROGRESS" or .status == "QUEUED" or .state == "PENDING")] | length' 2>/dev/null || echo "0")

        if [[ "$review" == "CHANGES_REQUESTED" ]] || [[ "$failures" -gt 0 ]]; then
            reason=""
            [[ "$review" == "CHANGES_REQUESTED" ]] && reason="changes requested"
            [[ "$failures" -gt 0 ]] && reason="${reason:+$reason, }${failures} CI failure(s)"
            echo "[$SHORT] BLOCKED: #${number} ${title} (${reason})"
        elif [[ "$pending" -gt 0 ]]; then
            echo "[$SHORT] PENDING: #${number} ${title} (${pending} checks running)"
        elif [[ "$age_days" -ge "$STALE_DAYS" ]]; then
            echo "[$SHORT] STALE: #${number} ${title} (${age_days} days)"
            ALL_STALE="${ALL_STALE}⏳ [${SHORT}] #${number} ${title} (${age_days}d)
"
        else
            echo "[$SHORT] MERGE_READY: #${number} ${title}"
            ALL_READY="${ALL_READY}✅ [${SHORT}] #${number} ${title}
"
        fi
    done < <(echo "$PRS" | jq -c '.[]')
done

ALL_READY="${ALL_READY%$'\n'}"
ALL_STALE="${ALL_STALE%$'\n'}"

if [[ -n "$ALL_READY" ]] || [[ -n "$ALL_STALE" ]]; then
    BODY=$(printf '%s\n%s' "$ALL_READY" "$ALL_STALE" | grep -v '^$' | head -10)
    $NOTIFY --title "📋 PR Triage" --body "$BODY" --urgency warn || true
    echo "[$(date)] Discord notified on actionable PRs."
fi
echo "[$(date)] PR triage complete."
