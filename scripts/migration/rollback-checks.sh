#!/usr/bin/env bash
# Validate rollback path for a Helm release.

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <namespace> <release> [revision]"
  exit 1
fi

NAMESPACE="$1"
RELEASE="$2"
REVISION="${3:-1}"

echo "Helm history"
helm history -n "${NAMESPACE}" "${RELEASE}"

echo
echo "Rollback command (dry info)"
echo "helm rollback -n ${NAMESPACE} ${RELEASE} ${REVISION}"

echo
echo "Compose edge fallback check"
docker ps --format '{{.Names}} {{.Status}}' | grep -E '^(caddy-lan|cloudflared) ' || {
  echo "Compose edge services (caddy-lan, cloudflared) are not both running"
  exit 1
}
