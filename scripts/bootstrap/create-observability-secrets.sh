#!/usr/bin/env bash
# Create k8s secrets for observability namespace.
# Run this ONCE on a fresh cluster or after credential rotation.
# NEVER commit real values to git — set them as env vars before running.
#
# Required env vars:
#   GRAFANA_ADMIN_PASSWORD
#   GRAFANA_OAUTH_CLIENT_SECRET
#   ALERTMANAGER_DISCORD_WEBHOOK_URL
#
# Example:
#   export GRAFANA_ADMIN_PASSWORD="..."
#   export GRAFANA_OAUTH_CLIENT_SECRET="..."
#   export ALERTMANAGER_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
#   ./scripts/secrets/create-observability-secrets.sh

set -euo pipefail

KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

: "${GRAFANA_ADMIN_PASSWORD:?Required env var GRAFANA_ADMIN_PASSWORD not set}"
: "${GRAFANA_OAUTH_CLIENT_SECRET:?Required env var GRAFANA_OAUTH_CLIENT_SECRET not set}"
: "${ALERTMANAGER_DISCORD_WEBHOOK_URL:?Required env var ALERTMANAGER_DISCORD_WEBHOOK_URL not set}"

echo "Creating grafana-auth secret..."
KUBECONFIG="$KUBECONFIG" kubectl create secret generic grafana-auth \
  --namespace observability \
  --from-literal=admin-password="$GRAFANA_ADMIN_PASSWORD" \
  --from-literal=oauth-client-secret="$GRAFANA_OAUTH_CLIENT_SECRET" \
  --dry-run=client -o yaml | KUBECONFIG="$KUBECONFIG" kubectl apply -f -

echo "Creating alertmanager-discord secret..."
KUBECONFIG="$KUBECONFIG" kubectl create secret generic alertmanager-discord \
  --namespace observability \
  --from-literal=discord_webhook_url="$ALERTMANAGER_DISCORD_WEBHOOK_URL" \
  --dry-run=client -o yaml | KUBECONFIG="$KUBECONFIG" kubectl apply -f -

echo "Done. Secrets created in observability namespace."
