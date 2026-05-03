#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/workspace-sync-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting workspace sync..."

REPOS="Lucky homelab Craftvaria"
RESULTS=""

for REPO in $REPOS; do
    OUTPUT=$(ssh agent-box "
        if [ -d /workspace/$REPO/.git ]; then
            cd /workspace/$REPO
            BEFORE=\$(git rev-parse HEAD 2>/dev/null)
            git fetch --tags -q 2>/dev/null || true
            git pull --ff-only -q 2>/dev/null || true
            AFTER=\$(git rev-parse HEAD 2>/dev/null)
            if [ \"\$BEFORE\" != \"\$AFTER\" ]; then
                COUNT=\$(git log --oneline \"\$BEFORE..\$AFTER\" 2>/dev/null | wc -l | tr -d ' ')
                echo \"UPDATED: $REPO +\${COUNT} commits\"
            else
                echo \"CURRENT: $REPO\"
            fi
        else
            echo \"MISSING: $REPO\"
        fi
    " 2>/dev/null) || OUTPUT="ERROR: $REPO"
    echo "$OUTPUT"
    RESULTS="$RESULTS
$OUTPUT"
done

echo "[$(date)] Workspace sync complete."
