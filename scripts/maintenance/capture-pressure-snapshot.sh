#!/usr/bin/env bash
# Capture a labeled pressure snapshot into a watch directory.

set -euo pipefail

LABEL="${1:-}"
WATCH_DIR="${2:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BURNIN_SINCE="30 minutes ago"

usage() {
  cat <<'EOF'
Usage: capture-pressure-snapshot.sh <LABEL> <WATCH_DIR> [--burnin-since '<value>']

Examples:
  capture-pressure-snapshot.sh TPLUS6H /tmp/homelab-pressure-watch-20260314_115740
  capture-pressure-snapshot.sh TNOW /tmp/homelab-pressure-watch --burnin-since '24 hours ago'
EOF
}

if [[ -z "${LABEL}" || -z "${WATCH_DIR}" ]]; then
  usage >&2
  exit 1
fi

shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --burnin-since)
      BURNIN_SINCE="$2"
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

mkdir -p "${WATCH_DIR}"

stamp="$(date --iso-8601=seconds)"
{
  echo "label=${LABEL}"
  echo "captured_at=${stamp}"
} > "${WATCH_DIR}/${LABEL}-meta.txt"

free -h > "${WATCH_DIR}/${LABEL}-free-h.txt"
swapon --show > "${WATCH_DIR}/${LABEL}-swapon-show.txt"
vmstat 1 5 > "${WATCH_DIR}/${LABEL}-vmstat.txt"

set +e
"${ROOT_DIR}/scripts/maintenance/burnin-status.sh" --since "${BURNIN_SINCE}" > "${WATCH_DIR}/${LABEL}-burnin-30m.txt" 2>&1
burnin_rc=$?
"${ROOT_DIR}/scripts/homelab" health > "${WATCH_DIR}/${LABEL}-health.txt" 2>&1
health_rc=$?
set -e

if [[ "${health_rc}" -ne 0 ]]; then
  # Fallback for non-interactive timer contexts where Python user-site deps are not loaded.
  if docker ps --format '{{.Status}}' | rg -qi 'unhealthy'; then
    {
      echo "fallback-health: UNHEALTHY"
      echo "WARN: ./scripts/homelab health exited ${health_rc}; used docker status fallback"
    } > "${WATCH_DIR}/${LABEL}-health.txt"
    health_rc=1
  elif docker ps --format '{{.Status}}' >/dev/null 2>&1; then
    {
      echo "fallback-health: HEALTHY"
      echo "WARN: ./scripts/homelab health exited ${health_rc}; used docker status fallback"
    } > "${WATCH_DIR}/${LABEL}-health.txt"
    health_rc=0
  fi
fi

{
  echo "burnin_exit=${burnin_rc}"
  echo "health_exit=${health_rc}"
} >> "${WATCH_DIR}/${LABEL}-meta.txt"

if [[ "${burnin_rc}" -ne 0 ]]; then
  echo "WARN: burnin-status.sh exited ${burnin_rc}" >> "${WATCH_DIR}/${LABEL}-burnin-30m.txt"
fi

if [[ "${health_rc}" -ne 0 ]]; then
  echo "WARN: ./scripts/homelab health exited ${health_rc}" >> "${WATCH_DIR}/${LABEL}-health.txt"
fi

echo "TIMESTAMP=${stamp}"
echo "WATCH_DIR=${WATCH_DIR}"
echo "LABEL=${LABEL}"
echo "BURNIN_SINCE=${BURNIN_SINCE}"
echo "BURNIN_EXIT=${burnin_rc}"
echo "HEALTH_EXIT=${health_rc}"
echo "STATUS=ok"
