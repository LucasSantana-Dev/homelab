#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/homelab-drift-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting homelab drift detection..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

PROMPT='Homelab drift detection.
1. docker ps --format "{{.Names}}\t{{.Status}}\t{{.Image}}"
2. Read all /workspace/.drift-homelab/compose/*.yml and list every service name
3. UNEXPECTED: running containers with no matching compose service
4. MISSING: compose services (no profiles gate) with no running container
5. Print DRIFT_DETECTED: with sections, or NO_DRIFT if all match.
Read-only. Do not touch any containers.'

rc=0
RESULT=$(ssh agent-box bash -c "
  source /etc/profile.d/agent-env.sh
  unset ANTHROPIC_API_KEY CLAUDE_API_KEY
  # Own checkout pinned to release. The shared homelab checkout is the agent
  # gate's workdir: it can sit on a PR branch, and a pull there races the gate's
  # own git calls. If the checkout cannot be refreshed, claude does not run.
  # git errors go to stderr, which lands in this run's log.
  if ! { { [ -d /workspace/.drift-homelab/.git ] ||
      git clone -q --no-checkout https://github.com/LucasSantana-Dev/homelab.git /workspace/.drift-homelab; } &&
    cd /workspace/.drift-homelab &&
    git fetch -q origin release &&
    git checkout -q -f --detach FETCH_HEAD &&
    git clean -q -fdx; }; then
    echo 'ERROR: drift checkout refresh failed'
    exit 1
  fi
  claude -p '$PROMPT' --dangerously-skip-permissions --allowedTools 'Bash,Read' 2>&1
") || rc=$?
case $rc in
  0) ;;
  255) RESULT="ERROR: SSH failed" ;;
  *) RESULT="${RESULT:-ERROR: drift run failed (exit $rc)}" ;;
esac

echo "$RESULT"

if echo "$RESULT" | grep -q 'DRIFT_DETECTED:'; then
    DETAIL=$(echo "$RESULT" | grep -A10 'DRIFT_DETECTED:' | head -8 | sed 's/^/• /' | tr '\n' '|' | sed 's/|$//')
    $NOTIFY --title "⚠️ Homelab Drift Detected" --body "$DETAIL" --urgency alert || true
    echo "[$(date)] Discord alerted on drift."
else
    echo "[$(date)] No drift."
fi
echo "[$(date)] Homelab drift detection complete."
