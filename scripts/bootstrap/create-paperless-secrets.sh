#!/usr/bin/env bash
# Creates paperless Kubernetes secrets imperatively (never commit secrets to git)
# Usage: PAPERLESS_DBPASS=... PAPERLESS_SECRET_KEY=... PAPERLESS_ADMIN_PASSWORD=... ./create-paperless-secrets.sh
set -euo pipefail

NAMESPACE="apps"

: "${PAPERLESS_DBPASS:?PAPERLESS_DBPASS is required}"
: "${PAPERLESS_SECRET_KEY:?PAPERLESS_SECRET_KEY is required}"
: "${PAPERLESS_ADMIN_PASSWORD:?PAPERLESS_ADMIN_PASSWORD is required}"

kubectl create secret generic paperless-secrets \
  --namespace="${NAMESPACE}" \
  --from-literal=PAPERLESS_DBPASS="${PAPERLESS_DBPASS}" \
  --from-literal=PAPERLESS_SECRET_KEY="${PAPERLESS_KEY}" \
  --from-literal=PAPERLESS_ADMIN_PASSWORD="${PAPERLESS_ADMIN_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "paperless-secrets created/updated in namespace ${NAMESPACE}"
