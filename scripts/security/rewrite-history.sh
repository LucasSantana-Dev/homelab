#!/usr/bin/env bash
# Rewrite git history to remove known sensitive artifacts and scrub token-like values.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REMOVE_PATHS_FILE="${ROOT_DIR}/security/history-rewrite/remove-paths.txt"
REPLACE_TEXT_FILE="${ROOT_DIR}/security/history-rewrite/replace-text.txt"
PUSH=false
REMOTE_NAME="origin"

usage() {
  cat <<'EOF'
Usage: rewrite-history.sh [--push] [--remote origin]

Requirements:
  - Clean working tree (no pending changes)
  - git-filter-repo installed
  - Remote backup/checkpoint already created

Options:
  --push            Force-push rewritten history to remote
  --remote <name>   Remote name for force-push (default: origin)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push)
      PUSH=true
      shift
      ;;
    --remote)
      REMOTE_NAME="$2"
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

if ! command -v git-filter-repo >/dev/null 2>&1; then
  echo "git-filter-repo is required. Install it and retry." >&2
  exit 1
fi

if [[ ! -f "${REMOVE_PATHS_FILE}" || ! -f "${REPLACE_TEXT_FILE}" ]]; then
  echo "Missing history rewrite policy files under security/history-rewrite/" >&2
  exit 1
fi

if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash changes before rewriting history." >&2
  exit 1
fi

echo "Rewriting history with git-filter-repo..."
git -C "${ROOT_DIR}" filter-repo --force \
  --replace-text "${REPLACE_TEXT_FILE}" \
  --paths-from-file "${REMOVE_PATHS_FILE}" \
  --invert-paths

echo "Running post-rewrite secret checks..."
"${ROOT_DIR}/scripts/security/secret-gate.sh" --history
"${ROOT_DIR}/scripts/security/public-safety-gate.sh"

if [[ "${PUSH}" == "true" ]]; then
  echo "Force-pushing rewritten history to ${REMOTE_NAME}..."
  git -C "${ROOT_DIR}" push --force "${REMOTE_NAME}" --all
  git -C "${ROOT_DIR}" push --force "${REMOTE_NAME}" --tags
  echo "Rewrite pushed. Collaborators must re-clone."
else
  echo "Rewrite complete locally. Review and run with --push when ready."
fi
