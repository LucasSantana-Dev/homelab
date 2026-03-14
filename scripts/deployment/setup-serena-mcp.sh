#!/usr/bin/env bash
# Build a Serena MCP image with node + terraform and register it in Codex.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_TAG="local/serena-mcp:latest"
SERENA_CONFIG_DIR="${HOME}/.serena-config"

cd "${PROJECT_ROOT}"

echo "Building ${IMAGE_TAG}..."
docker build -f dockerfiles/serena-mcp.Dockerfile -t "${IMAGE_TAG}" dockerfiles

echo "Refreshing Codex MCP server 'serena'..."
if codex mcp get serena --json >/dev/null 2>&1; then
  codex mcp remove serena >/dev/null
fi

mkdir -p "${SERENA_CONFIG_DIR}"

codex mcp add serena -- \
  docker run -i --rm -u 1000:1000 \
  -v "${SERENA_CONFIG_DIR}:/workspaces/serena/config" \
  -v "${PROJECT_ROOT}:/workspaces/project" \
  "${IMAGE_TAG}" \
  serena start-mcp-server \
  --context codex \
  --enable-web-dashboard false \
  --project /workspaces/project

echo
echo "Running Serena project health-check (this can take a minute on first run)..."
docker run --rm -u 1000:1000 \
  -v "${SERENA_CONFIG_DIR}:/workspaces/serena/config" \
  -v "${PROJECT_ROOT}:/workspaces/project" \
  "${IMAGE_TAG}" \
  serena project health-check /workspaces/project

echo
echo "Serena MCP registration"
codex mcp list | sed -n '1,40p'
echo
codex mcp get serena --json
echo
echo "If an existing Codex chat still shows 'Transport closed' for Serena tools,"
echo "restart the Codex session so it reconnects with the refreshed MCP process."
