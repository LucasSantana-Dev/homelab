#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)

[ -z "$COMMAND" ] && exit 0

printf '%s' "$COMMAND" | grep -qE '(tee |cat >|echo .+>|printf .+>|>> )' || exit 0

block_secret() { printf 'BLOCK: Possible hardcoded secret in Bash write command (%s). Use env vars or REPLACE_WITH_ placeholders.\n' "$1" >&2; exit 2; }

printf '%s' "$COMMAND" | grep -qE 'sk-ant-api0[0-9]-[A-Za-z0-9_-]{90,}' && block_secret "Anthropic API key"
printf '%s' "$COMMAND" | grep -qE 'github_pat_[A-Za-z0-9_]{36,}' && block_secret "GitHub fine-grained PAT"
printf '%s' "$COMMAND" | grep -qE 'ghp_[A-Za-z0-9]{36,}' && block_secret "GitHub classic token"
printf '%s' "$COMMAND" | grep -qE 'AKIA[0-9A-Z]{16}' && block_secret "AWS Access Key ID"
printf '%s' "$COMMAND" | grep -qE 'AGE-SECRET-KEY-1[A-Z0-9]{58}' && block_secret "age private key"
printf '%s' "$COMMAND" | grep -qE 'https?://[^/ ]+:[^/ @]+@' && block_secret "credentials embedded in URL"

exit 0
