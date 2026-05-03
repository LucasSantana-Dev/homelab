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

for REPO in $REPOS; do
    SHORT="${REPO#*/}"
    PROMPT="PR triage for ${REPO}.
gh pr list --repo ${REPO} --json number,title,isDraft,createdAt,statusCheckRollup,reviewDecision --limit 20
For each non-draft PR output one line:
  MERGE_READY: #N title
  STALE: #N title (N days)
  BLOCKED: #N title (reason)
If none open: NO_OPEN_PRS. No mutations."

    RESULT=$(ssh agent-box bash -c "
      source /etc/profile.d/agent-env.sh
      unset ANTHROPIC_API_KEY CLAUDE_API_KEY
      cd /workspace/${SHORT} 2>/dev/null || true
      claude -p '$PROMPT' --dangerously-skip-permissions --allowedTools 'Bash' 2>&1
    " 2>/dev/null) || RESULT="ERROR: SSH failed"

    echo "[${SHORT}] $RESULT"

    READY=$(echo "$RESULT" | grep 'MERGE_READY:' | sed "s/MERGE_READY: /✅ [${SHORT}] /" | head -3 || true)
    STALE=$(echo "$RESULT" | grep 'STALE:' | sed "s/STALE: /⏳ [${SHORT}] /" | head -3 || true)
    [[ -n "$READY" ]] && ALL_READY="${ALL_READY}${READY}
"
    [[ -n "$STALE" ]] && ALL_STALE="${ALL_STALE}${STALE}
"
done

if [[ -n "$ALL_READY" || -n "$ALL_STALE" ]]; then
    BODY=$(printf '%s%s' "$ALL_READY" "$ALL_STALE" | grep -v '^$' | head -10 | tr '\n' '|' | sed 's/|$//')
    $NOTIFY --title "📋 PR Triage" --body "$BODY" --urgency warn || true
    echo "[$(date)] Discord notified on actionable PRs."
fi
echo "[$(date)] PR triage complete."
