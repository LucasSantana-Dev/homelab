#!/usr/bin/env bash
# Block tag deletion, forced tag pushes, npm publish, and production deploys.
set -euo pipefail

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
[ -z "$CMD" ] && exit 0

block() { printf 'BLOCK: %s\n' "$*" >&2; exit 2; }

# No deleting git tags (Lucky release tags are permanent)
if printf '%s' "$CMD" | grep -qE 'git\s+tag\s+(-d|--delete)'; then
    block "Deleting git tags is forbidden — Lucky release tags must be permanent."
fi

# No force-pushing tags
if printf '%s' "$CMD" | grep -qE 'git\s+push.*--force.*v[0-9]|git\s+push.*-f.*v[0-9]'; then
    block "Force-pushing release tags is forbidden."
fi

# No npm publish without explicit request
if printf '%s' "$CMD" | grep -qE 'npm\s+publish|yarn\s+publish'; then
    block "npm/yarn publish is blocked — publishing to npm requires explicit user confirmation."
fi

# No mass file deletion
if printf '%s' "$CMD" | grep -qE 'git\s+clean\s+-[a-z]*f[a-z]*d|find\s+.*-delete|find\s+.*-exec\s+rm'; then
    block "Mass file deletion (git clean -fd, find -delete) requires explicit user confirmation."
fi

# No accessing the container's own secrets or env injection files
if printf '%s' "$CMD" | grep -qE '/run/secrets/|/etc/profile\.d/agent-env'; then
    block "Accessing container secrets or env injection files is forbidden."
fi

exit 0
