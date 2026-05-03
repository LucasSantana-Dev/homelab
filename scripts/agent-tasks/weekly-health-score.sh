#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/weekly-health-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting weekly health score..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

PROMPT='Weekly health summary across LucasSantana-Dev/Lucky.
1. gh run list --repo LucasSantana-Dev/Lucky --branch main --limit 14 --json status,conclusion,createdAt — count successes vs failures in last 7 days
2. gh pr list --repo LucasSantana-Dev/Lucky --state merged --json mergedAt --limit 20 — count PRs merged in last 7 days
3. gh pr list --repo LucasSantana-Dev/Lucky --state open --json number --limit 20 — count currently open PRs
4. gh issue list --repo LucasSantana-Dev/Lucky --state open --label bug --json number --limit 20 — count open bug issues
5. Output exactly these lines:
   CI_PASS_RATE: X/Y runs passed
   PRS_MERGED: N this week
   PRS_OPEN: N
   BUGS_OPEN: N
6. One-line assessment: HEALTH_GOOD, HEALTH_WARN, or HEALTH_CRITICAL with brief reason.'

RESULT=$(ssh agent-box bash -c "
  source /etc/profile.d/agent-env.sh
  unset ANTHROPIC_API_KEY CLAUDE_API_KEY
  cd /workspace/Lucky
  claude -p '$PROMPT' --dangerously-skip-permissions --allowedTools 'Bash' 2>&1
" 2>/dev/null) || RESULT="ERROR: SSH failed"

echo "$RESULT"

CI_LINE=$(echo "$RESULT" | grep 'CI_PASS_RATE:' | head -1 | sed 's/CI_PASS_RATE: /CI: /' || echo "CI: unknown")
PRS_MERGED=$(echo "$RESULT" | grep 'PRS_MERGED:' | head -1 | sed 's/PRS_MERGED: /Merged: /' || echo "Merged: ?")
PRS_OPEN=$(echo "$RESULT" | grep 'PRS_OPEN:' | head -1 | sed 's/PRS_OPEN: /Open PRs: /' || echo "Open PRs: ?")
BUGS=$(echo "$RESULT" | grep 'BUGS_OPEN:' | head -1 | sed 's/BUGS_OPEN: /Bugs: /' || echo "Bugs: ?")
ASSESSMENT=$(echo "$RESULT" | grep -E 'HEALTH_(GOOD|WARN|CRITICAL)' | head -1 || echo "HEALTH_UNKNOWN")

BODY="$(printf '%s\n%s\n%s\n%s\n\n%s' "$CI_LINE" "$PRS_MERGED" "$PRS_OPEN" "$BUGS" "$ASSESSMENT")"

URGENCY="info"
echo "$ASSESSMENT" | grep -q 'HEALTH_WARN' && URGENCY="warn" || true
echo "$ASSESSMENT" | grep -q 'HEALTH_CRITICAL' && URGENCY="alert" || true

$NOTIFY --title "📊 Lucky Weekly Health" --body "$BODY" --urgency "$URGENCY" || true
echo "[$(date)] Weekly health score complete."
