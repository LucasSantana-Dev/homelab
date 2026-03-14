#!/usr/bin/env bash
# 24h pressure watch workflow with swap-threshold escalation hints.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
LOG_DIR="${PROJECT_ROOT}/logs/host-stabilization"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/pressure-watch-${TIMESTAMP}.log"

SAMPLES=6
INTERVAL_SECONDS=$((4 * 60 * 60))
SWAP_THRESHOLD_GIB="2.0"
BURNIN_SINCE="24 hours ago"
ESCALATE=false
NO_SLEEP=false

usage() {
  cat <<'EOF'
Usage: pressure-watch.sh [options]

Options:
  --samples N               Number of samples (default: 6, i.e. 24h at 4h cadence)
  --interval-seconds N      Delay between samples (default: 14400)
  --swap-threshold-gib X    Escalation threshold in GiB (default: 2.0)
  --burnin-since VALUE      burnin-status --since value (default: "24 hours ago")
  --escalate                Run swap-recover.sh when threshold is hit
  --no-sleep                Skip delays between samples (for dry runs/testing)
  -h, --help                Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --samples)
      SAMPLES="$2"
      shift 2
      ;;
    --interval-seconds)
      INTERVAL_SECONDS="$2"
      shift 2
      ;;
    --swap-threshold-gib)
      SWAP_THRESHOLD_GIB="$2"
      shift 2
      ;;
    --burnin-since)
      BURNIN_SINCE="$2"
      shift 2
      ;;
    --escalate)
      ESCALATE=true
      shift
      ;;
    --no-sleep)
      NO_SLEEP=true
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

if ! [[ "${SAMPLES}" =~ ^[0-9]+$ ]] || [[ "${SAMPLES}" -lt 1 ]]; then
  echo "--samples must be an integer >= 1" >&2
  exit 1
fi
if ! [[ "${INTERVAL_SECONDS}" =~ ^[0-9]+$ ]] || [[ "${INTERVAL_SECONDS}" -lt 1 ]]; then
  echo "--interval-seconds must be an integer >= 1" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

swap_used_bytes() {
  swapon --show --bytes --noheadings 2>/dev/null | awk '{sum += $4} END {print sum + 0}'
}

swap_used_human() {
  local used_bytes="$1"
  awk -v b="${used_bytes}" '
    BEGIN {
      split("B KiB MiB GiB TiB", units, " ");
      i=1;
      while (b >= 1024 && i < 5) {
        b /= 1024;
        i++;
      }
      printf "%.2f %s", b, units[i];
    }
  '
}

threshold_bytes="$(awk -v g="${SWAP_THRESHOLD_GIB}" 'BEGIN {printf "%.0f", g * 1024 * 1024 * 1024}')"

log "Pressure watch started"
log "samples=${SAMPLES} interval_seconds=${INTERVAL_SECONDS} threshold_gib=${SWAP_THRESHOLD_GIB} escalate=${ESCALATE}"
log "log_file=${LOG_FILE}"

for sample in $(seq 1 "${SAMPLES}"); do
  log "=== sample ${sample}/${SAMPLES} ==="

  {
    echo "--- free -h ---"
    free -h
    echo
    echo "--- swapon --show ---"
    swapon --show
    echo
    echo "--- burnin-status (${BURNIN_SINCE}) ---"
    "${PROJECT_ROOT}/scripts/maintenance/burnin-status.sh" --since "${BURNIN_SINCE}"
  } | tee -a "${LOG_FILE}"

  used_bytes="$(swap_used_bytes)"
  used_human="$(swap_used_human "${used_bytes}")"
  log "swap_used=${used_human}"

  if [[ "${used_bytes}" -ge "${threshold_bytes}" ]]; then
    log "Threshold reached: swap_used >= ${SWAP_THRESHOLD_GIB} GiB"
    if [[ "${ESCALATE}" == "true" ]]; then
      log "Escalation step 1: running swap-recover.sh"
      "${PROJECT_ROOT}/scripts/maintenance/swap-recover.sh" | tee -a "${LOG_FILE}"
      post_bytes="$(swap_used_bytes)"
      post_human="$(swap_used_human "${post_bytes}")"
      log "post_recover_swap_used=${post_human}"

      if [[ "${post_bytes}" -ge "${threshold_bytes}" ]]; then
        log "Escalation step 2 suggested: run server-mode plan (and apply only if still unstable)"
        log "  ${PROJECT_ROOT}/scripts/maintenance/convert-to-server-mode.sh"
        log "  ${PROJECT_ROOT}/scripts/maintenance/convert-to-server-mode.sh --apply"
      fi
    else
      log "Escalation hint: run swap-recover.sh, then server-mode plan/apply only if pressure remains unstable."
      log "  ${PROJECT_ROOT}/scripts/maintenance/swap-recover.sh"
      log "  ${PROJECT_ROOT}/scripts/maintenance/convert-to-server-mode.sh"
    fi
  fi

  if [[ "${sample}" -lt "${SAMPLES}" && "${NO_SLEEP}" != "true" ]]; then
    log "Sleeping ${INTERVAL_SECONDS}s before next sample"
    sleep "${INTERVAL_SECONDS}"
  fi
done

log "Pressure watch completed"
