#!/usr/bin/env bash
# Deploy Wave A services and enforce a burn-in stability gate.

set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
export PATH="${HOME}/.local/bin:${PATH}"

BURNIN_MINUTES="${BURNIN_MINUTES:-30}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-60}"
LOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/logs/migration"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/wave-a-gate-${TIMESTAMP}.log"

mkdir -p "${LOG_DIR}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

usage() {
  cat <<'EOF'
Usage: wave-a-gate.sh [--burnin-minutes N] [--interval-seconds N]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --burnin-minutes)
      BURNIN_MINUTES="$2"
      shift 2
      ;;
    --interval-seconds)
      CHECK_INTERVAL_SECONDS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

check_release_ready() {
  local namespace="$1"
  local release="$2"

  local deployments
  deployments="$(kubectl get deploy -n "${namespace}" -l app.kubernetes.io/instance="${release}" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')"
  if [[ -z "${deployments}" ]]; then
    log "No deployments found for ${release} in ${namespace}"
    return 1
  fi

  while IFS= read -r deploy; do
    [[ -z "${deploy}" ]] && continue
    kubectl rollout status deployment/"${deploy}" -n "${namespace}" --timeout=120s >/dev/null
  done <<< "${deployments}"

  local service
  service="$(kubectl get svc -n "${namespace}" -l app.kubernetes.io/instance="${release}" -o jsonpath='{.items[0].metadata.name}')"
  if [[ -z "${service}" ]]; then
    log "No service found for ${release} in ${namespace}"
    return 1
  fi

  local endpoints
  endpoints="$(kubectl get endpoints -n "${namespace}" "${service}" -o jsonpath='{.subsets[*].addresses[*].ip}')"
  if [[ -z "${endpoints}" ]]; then
    log "Service ${service} has no ready endpoints"
    return 1
  fi

  log "Release ${release} in ${namespace} is ready (service=${service})"
}

rollback_hint() {
  log "Rollback commands:"
  log "  helm rollback -n apps homepage 1"
  log "  helm rollback -n observability blackbox-exporter 1"
  log "  make wave-rollback NS=apps RELEASE=homepage REV=1"
  log "  make wave-rollback NS=observability RELEASE=blackbox-exporter REV=1"
}

log "Deploying Wave A releases"
helm upgrade --install homepage ./k8s/helm/homepage -n apps --create-namespace | tee -a "${LOG_FILE}"
helm upgrade --install blackbox-exporter ./k8s/helm/blackbox-exporter -n observability --create-namespace | tee -a "${LOG_FILE}"

log "Running initial readiness checks"
check_release_ready apps homepage
check_release_ready observability blackbox-exporter

log "Starting burn-in gate for ${BURNIN_MINUTES} minutes (interval ${CHECK_INTERVAL_SECONDS}s)"
end_ts="$(( $(date +%s) + BURNIN_MINUTES * 60 ))"
while [[ "$(date +%s)" -lt "${end_ts}" ]]; do
  if ! check_release_ready apps homepage; then
    log "Wave A gate failed for homepage"
    rollback_hint
    exit 1
  fi
  if ! check_release_ready observability blackbox-exporter; then
    log "Wave A gate failed for blackbox-exporter"
    rollback_hint
    exit 1
  fi
  sleep "${CHECK_INTERVAL_SECONDS}"
done

log "Wave A burn-in gate passed"
rollback_hint
log "Log file: ${LOG_FILE}"
