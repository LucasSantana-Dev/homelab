#!/usr/bin/env bash
# Ensure known private infrastructure identifiers are not committed in public-facing files.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

DENY_HOST_PREFIX='server-do-'
DENY_HOST_SUFFIX='luk'
DENY_REGEX="luk-homeserver\\\\?\\.com\\\\?\\.br|tailab88e9\\\\?\\.ts\\\\?\\.net|100\\.95\\.204\\.103|${DENY_HOST_PREFIX}${DENY_HOST_SUFFIX}"
EXCLUDE_PATH_REGEX='^(tests/|\.serena/|\.cursor/|security-reports/|appdata/|docs/access-layers\.md|scripts/security/public-safety-gate\.sh$|config/caddy/|config/cloudflared/|config/homepage/|compose/media\.yml$)'

mapfile -t tracked_files < <(
  git -C "${ROOT_DIR}" diff --cached --name-only -- \
    '*.md' '*.yml' '*.yaml' '*.conf' '*.json' '*.sh' '*.py' '*.toml' \
    'Makefile' '.github/workflows/*.yml' '.github/*.md'
)

if [[ ${#tracked_files[@]} -eq 0 ]]; then
  echo "No staged files to check for public safety"
  exit 0
fi

violations=0
for file in "${tracked_files[@]}"; do
  if [[ "${file}" =~ ${EXCLUDE_PATH_REGEX} ]]; then
    continue
  fi

  # Scan only the STAGED ADDED lines, not the whole file (#193). Whole-file
  # scanning re-flagged pre-existing identifiers in already-committed files on
  # every unrelated edit (recurring false-positives). The gate's job is to block
  # NEW additions of private identifiers; a pre-existing occurrence is already in
  # history and is handled by the release-scrub flow, not this pre-commit gate.
  added_lines="$(
    git -C "${ROOT_DIR}" diff --cached -U0 -- "${file}" \
      | grep '^+' | grep -v '^+++' | sed 's/^+//'
  )"
  if printf '%s\n' "${added_lines}" \
      | rg -n --regexp "${DENY_REGEX}" >/tmp/public-safety-match.txt 2>/dev/null; then
    if [[ "${violations}" -eq 0 ]]; then
      echo "Public safety gate failed. Found private identifiers in newly-added lines:"
    fi
    violations=$((violations + 1))
    sed "s#^#${file} (added):#" /tmp/public-safety-match.txt
  fi
done

if [[ "${violations}" -gt 0 ]]; then
  exit 1
fi

echo "Public safety gate passed"
