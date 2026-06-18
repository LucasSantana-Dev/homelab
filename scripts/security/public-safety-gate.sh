#!/usr/bin/env bash
# Ensure known private infrastructure identifiers are not committed in public-facing files.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

DENY_HOST_PREFIX='server-do-'
DENY_HOST_SUFFIX='luk'
DENY_REGEX="luk-homeserver\\\\?\\.com\\\\?\\.br|tailab88e9\\\\?\\.ts\\\\?\\.net|100\\.95\\.204\\.103|${DENY_HOST_PREFIX}${DENY_HOST_SUFFIX}"
EXCLUDE_PATH_REGEX='^(tests/|\.serena/|\.cursor/|security-reports/|appdata/|docs/access-layers\.md|scripts/security/public-safety-gate\.sh$)'

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

  if rg -n --regexp "${DENY_REGEX}" "${ROOT_DIR}/${file}" >/tmp/public-safety-match.txt 2>/dev/null; then
    if [[ "${violations}" -eq 0 ]]; then
      echo "Public safety gate failed. Found private identifiers in staged files:"
    fi
    violations=$((violations + 1))
    sed "s#^#${file}:#" /tmp/public-safety-match.txt
  fi
done

if [[ "${violations}" -gt 0 ]]; then
  exit 1
fi

echo "Public safety gate passed"
