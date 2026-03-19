#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly WORKFLOWS_DIR="${ROOT_DIR}/.github/workflows"

ENFORCE_PINNED=0

usage() {
  cat <<'EOF'
Usage: workflow-ref-guard.sh [OPTIONS] [WORKFLOW_FILES...]

Validate GitHub Actions workflow `uses:` references.

Rules:
  - Docker refs must not use latest (docker://...:latest)
  - Action refs must not use mutable major-only tags (@v1, @v2, ...)

Options:
  --enforce-pinned   Require all action refs to be full-length commit SHAs.
  -h, --help         Show this help and exit.

Arguments:
  WORKFLOW_FILES     Optional list of workflow files to scan.
                     If omitted, scans all files in .github/workflows.
EOF
}

POSITIONAL_FILES=()

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --enforce-pinned)
        ENFORCE_PINNED=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        if [[ "$1" == -* ]]; then
          echo "Unknown option: $1" >&2
          usage >&2
          exit 2
        fi
        POSITIONAL_FILES+=("$1")
        ;;
    esac
    shift
  done
}

if [[ ! -d "${WORKFLOWS_DIR}" ]]; then
  echo "ERROR: Workflows directory not found: ${WORKFLOWS_DIR}" >&2
  exit 2
fi

parse_args "$@"

python3 - "${WORKFLOWS_DIR}" "${ENFORCE_PINNED}" "${POSITIONAL_FILES[@]}" <<'PY'
from __future__ import annotations

import pathlib
import re
import sys

workflows_dir = pathlib.Path(sys.argv[1])
enforce_pinned = sys.argv[2] == "1"
requested_files = [pathlib.Path(item).resolve() for item in sys.argv[3:]]

if requested_files:
    files = requested_files
else:
    files = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))

major_tag_re = re.compile(r"@v\d+$")
sha_ref_re = re.compile(r"@[0-9a-f]{40}$")
symbolic_ref_re = re.compile(r"@(main|master|latest)$")
uses_re = re.compile(r"^-?\s*uses:\s*(.+)$")

violations: list[tuple[pathlib.Path, int, str, str]] = []

for workflow in files:
    if not workflow.exists():
        print(f"ERROR: File does not exist: {workflow}", file=sys.stderr)
        sys.exit(2)

    for index, raw_line in enumerate(workflow.read_text().splitlines(), start=1):
        match = uses_re.match(raw_line)
        if not match:
            continue

        ref = match.group(1).strip().strip("\"'")
        reason: str | None = None

        if ref.startswith("docker://"):
            if ref.endswith(":latest"):
                reason = "docker reference uses mutable ':latest'"
        elif symbolic_ref_re.search(ref):
            reason = "action reference uses mutable symbolic tag"
        elif major_tag_re.search(ref):
            reason = "action reference uses mutable major tag"
        elif enforce_pinned and not sha_ref_re.search(ref):
            reason = "action reference is not pinned to full SHA"

        if reason:
            violations.append((workflow, index, ref, reason))

if violations:
    print("Workflow reference guard failed:", file=sys.stderr)
    for workflow, line_no, ref, reason in violations:
        try:
            display_path = workflow.relative_to(workflows_dir.parent.parent)
        except ValueError:
            display_path = workflow
        print(f"- {display_path}:{line_no} -> {ref} ({reason})", file=sys.stderr)
    sys.exit(3)

mode = "strict SHA pinning" if enforce_pinned else "mutable-tag guard"
print(f"Workflow reference guard passed ({mode}).")
PY
