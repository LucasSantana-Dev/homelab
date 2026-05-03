#!/usr/bin/env bash
# Block destructive operations against production homelab containers and services.
set -euo pipefail

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
[ -z "$CMD" ] && exit 0

block() { printf 'BLOCK: %s\n' "$*" >&2; exit 2; }

# ── Production containers that must not be touched ──────────────────────────
PROTECTED_RE='lucky[-_](bot|backend|frontend|nginx|postgres|redis|webhook|tunnel)|nextcloud|nextcloud[-_](db|redis)|craftvaria|homeassistant|pihole|cloudflared|caddy[-_]lan|open[-_]webui|craftvaria[-_](admin|cloudflared|playit|minecraft)'

# docker stop / rm / kill / restart / pause on a protected container
if printf '%s' "$CMD" | grep -qE 'docker\s+(stop|rm|kill|restart|pause)'; then
    TARGETS=$(printf '%s' "$CMD" | grep -oE '[a-zA-Z0-9_-]+' | tail -n +4)
    for t in $TARGETS; do
        if printf '%s' "$t" | grep -qE "$PROTECTED_RE"; then
            block "Container '$t' is a production service — stop/rm/kill blocked. Confirm with user first."
        fi
    done
fi

# docker compose down (always destructive in homelab context)
if printf '%s' "$CMD" | grep -qE 'docker[\s-]compose\s+down|docker\s+compose\s+down'; then
    block "'docker compose down' would take down production services. Requires explicit user confirmation."
fi

# docker system prune
if printf '%s' "$CMD" | grep -qE 'docker\s+system\s+prune'; then
    block "'docker system prune' may delete production image layers. Requires explicit user confirmation."
fi

exit 0
