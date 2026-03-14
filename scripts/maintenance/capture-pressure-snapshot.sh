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

"${ROOT_DIR}/scripts/maintenance/burnin-status.sh" --since "${BURNIN_SINCE}" > "${WATCH_DIR}/${LABEL}-burnin-30m.txt"
"${ROOT_DIR}/scripts/homelab" health > "${WATCH_DIR}/${LABEL}-health.txt"

echo "TIMESTAMP=${stamp}"
echo "WATCH_DIR=${WATCH_DIR}"
echo "LABEL=${LABEL}"
echo "BURNIN_SINCE=${BURNIN_SINCE}"
echo "STATUS=ok"
