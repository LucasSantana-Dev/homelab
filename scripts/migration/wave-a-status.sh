#!/usr/bin/env bash
# k3s migration health check — Waves A through D.
# Exit 0 = all healthy, exit 1 = degraded.

set -uo pipefail

export KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
export PATH="${HOME}/.local/bin:${PATH}"

RELEASES=(
  "apps:homepage"
  "observability:blackbox-exporter"
  "apps:filebrowser"
  "apps:uptime-kuma"
  "apps:vaultwarden"
  "apps:n8n"
  "apps:pihole"
)
STATUS=0

for entry in "${RELEASES[@]}"; do
  ns="${entry%%:*}"
  release="${entry##*:}"

  ready=$(kubectl get deploy -n "${ns}" \
    -l "app.kubernetes.io/instance=${release}" \
    -o jsonpath='{.items[0].status.readyReplicas}' 2>/dev/null)
  desired=$(kubectl get deploy -n "${ns}" \
    -l "app.kubernetes.io/instance=${release}" \
    -o jsonpath='{.items[0].spec.replicas}' 2>/dev/null)

  if [[ "${ready:-0}" -eq "${desired:-1}" && "${ready:-0}" -gt 0 ]]; then
    echo "OK  ${ns}/${release} (${ready}/${desired} ready)"
  else
    echo "BAD ${ns}/${release} (${ready:-0}/${desired:-?} ready)"
    STATUS=1
  fi
done

echo ""
echo "Total restarts across all migrated pods:"
restarts=$(kubectl get pods -n apps -n observability \
  -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{"\n"}{end}' 2>/dev/null | awk '{s+=$1}END{print s+0}')
echo "RESTARTS: ${restarts}"
if [[ "${restarts}" -gt 5 ]]; then
  STATUS=1
fi

exit "${STATUS}"
