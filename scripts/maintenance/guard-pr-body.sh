#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: guard-pr-body.sh [options]

Scan PR metadata text for token-like leaks.

Options:
  --title TEXT         Optional PR title text to scan
  --body TEXT          PR body text to scan
  --body-file PATH     PR body file to scan
  --stdin              Read PR body text from stdin
  -h, --help           Show help

Exit codes:
  0  No token-like patterns found
  3  Token-like pattern found
  4  Invalid usage

Examples:
  guard-pr-body.sh --body-file pr.md
  guard-pr-body.sh --title "fix(ci): update watchdog" --body "Safe text"
  gh pr view 123 --json body --jq '.body' | guard-pr-body.sh --stdin
EOF
}

title=""
body=""
read_stdin=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      title="${2-}"
      shift 2
      ;;
    --body)
      body="${2-}"
      shift 2
      ;;
    --body-file)
      if [[ ! -f "${2-}" ]]; then
        echo "Body file not found: ${2-}" >&2
        exit 4
      fi
      body="$(<"$2")"
      shift 2
      ;;
    --stdin)
      read_stdin=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 4
      ;;
  esac
done

if [[ "$read_stdin" == true ]]; then
  body="$(cat)"
fi

if [[ -z "$title" && -z "$body" ]]; then
  echo "No input provided. Use --body, --body-file, --stdin, and/or --title." >&2
  exit 4
fi

export GUARD_TITLE="$title"
export GUARD_BODY="$body"

python3 <<'PY'
import os
import re
import sys

patterns = [
    ("ghp", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("gho", re.compile(r"\bgho_[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
]


def redact(token: str) -> str:
    if len(token) <= 10:
        return "<redacted>"
    return f"{token[:6]}...{token[-4:]}"


title = os.environ.get("GUARD_TITLE", "")
body = os.environ.get("GUARD_BODY", "")

findings = []
for field_name, text in (("title", title), ("body", body)):
    if not text:
        continue
    for pattern_name, pattern in patterns:
        for match in pattern.finditer(text):
            findings.append((field_name, pattern_name, redact(match.group(0))))

if findings:
    print("Token-like pattern detected in PR metadata:", file=sys.stderr)
    for field_name, pattern_name, token in findings:
        print(f"- field={field_name} pattern={pattern_name} sample={token}", file=sys.stderr)
    sys.exit(3)

print("No token-like patterns detected.")
sys.exit(0)
PY
