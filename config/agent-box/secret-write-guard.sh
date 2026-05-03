#!/usr/bin/env bash
# Scan content being written/edited for hardcoded secrets.
# Fires on Write|Edit|MultiEdit PreToolUse.
set -euo pipefail

INPUT=$(cat)
# Extract content from Write (new_string) or Edit (new_string / content)
CONTENT=$(printf '%s' "$INPUT" | jq -r '
  .tool_input.new_string //
  .tool_input.content //
  (.tool_input.edits // [] | map(.new_string) | join("\n")) //
  empty' 2>/dev/null || true)

[ -z "$CONTENT" ] && exit 0

block_secret() { printf 'BLOCK: Possible hardcoded secret detected (%s). Use env vars or REPLACE_WITH_ placeholders.\n' "$1" >&2; exit 2; }

# High-confidence token patterns — these are very unlikely to be false positives
if printf '%s' "$CONTENT" | grep -qE 'sk-ant-api0[0-9]-[A-Za-z0-9_-]{90,}'; then
    block_secret "Anthropic API key"
fi
if printf '%s' "$CONTENT" | grep -qE 'github_pat_[A-Za-z0-9_]{36,}'; then
    block_secret "GitHub fine-grained PAT"
fi
if printf '%s' "$CONTENT" | grep -qE 'ghp_[A-Za-z0-9]{36,}'; then
    block_secret "GitHub classic token"
fi
if printf '%s' "$CONTENT" | grep -qE 'AKIA[0-9A-Z]{16}'; then
    block_secret "AWS Access Key ID"
fi
if printf '%s' "$CONTENT" | grep -qE 'AGE-SECRET-KEY-1[A-Z0-9]{58}'; then
    block_secret "age private key"
fi
if printf '%s' "$CONTENT" | grep -qE 'https?://[^/ ]+:[^/ @]+@'; then
    block_secret "credentials embedded in URL"
fi

exit 0
