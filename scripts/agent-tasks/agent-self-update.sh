#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/agent-self-update-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting agent self-update check..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

cd /home/luk-server/homelab

# Pull claude-env inside container for skills/settings refresh
ssh agent-box "
    if [ -d /home/agent/.claude-env ]; then
        cd /home/agent/.claude-env
        git pull --ff-only -q 2>/dev/null || true
    fi
" 2>/dev/null || true

# Report installed claude version
CURRENT_VERSION=$(ssh agent-box "claude --version 2>/dev/null | head -1" 2>/dev/null || echo "unknown")
echo "[$(date)] Claude version: $CURRENT_VERSION"

# Dockerfile change detection — use git if tracked, fall back to sha256
LAST_HASH_FILE="/home/luk-server/agent-logs/.last-dockerfile-hash"

if git ls-files --error-unmatch Dockerfile.agent-box > /dev/null 2>&1; then
    # File is tracked — check git for upstream changes
    git fetch -q 2>/dev/null || true
    CHANGED=$(git log --oneline HEAD..origin/HEAD -- Dockerfile.agent-box 2>/dev/null | wc -l | tr -d ' ')
    CHANGED_BY="git (${CHANGED} upstream commits)"
else
    # File untracked — use sha256 hash comparison
    CURRENT_HASH=$(sha256sum Dockerfile.agent-box 2>/dev/null | cut -d' ' -f1 || echo "unknown")
    LAST_HASH=$(cat "$LAST_HASH_FILE" 2>/dev/null || echo "")
    if [[ "$CURRENT_HASH" != "$LAST_HASH" ]]; then
        CHANGED=1
        echo "$CURRENT_HASH" > "$LAST_HASH_FILE"
    else
        CHANGED=0
    fi
    CHANGED_BY="sha256 hash"
fi

if [[ "$CHANGED" -gt 0 ]]; then
    echo "[$(date)] Dockerfile.agent-box changed (${CHANGED_BY}) — rebuild needed"
    $NOTIFY --title "🔧 Agent Rebuild Needed" \
        --body "Dockerfile.agent-box changed. Run: cd ~/homelab && docker compose -f compose/agent-box.yml build && docker compose -f compose/agent-box.yml up -d" \
        --urgency warn || true
else
    echo "[$(date)] Dockerfile unchanged — skills/settings refreshed only."
fi

echo "[$(date)] Agent self-update check complete."
