#!/usr/bin/env bash
# Creates nextcloud Kubernetes secrets imperatively (never commit secrets to git)
# Usage: MYSQL_PASSWORD=... MYSQL_ROOT_PASSWORD=... ./create-nextcloud-secrets.sh
set -euo pipefail

NAMESPACE="apps"

: "${MYSQL_PASSWORD:?MYSQL_PASSWORD is required}"
: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required}"

kubectl create secret generic nextcloud-secrets \
  --namespace="${NAMESPACE}" \
  --from-literal=MYSQL_PASSWORD="${MYSQL_PASSWORD}" \
  --from-literal=MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "nextcloud-secrets created/updated in namespace ${NAMESPACE}"
