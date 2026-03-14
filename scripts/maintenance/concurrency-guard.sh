#!/usr/bin/env bash
# Snapshot/verify git state for multi-agent task chunks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
STATE_DIR="${PROJECT_ROOT}/.git"
STATE_FILE="${STATE_DIR}/agent-concurrency-guard.state"

MODE="${1:-}"
shift || true

LABEL=""
declare -a ALLOW_PREFIXES=()

usage() {
  cat <<'EOF'
Usage:
  concurrency-guard.sh snapshot --label "<chunk>"
  concurrency-guard.sh verify --label "<chunk>" [--allow-prefix <path>]...

Examples:
  ./scripts/maintenance/concurrency-guard.sh snapshot --label "agent-a-chunk-1"
  ./scripts/maintenance/concurrency-guard.sh verify --label "agent-a-chunk-1" \
    --allow-prefix scripts/maintenance/ --allow-prefix Makefile
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --label)
      LABEL="$2"
      shift 2
      ;;
    --allow-prefix)
      ALLOW_PREFIXES+=("$2")
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

if [[ -z "${MODE}" || -z "${LABEL}" ]]; then
  usage >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

head_sha="$(git rev-parse HEAD)"
status_output="$(git status --porcelain=v1)"

print_report() {
  echo "[concurrency-guard] label=${LABEL}"
  echo "[concurrency-guard] head=${head_sha}"
  if [[ -z "${status_output}" ]]; then
    echo "[concurrency-guard] status=clean"
  else
    echo "[concurrency-guard] status=dirty"
    printf '%s\n' "${status_output}"
  fi
}

extract_changed_paths() {
  if [[ -z "${status_output}" ]]; then
    return
  fi
  printf '%s\n' "${status_output}" | awk '{print substr($0,4)}'
}

path_allowed() {
  local path="$1"
  local prefix
  for prefix in "${ALLOW_PREFIXES[@]}"; do
    if [[ "${path}" == "${prefix}"* ]]; then
      return 0
    fi
  done
  return 1
}

case "${MODE}" in
  snapshot)
    print_report
    {
      echo "label=${LABEL}"
      echo "head=${head_sha}"
    } > "${STATE_FILE}"
    ;;
  verify)
    if [[ ! -f "${STATE_FILE}" ]]; then
      echo "State file missing: ${STATE_FILE}. Run snapshot first." >&2
      exit 1
    fi

    baseline_head="$(awk -F= '/^head=/{print $2}' "${STATE_FILE}")"
    print_report

    if [[ "${baseline_head}" != "${head_sha}" ]]; then
      echo "HEAD changed during chunk: baseline=${baseline_head}, current=${head_sha}" >&2
      exit 1
    fi

    if [[ -z "${status_output}" ]]; then
      echo "[concurrency-guard] verify=ok (clean)"
      exit 0
    fi

    if [[ ${#ALLOW_PREFIXES[@]} -eq 0 ]]; then
      echo "Dirty worktree detected and no allow-prefix list provided." >&2
      exit 1
    fi

    mapfile -t changed_paths < <(extract_changed_paths)
    disallowed=0
    for path in "${changed_paths[@]}"; do
      if ! path_allowed "${path}"; then
        echo "Disallowed change detected: ${path}" >&2
        disallowed=1
      fi
    done

    if [[ "${disallowed}" -ne 0 ]]; then
      exit 1
    fi

    echo "[concurrency-guard] verify=ok (all changes allowed)"
    ;;
  *)
    echo "Unknown mode: ${MODE}" >&2
    usage >&2
    exit 1
    ;;
esac
