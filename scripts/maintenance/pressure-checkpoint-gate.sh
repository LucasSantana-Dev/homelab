#!/usr/bin/env bash
# Evaluate a timed pressure checkpoint artifact set and emit a gate token.

set -euo pipefail

WATCH_DIR="${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}"
LABEL="${LABEL:-}"
PREV_LABEL="${PREV_LABEL:-}"
SWAP_THRESHOLD_GIB="${SWAP_THRESHOLD_GIB:-2.0}"

usage() {
  cat <<'EOF'
Usage: pressure-checkpoint-gate.sh --label <SAMPLE2|TPLUS6H|TPLUS24H|...> [options]

Options:
  --watch-dir DIR           Checkpoint directory (default: /tmp/homelab-pressure-watch-20260314_115740)
  --label NAME              Checkpoint label to evaluate (required)
  --prev-label NAME         Prior label for trend comparison
  --swap-threshold-gib X    Swap threshold in GiB (default: 2.0)
  -h, --help                Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch-dir)
      WATCH_DIR="$2"
      shift 2
      ;;
    --label)
      LABEL="$2"
      shift 2
      ;;
    --prev-label)
      PREV_LABEL="$2"
      shift 2
      ;;
    --swap-threshold-gib)
      SWAP_THRESHOLD_GIB="$2"
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

if [[ -z "${LABEL}" ]]; then
  echo "--label is required" >&2
  usage >&2
  exit 1
fi

if [[ ! -d "${WATCH_DIR}" ]]; then
  echo "WATCH_DIR does not exist: ${WATCH_DIR}" >&2
  exit 1
fi

derive_prev_label() {
  local current="$1"
  case "${current}" in
    SAMPLE2) echo "TNOW" ;;
    TPLUS6H) echo "T0" ;;
    TPLUS24H) echo "TPLUS6H" ;;
    TNOW) echo "T0" ;;
    *) echo "" ;;
  esac
}

human_to_bytes() {
  local value="$1"
  numfmt --from=iec "${value}"
}

print_kv() {
  echo "$1=$2"
}

if [[ -z "${PREV_LABEL}" ]]; then
  PREV_LABEL="$(derive_prev_label "${LABEL}")"
fi

TIMER_UNIT=""
case "${LABEL}" in
  SAMPLE2) TIMER_UNIT="homelab-pressure-gate-sample2.timer" ;;
  TPLUS6H) TIMER_UNIT="homelab-pressure-watch-tplus6h.timer" ;;
  TPLUS24H) TIMER_UNIT="homelab-pressure-watch-tplus24h.timer" ;;
esac

TIMER_LINE=""
TIMER_NEXT=""
if [[ -n "${TIMER_UNIT}" ]]; then
  TIMER_LINE="$(systemctl --user list-timers --all --no-legend "${TIMER_UNIT}" 2>/dev/null | head -n1 || true)"
  if [[ -n "${TIMER_LINE}" ]]; then
    TIMER_NEXT="$(awk '{print $1" "$2" "$3" "$4}' <<< "${TIMER_LINE}")"
  fi
fi

meta_file="${WATCH_DIR}/${LABEL}-meta.txt"
swap_file="${WATCH_DIR}/${LABEL}-swapon-show.txt"
vmstat_file="${WATCH_DIR}/${LABEL}-vmstat.txt"
burnin_file="${WATCH_DIR}/${LABEL}-burnin-30m.txt"
health_file="${WATCH_DIR}/${LABEL}-health.txt"
prev_swap_file=""
if [[ -n "${PREV_LABEL}" ]]; then
  prev_swap_file="${WATCH_DIR}/${PREV_LABEL}-swapon-show.txt"
fi

timestamp="$(date --iso-8601=seconds)"
threshold_bytes="$(awk -v g="${SWAP_THRESHOLD_GIB}" 'BEGIN {printf "%.0f", g * 1024 * 1024 * 1024}')"

required=( "${meta_file}" "${swap_file}" "${vmstat_file}" "${burnin_file}" "${health_file}" )
missing=()
for f in "${required[@]}"; do
  if [[ ! -f "${f}" ]]; then
    missing+=( "${f}" )
  fi
done

