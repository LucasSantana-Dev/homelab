#!/usr/bin/env bash
# Validate Helm release and endpoint availability after cutover.

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <namespace> <release> <url>"
  exit 1
fi

NAMESPACE="$1"
RELEASE="$2"
URL="$3"

echo "Helm release status"
helm status -n "${NAMESPACE}" "${RELEASE}"

echo
echo "Kubernetes rollout"
kubectl rollout status deployment -n "${NAMESPACE}" -l app.kubernetes.io/instance="${RELEASE}" --timeout=120s

echo
echo "HTTP check"
curl -fsSIL "${URL}" | head -n 5

echo
echo "Cutover checks complete"
