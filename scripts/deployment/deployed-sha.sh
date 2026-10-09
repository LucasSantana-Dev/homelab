#!/bin/bash
# deployed-sha.sh {read|write [sha]}
#
# Tracks the git SHA that was actually deployed by the last successful
# `make deploy`, so apply-config-changes.sh can diff against "what's actually
# running" instead of assuming a `git pull` just happened (ADR-0023 keeps
# deploys deliberate/manual, so a config-only re-run of `make deploy` with no
# preceding pull is a normal case).
#
# State dir mirrors the ADR-0023 pattern already used by
# record-deploy-health.sh: typically root-owned on the real host, so a direct
# write from the deploy user falls back to `sudo -n tee`, and if neither works
# the write is best-effort (never blocks deploy: `apply-config-changes.sh`
# already treats an unreadable/empty state as "everything changed", which is
# the safe default).
set -uo pipefail

STATE_DIR="${HOMELAB_STATE_DIR:-/var/lib/homelab}"
STATE_FILE="${HOMELAB_DEPLOYED_SHA_FILE:-${STATE_DIR}/deployed-sha}"

cmd="${1:-read}"

case "$cmd" in
    read)
        content=""
        if [[ -r "$STATE_FILE" ]]; then
            content="$(tr -d '[:space:]' < "$STATE_FILE" 2>/dev/null || true)"
        fi
        echo "$content"
        ;;
    write)
        sha="${2:-$(git rev-parse HEAD)}"
        # A fresh host has no /var/lib/homelab yet; plain `mkdir -p` fails
        # against a root-owned parent, and `sudo -n tee` alone can't create a
        # missing directory either. Try a passwordless `sudo -n mkdir -p` too
        # before giving up on the directory.
        if ! mkdir -p "$STATE_DIR" 2>/dev/null; then
            command -v sudo >/dev/null 2>&1 && sudo -n mkdir -p "$STATE_DIR" 2>/dev/null
        fi
        if [[ -w "$STATE_DIR" ]] || { [[ -d "$STATE_DIR" ]] && touch "$STATE_DIR/.w" 2>/dev/null && rm -f "$STATE_DIR/.w"; }; then
            tmp="${STATE_FILE}.tmp"
            if ! { echo "$sha" > "$tmp" && mv "$tmp" "$STATE_FILE"; }; then
                echo "⚠️  deployed-sha: writable dir but failed to write ${STATE_FILE}" >&2
                exit 1
            fi
        elif command -v sudo >/dev/null 2>&1 && echo "$sha" | sudo -n tee "$STATE_FILE" >/dev/null 2>&1; then
            : # written via sudo
        else
            echo "⚠️  deployed-sha: could not persist deployed SHA to ${STATE_FILE} (no write access, no passwordless sudo). The next apply-config-changes.sh run will treat everything as changed." >&2
            exit 1
        fi
        ;;
    *)
        echo "usage: $0 {read|write [sha]}" >&2
        exit 1
        ;;
esac
