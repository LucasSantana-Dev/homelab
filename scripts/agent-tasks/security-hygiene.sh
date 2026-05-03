#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/security-hygiene-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting security hygiene scan..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

PROMPT='Security hygiene scan across /workspace repos.
1. For Lucky, homelab, Craftvaria: grep for hardcoded secrets (sk-ant-api, github_pat_, ghp_, AKIA) in ts/js/py/yml files excluding node_modules
2. npm audit --audit-level=high in /workspace/Lucky — report HIGH_VULNS count or VULNS_OK
3. Output SECURITY_CLEAN if nothing found, or SECURITY_ISSUES: with specifics.
Read-only.'

RESULT=$(ssh agent-box bash -c "
  source /etc/profile.d/agent-env.sh
  unset ANTHROPIC_API_KEY CLAUDE_API_KEY
  claude -p '$PROMPT' --dangerously-skip-permissions --allowedTools 'Bash' 2>&1
" 2>/dev/null) || RESULT="ERROR: SSH failed"

echo "$RESULT"

if echo "$RESULT" | grep -q 'SECURITY_ISSUES:'; then
    DETAIL=$(echo "$RESULT" | grep -A5 'SECURITY_ISSUES:' | head -6 | sed 's/^/• /' | tr '\n' '|' | sed 's/|$//')
    $NOTIFY --title "🔐 Security Issues Found" --body "$DETAIL" --urgency alert || true
    echo "[$(date)] Discord alerted on security issues."
else
    echo "[$(date)] Security clean."
fi
echo "[$(date)] Security hygiene scan complete."
