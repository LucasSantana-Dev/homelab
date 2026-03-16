#!/usr/bin/env bash
# Create authentik secrets in k8s (never store in git)
# Usage: AUTHENTIK_POSTGRESQL__PASSWORD=... AUTHENTIK_SECRET_KEY=... bash scripts/bootstrap/create-authentik-secrets.sh
set -euo pipefail

: "${AUTHENTIK_POSTGRESQL__PASSWORD:?Required}"
: "${AUTHENTIK_SECRET_KEY:?Required}"

NAMESPACE=apps
SECRET_NAME=authentik-secrets

if KUBECONFIG=~/.kube/config kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &>/dev/null; then
  echo "Secret $SECRET_NAME already exists — deleting and recreating"
  KUBECONFIG=~/.kube/config kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE"
fi

KUBECONFIG=~/.kube/config kubectl create secret generic "$SECRET_NAME" \
  --namespace="$NAMESPACE" \
  --from-literal="AUTHENTIK_POSTGRESQL__PASSWORD=${AUTHENTIK_POSTGRESQL__PASSWORD}" \
  --from-literal="AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}"

echo "Secret $SECRET_NAME created in namespace $NAMESPACE"
