#!/usr/bin/env bash
# Shared bootstrap for agent-box task scripts.
# Source this at the top of each task script after set -euo pipefail and LOG_FILE setup.

NOTIFY="$(dirname "${BASH_SOURCE[0]}")/notify.sh"

source /etc/profile.d/agent-env.sh 2>/dev/null || true

# Decrypt secrets (AGENT_DISCORD_WEBHOOK, AGENT_GITHUB_TOKEN, etc.)
# Read KEY=value lines and export each value LITERALLY — no `eval`, so a secret
# whose value contains $, ;, spaces, or backticks can't break or inject the shell
# (this also bit benign tokens with special chars before). (#219)
# || true: task continues even if SOPS is unavailable; webhook warning below covers the gap
while IFS='=' read -r _k _v; do
    [[ $_k == [A-Za-z_]* ]] || continue   # skip blank/comment lines
    export "$_k=$_v"
done < <(SOPS_AGE_KEY_FILE=/home/luk-server/.config/sops/age/keys.txt \
    sops --config /dev/null --input-type yaml --output-type dotenv \
    -d /home/luk-server/homelab/secrets/agent-box.secrets.yaml.age 2>/dev/null) || true

export AGENT_DISCORD_WEBHOOK

if [[ -z "${AGENT_DISCORD_WEBHOOK:-}" ]]; then
    echo "[$(date)] WARNING: AGENT_DISCORD_WEBHOOK not set — notifications will be skipped" >&2
fi

# Run a command on agent-box via SSH, sourcing the container env first.
# Usage: run_on_agent "gh pr list --repo Org/Repo --json number"
run_on_agent() {
    # shellcheck disable=SC2029
    ssh agent-box "source /etc/profile.d/agent-env.sh && $(printf '%q' "$1")" 2>/dev/null
}
