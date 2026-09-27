#!/bin/bash
# apply-config-changes.sh [old-sha]
#
# Run after `docker compose up -d --build` in `make deploy`. Three config
# paths are mounted in ways that neither `git pull` nor `docker compose up -d`
# alone gets a running container to actually use (found across three manual
# deploys on 2026-09-27):
#
#   - config/caddy/Caddyfile is bind-mounted as a single FILE (compose/
#     lan-proxy.yml). git replaces the file (new inode); the running
#     container keeps serving the old one, `caddy reload` reloads stale
#     content, and `docker compose up -d` does not recreate caddy-lan because
#     nothing in the caddy-lan *service definition* changed. Needs a restart.
#   - config/prometheus/ and config/alertmanager/ are directory mounts, so the
#     new files ARE visible inside the container, but neither process re-reads
#     them without a signal.
#
# Usage: apply-config-changes.sh [old-sha]
#   old-sha missing, empty, or "unknown" -> no reliable base to diff from
#   (e.g. first run, no recorded deployed-sha yet), so every managed config
#   path is treated as changed.
set -uo pipefail

# Operates on the current working directory's repo (Make always runs recipe
# commands from the Makefile's directory, i.e. the repo root; tests point
# this at a temporary repo the same way).
OLD_SHA="${1:-}"
MANAGED_PATHS=(config/caddy config/prometheus config/alertmanager)
# Overridable so tests don't burn 10+ real seconds per reload check; the host
# defaults (10 x 1s) match record-deploy-health.sh's retry style.
RELOAD_POLL_ATTEMPTS="${RELOAD_POLL_ATTEMPTS:-10}"
RELOAD_POLL_INTERVAL="${RELOAD_POLL_INTERVAL:-1}"
errors=0

changed_all=false
if [[ -z "$OLD_SHA" || "$OLD_SHA" == "unknown" ]]; then
    changed_all=true
    echo "ℹ️  No previous deployed SHA on record. Treating all managed config as changed."
elif ! git cat-file -e "${OLD_SHA}^{commit}" 2>/dev/null; then
    changed_all=true
    echo "⚠️  Previous deployed SHA ${OLD_SHA} not found in history. Treating all managed config as changed."
fi

if $changed_all; then
    changed_files="$(git ls-files -- "${MANAGED_PATHS[@]}")"
else
    changed_files="$(git diff --name-only "${OLD_SHA}" HEAD -- "${MANAGED_PATHS[@]}")"
fi

caddy_changed=false
prometheus_changed=false
alertmanager_changed=false
if printf '%s\n' "$changed_files" | grep -qx 'config/caddy/Caddyfile'; then
    caddy_changed=true
fi
if printf '%s\n' "$changed_files" | grep -q '^config/prometheus/'; then
    prometheus_changed=true
fi
if printf '%s\n' "$changed_files" | grep -q '^config/alertmanager/'; then
    alertmanager_changed=true
fi

if ! $caddy_changed && ! $prometheus_changed && ! $alertmanager_changed; then
    echo "✅ apply-config-changes: no bind-mounted/dir-mounted config changed, nothing to reload."
    exit 0
fi

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum | awk '{print $1}'
    else
        shasum -a 256 | awk '{print $1}'
    fi
}

# Prometheus and Alertmanager both use the same config-reload machinery and
# log "Completed loading of configuration file" on success, whether triggered
# by SIGHUP or (for prometheus, which runs --web.enable-lifecycle) the
# /-/reload HTTP endpoint. SIGHUP works for both regardless of that flag and
# does not depend on knowing the container's bound host/port, so it is used
# for both. This is what was actually run and verified working on the host
# on 2026-09-27.
reload_via_hup() {
    local container="$1"
    local marker="Completed loading of configuration file"
    local since
    since="$(date -u +%Y-%m-%dT%H:%M:%S)"
    if ! docker kill -s HUP "$container" >/dev/null 2>&1; then
        echo "❌ failed to send SIGHUP to ${container}" >&2
        return 1
    fi
    for _ in $(seq 1 "$RELOAD_POLL_ATTEMPTS"); do
        if docker logs --since "$since" "$container" 2>&1 | grep -qi "$marker"; then
            echo "  ✓ ${container} reloaded config"
            return 0
        fi
        sleep "$RELOAD_POLL_INTERVAL"
    done
    echo "❌ ${container} did not confirm config reload (no '${marker}' in logs since ${since})" >&2
    return 1
}

if $caddy_changed; then
    echo "🔁 config/caddy/Caddyfile changed, restarting caddy-lan (file bind-mount; compose up -d won't recreate it)..."
    if ! docker restart caddy-lan >/dev/null 2>&1; then
        echo "❌ failed to restart caddy-lan" >&2
        errors=$((errors + 1))
    else
        host_hash="$(sha256_of < config/caddy/Caddyfile)"
        container_hash="$(docker exec caddy-lan cat /etc/caddy/Caddyfile 2>/dev/null | sha256_of)"
        if [[ -z "$container_hash" || "$host_hash" != "$container_hash" ]]; then
            echo "❌ caddy-lan is not serving the new Caddyfile (host sha256=${host_hash} container sha256=${container_hash:-<none>})" >&2
            errors=$((errors + 1))
        else
            echo "  ✓ caddy-lan serving current Caddyfile (sha256=${host_hash})"
        fi
    fi
fi

if $prometheus_changed; then
    echo "🔁 config/prometheus/ changed, sending SIGHUP to prometheus..."
    reload_via_hup prometheus || errors=$((errors + 1))
fi

if $alertmanager_changed; then
    echo "🔁 config/alertmanager/ changed, sending SIGHUP to alertmanager..."
    reload_via_hup alertmanager || errors=$((errors + 1))
fi

if [[ $errors -gt 0 ]]; then
    echo "❌ apply-config-changes FAILED (${errors} verification failure(s))." >&2
    exit 1
fi

echo "✅ apply-config-changes: config reload/restart verified."
exit 0
