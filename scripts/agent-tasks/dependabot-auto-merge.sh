#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/dependabot-auto-merge-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting Dependabot auto-merge..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

REPO="LucasSantana-Dev/Lucky"
MERGED=0
SKIPPED=0

PRS=$(run_on_agent "gh pr list --repo $REPO --author app/dependabot --state open --json number,title,statusCheckRollup,reviewDecision,labels --limit 30") || PRS="[]"
PR_COUNT=$(echo "$PRS" | jq 'length' 2>/dev/null || echo "0")

echo "Found $PR_COUNT open Dependabot PRs"

while IFS= read -r pr_json; do
    number=$(echo "$pr_json" | jq -r '.number')
    title=$(echo "$pr_json" | jq -r '.title')
    review=$(echo "$pr_json" | jq -r '.reviewDecision // ""')

    # Never auto-merge if changes are requested
    if [[ "$review" == "CHANGES_REQUESTED" ]]; then
        echo "SKIP #$number: changes requested — $title"
        (( SKIPPED++ )) || true
        continue
    fi

    # Skip major version bumps (title contains "from X to Y" where major differs)
    if echo "$title" | grep -qE 'from [0-9]+\. to [0-9]+\.'; then
        old_major=$(echo "$title" | grep -oE 'from [0-9]+' | grep -oE '[0-9]+')
        new_major=$(echo "$title" | grep -oE 'to [0-9]+\.' | grep -oE '^[0-9]+')
        if [[ "$old_major" != "$new_major" ]]; then
            echo "SKIP #$number: major bump ($old_major→$new_major) — $title"
            (( SKIPPED++ )) || true
            continue
        fi
    fi

    # All checks must pass
    failures=$(echo "$pr_json" | jq '[(.statusCheckRollup // []) | .[] | select(.conclusion == "FAILURE" or .state == "FAILURE")] | length' 2>/dev/null || echo "1")
    pending=$(echo "$pr_json" | jq '[(.statusCheckRollup // []) | .[] | select(.status == "IN_PROGRESS" or .status == "QUEUED" or .state == "PENDING")] | length' 2>/dev/null || echo "1")

    if [[ "$failures" -gt 0 ]]; then
        echo "SKIP #$number: $failures CI failure(s) — $title"
        (( SKIPPED++ )) || true
        continue
    fi
    if [[ "$pending" -gt 0 ]]; then
        echo "SKIP #$number: $pending checks pending — $title"
        (( SKIPPED++ )) || true
        continue
    fi

    echo "MERGING #$number — $title"
    if run_on_agent "gh pr merge $number --repo $REPO --squash --auto" > /dev/null 2>&1; then
        echo "MERGED #$number"
        (( MERGED++ )) || true
    else
        echo "MERGE_FAILED #$number"
        (( SKIPPED++ )) || true
    fi
done < <(echo "$PRS" | jq -c '.[]')

echo "Result: merged=$MERGED skipped=$SKIPPED"

if [[ "$MERGED" -gt 0 ]]; then
    $NOTIFY --title "✅ Dependabot Auto-Merge" \
        --body "Merged ${MERGED} PR(s), skipped ${SKIPPED}" \
        --urgency info || true
fi
echo "[$(date)] Dependabot auto-merge complete."
