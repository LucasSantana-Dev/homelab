#!/usr/bin/env bash
# Register Forge Space MCP Gateway in Codex MCP list using the gateway's stdio wrapper.

set -euo pipefail

FORGE_MCP_WRAPPER_IMAGE="${FORGE_MCP_WRAPPER_IMAGE:-ghcr.io/ibm/mcp-context-forge:1.0.0-BETA-2}"
FORGE_MCP_SERVER_URL="${FORGE_MCP_SERVER_URL:-http://127.0.0.1:4444/servers/<UUID>/mcp}"
FORGE_MCP_JWT="${FORGE_MCP_JWT:-}"

usage() {
  cat <<'EOF'
Usage:
  FORGE_MCP_SERVER_URL=http://127.0.0.1:4444/servers/<UUID>/mcp \
  FORGE_MCP_JWT=<jwt-token> \
  ./scripts/deployment/setup-forge-space-mcp.sh

Notes:
  - Replace <UUID> with a virtual server UUID from Forge MCP Gateway admin UI.
  - FORGE_MCP_JWT is required when gateway auth is enabled.
  - Optional override: FORGE_MCP_WRAPPER_IMAGE=ghcr.io/ibm/mcp-context-forge:1.0.0-BETA-2
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI not found" >&2
  exit 1
fi

if [[ "${FORGE_MCP_SERVER_URL}" == *"<UUID>"* ]]; then
  echo "FORGE_MCP_SERVER_URL still contains <UUID>. Set a real server URL." >&2
  exit 1
fi

if [[ ! "${FORGE_MCP_SERVER_URL}" =~ ^https?:// ]]; then
  echo "FORGE_MCP_SERVER_URL must start with http:// or https://" >&2
  exit 1
fi

if [[ -z "${FORGE_MCP_JWT}" ]]; then
  echo "FORGE_MCP_JWT is empty. Provide a token or disable auth in gateway settings." >&2
  exit 1
fi

AUTH_HEADER="Bearer ${FORGE_MCP_JWT}"

echo "Registering forge-space MCP server in Codex..."
codex mcp remove forge-space >/dev/null 2>&1 || true
codex mcp add forge-space -- \
  docker run -i --rm --network host \
  "${FORGE_MCP_WRAPPER_IMAGE}" \
  python -m mcpgateway.wrapper \
  "--url=${FORGE_MCP_SERVER_URL}" \
  "--auth=${AUTH_HEADER}"

echo "Validating registration..."
codex mcp get forge-space --json >/dev/null
codex mcp list | sed -n '1,40p'
echo "Forge Space MCP registration complete."
