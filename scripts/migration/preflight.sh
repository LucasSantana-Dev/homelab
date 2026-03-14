#!/usr/bin/env bash
# Preflight checks before applying the K3s/Terraform migration waves.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REQUIRED_CMDS=(docker kubectl helm terraform sops age codex)
MISSING=()

for cmd in "${REQUIRED_CMDS[@]}"; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    MISSING+=("${cmd}")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "Missing required commands: ${MISSING[*]}"
  exit 1
fi

echo "Required tools found"

echo
echo "Host memory snapshot"
free -h

echo
echo "Compose edge services"
docker ps --format '{{.Names}} {{.Status}}' | grep -E '^(nginx-proxy|cloudflared) ' || {
  echo "Expected compose edge services are not both running"
  exit 1
}

echo
echo "Codex MCP status"
codex mcp list | sed -n '1,30p'
codex mcp get serena --json >/dev/null

echo
echo "Kubernetes context and API checks"
CURRENT_CONTEXT="$(kubectl config current-context 2>/dev/null || true)"
if [[ -z "${CURRENT_CONTEXT}" ]]; then
  echo "kubectl current-context is empty. Run: make k3s-bootstrap"
  exit 1
fi
echo "kubectl context: ${CURRENT_CONTEXT}"
if ! kubectl get --raw=/readyz >/dev/null 2>&1; then
  echo "Kubernetes API is unreachable for context '${CURRENT_CONTEXT}'. Run: make k3s-bootstrap"
  exit 1
fi
echo "Kubernetes API is reachable"

echo
echo "Terraform formatting and validation"
(
  cd "${ROOT_DIR}/infra/terraform"
  terraform init -backend=false -input=false >/dev/null
  terraform fmt -check
  terraform validate
)

echo
echo "Helm lint checks"
helm lint "${ROOT_DIR}/k8s/helm/homepage"
helm lint "${ROOT_DIR}/k8s/helm/blackbox-exporter"
helm lint "${ROOT_DIR}/k8s/helm/filebrowser"

echo
echo "Preflight checks complete"