if (( ${#missing[@]} > 0 )); then
  if [[ "${LABEL}" == "SAMPLE2" ]]; then
    live_swap_used_human="$(swapon --show --noheadings 2>/dev/null | awk 'NR==1 {print $4}')"
    live_swap_used_bytes=0
    if [[ -n "${live_swap_used_human}" ]]; then
      live_swap_used_bytes="$(human_to_bytes "${live_swap_used_human}")"
    fi
    if (( live_swap_used_bytes >= threshold_bytes )); then
      print_kv "TIMESTAMP" "${timestamp}"
      print_kv "WATCH_DIR" "${WATCH_DIR}"
      print_kv "LABEL" "${LABEL}"
      print_kv "PREV_LABEL" "${PREV_LABEL:-none}"
      print_kv "ARTIFACT_STATUS" "pre_sample_live_check"
      print_kv "TIMER_UNIT" "${TIMER_UNIT:-none}"
      print_kv "TIMER_NEXT" "${TIMER_NEXT:-unknown}"
      print_kv "SWAP_THRESHOLD_GIB" "${SWAP_THRESHOLD_GIB}"
      print_kv "SWAP_USED_HUMAN" "${live_swap_used_human}"
      print_kv "SWAP_USED_BYTES" "${live_swap_used_bytes}"
      print_kv "TREND" "UNKNOWN"
      print_kv "GATE_TOKEN" "BLOCKED"
      print_kv "REASON" "swap_above_threshold_pre_sample2"
      print_kv "MISSING_COUNT" "${#missing[@]}"
      printf 'MISSING_FILES=%s\n' "$(printf '%s;' "${missing[@]}")"
      exit 2
    fi
  fi

  print_kv "TIMESTAMP" "${timestamp}"
  print_kv "WATCH_DIR" "${WATCH_DIR}"
  print_kv "LABEL" "${LABEL}"
  print_kv "PREV_LABEL" "${PREV_LABEL:-none}"
  print_kv "ARTIFACT_STATUS" "waiting"
  print_kv "TIMER_UNIT" "${TIMER_UNIT:-none}"
  print_kv "TIMER_NEXT" "${TIMER_NEXT:-unknown}"
  print_kv "SWAP_THRESHOLD_GIB" "${SWAP_THRESHOLD_GIB}"
  print_kv "GATE_TOKEN" "WAITING"
  print_kv "REASON" "missing_artifacts"
  print_kv "MISSING_COUNT" "${#missing[@]}"
  printf 'MISSING_FILES=%s\n' "$(printf '%s;' "${missing[@]}")"
  exit 0
fi

swap_used_human="$(awk 'NR==2 {print $4}' "${swap_file}")"
if [[ -z "${swap_used_human}" ]]; then
  echo "Could not parse swap used from ${swap_file}" >&2
  exit 1
fi
swap_used_bytes="$(human_to_bytes "${swap_used_human}")"

prev_swap_used_human=""
prev_swap_used_bytes=""
trend="UNKNOWN"
if [[ -n "${prev_swap_file}" && -f "${prev_swap_file}" ]]; then
  prev_swap_used_human="$(awk 'NR==2 {print $4}' "${prev_swap_file}")"
  if [[ -n "${prev_swap_used_human}" ]]; then
    prev_swap_used_bytes="$(human_to_bytes "${prev_swap_used_human}")"
    if (( swap_used_bytes > prev_swap_used_bytes )); then
      trend="RISING"
    else
      trend="FLAT_OR_DOWN"
    fi
  fi
fi

burnin_status="UNKNOWN"
if grep -Eq '^Overall:[[:space:]]+PASS' "${burnin_file}"; then
  burnin_status="PASS"
elif grep -Eq '^Overall:[[:space:]]+FAIL' "${burnin_file}"; then
  burnin_status="FAIL"
fi

health_status="UNKNOWN"
if grep -q '❌' "${health_file}" || grep -qi 'unhealthy' "${health_file}"; then
  health_status="UNHEALTHY"
elif grep -q '✅' "${health_file}" || grep -qi 'healthy' "${health_file}"; then
  health_status="HEALTHY"
fi

gate_token="GREENLIGHT"
reason="stable"

if [[ "${LABEL}" == "SAMPLE2" ]] && (( swap_used_bytes >= threshold_bytes )); then
  gate_token="BLOCKED"
  reason="swap_above_threshold_pre_sample2"
elif [[ "${burnin_status}" != "PASS" ]]; then
  gate_token="BLOCKED"
  reason="burnin_not_pass"
elif [[ "${health_status}" != "HEALTHY" ]]; then
  gate_token="BLOCKED"
  reason="health_not_healthy"
elif (( swap_used_bytes > threshold_bytes )) && [[ "${trend}" == "RISING" ]]; then
  gate_token="BLOCKED"
  reason="swap_above_threshold_and_rising"
fi

print_kv "TIMESTAMP" "${timestamp}"
print_kv "WATCH_DIR" "${WATCH_DIR}"
print_kv "LABEL" "${LABEL}"
print_kv "PREV_LABEL" "${PREV_LABEL:-none}"
print_kv "ARTIFACT_STATUS" "ready"
print_kv "TIMER_UNIT" "${TIMER_UNIT:-none}"
print_kv "TIMER_NEXT" "${TIMER_NEXT:-unknown}"
print_kv "SWAP_THRESHOLD_GIB" "${SWAP_THRESHOLD_GIB}"
print_kv "SWAP_USED_HUMAN" "${swap_used_human}"
print_kv "SWAP_USED_BYTES" "${swap_used_bytes}"
print_kv "PREV_SWAP_USED_HUMAN" "${prev_swap_used_human:-unknown}"
print_kv "PREV_SWAP_USED_BYTES" "${prev_swap_used_bytes:-unknown}"
print_kv "TREND" "${trend}"
print_kv "BURNIN_STATUS" "${burnin_status}"
print_kv "HEALTH_STATUS" "${health_status}"
print_kv "GATE_TOKEN" "${gate_token}"
print_kv "REASON" "${reason}"

if [[ "${gate_token}" == "BLOCKED" ]]; then
  exit 2
fi
