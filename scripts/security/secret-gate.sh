#!/usr/bin/env bash
# Run gitleaks against tracked content (snapshot) and optionally full git history.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/.gitleaks.toml"
REPORT_DIR="${ROOT_DIR}/logs/security"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SCAN_HISTORY=false

usage() {
  cat <<'EOF'
Usage: secret-gate.sh [--history]

Options:
  --history   Also scan full git history (`--log-opts="--all"`).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --history)
      SCAN_HISTORY=true
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

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is required. Install it and retry." >&2
  exit 1
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Missing gitleaks config: ${CONFIG_FILE}" >&2
  exit 1
fi

mkdir -p "${REPORT_DIR}"

echo "Running tracked snapshot secret scan..."
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

git -C "${ROOT_DIR}" archive HEAD | tar -x -C "${TMP_DIR}"

SNAPSHOT_REPORT="${REPORT_DIR}/gitleaks-snapshot-${TIMESTAMP}.json"
gitleaks detect \
  --no-banner \
  --source "${TMP_DIR}" \
  --no-git \
  --config "${CONFIG_FILE}" \
  --redact \
  --report-format json \
  --report-path "${SNAPSHOT_REPORT}"

echo "Snapshot scan passed: ${SNAPSHOT_REPORT}"

if [[ "${SCAN_HISTORY}" == "true" ]]; then
  echo "Running git history secret scan..."
  HISTORY_REPORT="${REPORT_DIR}/gitleaks-history-${TIMESTAMP}.json"
  gitleaks detect \
    --no-banner \
    --source "${ROOT_DIR}" \
    --log-opts="--all" \
    --config "${CONFIG_FILE}" \
    --redact \
    --report-format json \
    --report-path "${HISTORY_REPORT}"
  echo "History scan passed: ${HISTORY_REPORT}"
fi

echo "Secret gate passed"
