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
    PROMPT="CI health check for ${REPO}.
1. gh run list --repo ${REPO} --branch main --limit 3 --json status,conclusion,name,createdAt
2. gh pr list --repo ${REPO} --json number,title,statusCheckRollup --limit 10
3. For any failed run: gh run view <id> --repo ${REPO} --log-failed 2>/dev/null | head -20
Output CI_HEALTHY if all green, or one line per failure: CI_FAILING: <branch/PR> — <check> — <error>"

    RESULT=$(ssh agent-box bash -c "
      source /etc/profile.d/agent-env.sh
      unset ANTHROPIC_API_KEY CLAUDE_API_KEY
      cd /workspace/${SHORT} 2>/dev/null || true
      git fetch -q 2>/dev/null || true
      claude -p '$PROMPT' --dangerously-skip-permissions --allowedTools 'Bash' 2>&1
    " 2>/dev/null) || RESULT="ERROR: SSH failed"

    echo "[${SHORT}] $RESULT"

    if echo "$RESULT" | grep -q 'CI_FAILING:'; then
        FAILING=$(echo "$RESULT" | grep 'CI_FAILING:' | head -5 | sed "s/CI_FAILING: /• [${SHORT}] /" | tr '\n' '|' | sed 's/|$//')
        ALL_FAILING="${ALL_FAILING}${FAILING}|"
    fi
done

ALL_FAILING="${ALL_FAILING%|}"

if [[ -n "$ALL_FAILING" ]]; then
    BODY="${ALL_FAILING//|/$'\n'}"
    $NOTIFY --title "🔴 CI Failures" --body "$BODY" --urgency alert || true
    echo "[$(date)] Discord alerted on CI failures."
else
    echo "[$(date)] CI healthy across all repos."
fi
echo "[$(date)] CI watch complete."
