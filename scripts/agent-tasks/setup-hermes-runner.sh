#!/usr/bin/env bash
# setup-hermes-runner.sh — install and register the GitHub Actions self-hosted runner on the homelab host.
# Run once as luk-server on the homelab host after rotating the agent-box PAT (backlog B4).
#
# Prerequisites:
#   - AGENT_GITHUB_TOKEN set (or readable via SOPS — see common.sh)
#   - Outbound internet access from homelab host
#
# Usage: bash scripts/agent-tasks/setup-hermes-runner.sh
set -euo pipefail

RUNNER_DIR="/home/luk-server/actions-runner"
RUNNER_VERSION="2.321.0"
REPO_URL="https://github.com/LucasSantana-Dev/homelab"
RUNNER_LABELS="homelab,self-hosted"

# Load secrets (gets AGENT_GITHUB_TOKEN)
source "$(dirname "$0")/common.sh" 2>/dev/null || true

TOKEN="${AGENT_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
if [[ -z "$TOKEN" ]]; then
    echo "ERROR: AGENT_GITHUB_TOKEN not set. Rotate the PAT (backlog B4) and re-run."
    exit 1
fi

# Hard dependency: the registration-token step below parses JSON with jq.
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required but not installed. Install it (e.g. 'sudo apt-get install -y jq') and re-run."
    exit 1
fi

echo "--- [1/5] Creating runner directory ---"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

echo "--- [2/5] Downloading runner v${RUNNER_VERSION} ---"
curl -fsSL \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
    -o runner.tar.gz
tar -xzf runner.tar.gz
rm runner.tar.gz
echo "Runner binary ready."

echo "--- [3/5] Getting registration token ---"
REG_TOKEN=$(curl -sf -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/LucasSantana-Dev/homelab/actions/runners/registration-token" \
    | jq -r .token)

if [[ -z "$REG_TOKEN" || "$REG_TOKEN" == "null" ]]; then
    echo "ERROR: Could not get registration token. Check that the PAT has 'repo' scope."
    exit 1
fi

echo "--- [4/5] Configuring runner ---"
./config.sh \
    --url "$REPO_URL" \
    --token "$REG_TOKEN" \
    --name "homelab-runner" \
    --labels "$RUNNER_LABELS" \
    --unattended \
    --replace

echo "--- [5/5] Installing as systemd service ---"
sudo ./svc.sh install luk-server
sudo ./svc.sh start

echo ""
echo "Runner installed and running. Verify:"
echo "  systemctl status actions.runner.LucasSantana-Dev-homelab.homelab-runner.service"
echo "  gh api repos/LucasSantana-Dev/homelab/actions/runners --jq '.runners[].name'"
