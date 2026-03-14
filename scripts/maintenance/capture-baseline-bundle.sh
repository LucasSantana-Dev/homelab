#!/usr/bin/env bash
# Capture baseline validation evidence for handoff.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
LOG_DIR="${PROJECT_ROOT}/logs/host-stabilization"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/baseline-bundle-${TIMESTAMP}.log"

mkdir -p "${LOG_DIR}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

run_step() {
  local name="$1"
  shift
  log "=== ${name} ==="
  "$@" 2>&1 | tee -a "${LOG_FILE}"
  log "=== ${name} complete ==="
}

log "Baseline bundle capture started"
log "log_file=${LOG_FILE}"

run_step "homelab health" "${PROJECT_ROOT}/scripts/homelab" health
run_step "burnin status" "${PROJECT_ROOT}/scripts/maintenance/burnin-status.sh"
run_step "migration budget" make -C "${PROJECT_ROOT}" migration-budget
run_step "migration preflight" make -C "${PROJECT_ROOT}" migration-preflight

log "Baseline bundle capture completed"
