#!/usr/bin/env bash
# Reset swap and collect pre/post pressure diagnostics.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
LOG_DIR="${PROJECT_ROOT}/logs/host-stabilization"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/swap-recover-${TIMESTAMP}.log"

DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: swap-recover.sh [--dry-run]

Options:
  --dry-run    Show commands without running swap reset
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
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

mkdir -p "${LOG_DIR}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

run_sudo() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

capture_metrics() {
  local phase="$1"
  log "=== ${phase} metrics ==="
  {
    free -h
    echo
    swapon --show
    echo
    vmstat 1 5
    echo
    ps -eo pid,user,comm,rss,%mem --sort=-rss | sed -n '1,30p'
  } | tee -a "${LOG_FILE}"
}

log "Swap recovery started"
capture_metrics "Before"

if [[ "${DRY_RUN}" == "true" ]]; then
  log "Dry run: would execute 'swapoff -a' then 'swapon -a'"
  exit 0
fi

log "Resetting swap (swapoff -a && swapon -a)"
run_sudo swapoff -a
run_sudo swapon -a

capture_metrics "After"
log "Swap recovery completed"
log "Log file: ${LOG_FILE}"
