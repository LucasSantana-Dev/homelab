#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/dependabot-report-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting dependabot report..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

PROMPT='Dependabot PR safety report for LucasSantana-Dev/Lucky.
1. gh pr list --repo LucasSantana-Dev/Lucky --author app/dependabot --json number,title,statusCheckRollup,reviewDecision,mergeable --limit 20
2. For each dependabot PR:
   - SAFE_TO_MERGE: #N title — if all CI checks pass AND mergeable=MERGEABLE AND no CHANGES_REQUESTED
   - BLOCKED: #N title (reason) — if CI failing or merge conflict
3. If none open print: NO_DEPENDABOT_PRS
4. Do NOT merge any PRs. Read-only report only.'

RESULT=$(ssh agent-box bash -c "
  source /etc/profile.d/agent-env.sh
  unset ANTHROPIC_API_KEY CLAUDE_API_KEY
  cd /workspace/Lucky
  claude -p '$PROMPT' --dangerously-skip-permissions --allowedTools 'Bash' 2>&1
" 2>/dev/null) || RESULT="ERROR: SSH failed"

echo "$RESULT"

SAFE_COUNT=$(echo "$RESULT" | grep -c 'SAFE_TO_MERGE:' 2>/dev/null || echo "0")
BLOCKED_COUNT=$(echo "$RESULT" | grep -c 'BLOCKED:' 2>/dev/null || echo "0")

if [[ "$SAFE_COUNT" -gt 0 || "$BLOCKED_COUNT" -gt 0 ]]; then
    SAFE_LIST=$(echo "$RESULT" | grep 'SAFE_TO_MERGE:' | sed 's/SAFE_TO_MERGE: /✅ /' | head -8 | tr '\n' '|' | sed 's/|$//')
    BLOCKED_LIST=$(echo "$RESULT" | grep 'BLOCKED:' | sed 's/BLOCKED: /⛔ /' | head -5 | tr '\n' '|' | sed 's/|$//')
    BODY="${SAFE_LIST}${BLOCKED_LIST:+
$BLOCKED_LIST}"
    TITLE="📦 Dependabot: ${SAFE_COUNT} safe, ${BLOCKED_COUNT} blocked"
    URGENCY="warn"
    [[ "$BLOCKED_COUNT" -gt 0 ]] && URGENCY="alert"
    $NOTIFY --title "$TITLE" --body "$BODY" --urgency "$URGENCY" || true
    echo "[$(date)] Discord notified."
else
    echo "[$(date)] No dependabot PRs — no notification."
fi
echo "[$(date)] Dependabot report complete."
