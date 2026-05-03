#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/lucky-release-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting Lucky release check..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

PROMPT='Lucky release check.
1. Run: git log $(git describe --tags --abbrev=0)..HEAD --oneline
2. Count non-chore/docs commits. If fewer than 3 print NOTHING_TO_RELEASE and stop.
3. If release-worthy: list feat/fix titles (one per line prefixed with type:), suggest next semver, last line must be: RELEASE_READY: vX.Y.Z
4. Do NOT create tags, push, bump version, or modify files.'

RESULT=$(ssh agent-box bash -c "
  source /etc/profile.d/agent-env.sh
  unset ANTHROPIC_API_KEY CLAUDE_API_KEY
  cd /workspace/Lucky
  git fetch --tags -q
  claude -p '$PROMPT' --dangerously-skip-permissions --allowedTools 'Bash' 2>&1
" 2>/dev/null) || RESULT="ERROR: SSH failed"

echo "$RESULT"

if echo "$RESULT" | grep -q 'RELEASE_READY:'; then
    VERSION=$(echo "$RESULT" | grep -oE 'RELEASE_READY: v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | awk '{print $2}' || echo "next")
    $NOTIFY \
        --title "🚀 Lucky Release Ready: ${VERSION}" \
        --body "Run /version-bump to ship ${VERSION}" \
        --urgency info || true
    echo "[$(date)] Discord notified."
fi
echo "[$(date)] Lucky release check complete."
