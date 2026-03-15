#!/usr/bin/env bash
# Quick Wave A+B deployment health check.
# Exit 0 = all healthy, exit 1 = degraded.

set -uo pipefail

export KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
export PATH="${HOME}/.local/bin:${PATH}"

RELEASES=("apps:homepage" "observability:blackbox-exporter" "apps:filebrowser" "apps:uptime-kuma" "apps:vaultwarden")
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

if command -v kubectl &>/dev/null; then
  restarts=$(kubectl get pods -A \
    -l 'app.kubernetes.io/instance in (homepage,blackbox-exporter)' \
    -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{"\n"}{end}' 2>/dev/null | awk '{s+=$1}END{print s+0}')
  echo "RESTARTS: ${restarts}"
  if [[ "${restarts}" -gt 0 ]]; then
    STATUS=1
  fi
fi

exit "${STATUS}"
