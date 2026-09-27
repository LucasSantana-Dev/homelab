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
# Bounded so a long-lived container's full log is never read: `--tail` costs
# the same regardless of how much history (or how many rotated files, per the
# compose `max-file` retention) sits behind it.
LOG_TAIL_LINES="${LOG_TAIL_LINES:-200}"
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
    committed_changed="$(git ls-files -- "${MANAGED_PATHS[@]}")"
else
    committed_changed="$(git diff --name-only "${OLD_SHA}" HEAD -- "${MANAGED_PATHS[@]}")"
fi
# DEPLOY_FORCE=1 (Makefile dirty-file gate override) lets `make deploy` run
# with uncommitted edits to tracked config still sitting in the worktree.
# Those never show up in old-sha..HEAD, so diff the worktree against HEAD too
# or a DEPLOY_FORCE=1 Caddy/Prometheus/Alertmanager edit would silently never
# get restarted/reloaded.
worktree_changed="$(git diff --name-only HEAD -- "${MANAGED_PATHS[@]}" 2>/dev/null || true)"
changed_files="$(printf '%s\n%s\n' "$committed_changed" "$worktree_changed")"

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

log_tail() {
    docker logs --tail "$LOG_TAIL_LINES" "$1" 2>&1
}

# Prometheus and Alertmanager both use the same config-reload machinery and
# log "Completed loading of configuration file" on success, whether triggered
# by SIGHUP or (for prometheus, which runs --web.enable-lifecycle) the
# /-/reload HTTP endpoint. SIGHUP works for both regardless of that flag and
# does not depend on knowing the container's bound host/port, so it is used
# for both. This is what was actually run and verified working on the host
# on 2026-09-27.
#
# Verification anchors on the single last log line before the signal (an
# O(1) `--tail 1` read, cheap and stable regardless of total log size or a
# rotation happening in between) rather than a wall-clock `--since` cutoff (a
# coarse 1s cutoff can match a pre-existing "Completed loading" line and
# falsely confirm a reload that never happened) or a raw line count (which
# stops distinguishing old from new once a bounded `--tail` window is full,
# which it usually is on a long-lived container). Content strictly after that
# anchor line, within a bounded tail, is what counts as new.
reload_via_hup() {
    local container="$1"
    local marker="Completed loading of configuration file"
    local anchor after_tail anchor_line new_lines
    anchor="$(docker logs --tail 1 "$container" 2>&1)"
    if ! docker kill -s HUP "$container" >/dev/null 2>&1; then
        echo "❌ failed to send SIGHUP to ${container}" >&2
        return 1
    fi
    for _ in $(seq 1 "$RELOAD_POLL_ATTEMPTS"); do
        after_tail="$(log_tail "$container")"
        if [[ -z "$anchor" ]]; then
            # No prior log line to anchor on (fresh container): everything in
            # the tail is new.
            new_lines="$after_tail"
        else
            anchor_line="$(printf '%s\n' "$after_tail" | grep -Fxn "$anchor" | tail -1 | cut -d: -f1)"
            if [[ -n "$anchor_line" ]]; then
                new_lines="$(printf '%s\n' "$after_tail" | tail -n "+$((anchor_line + 1))")"
            else
                # Anchor rolled out of the tail window: enough new lines
                # appeared that the whole window is new content.
                new_lines="$after_tail"
            fi
        fi
        if printf '%s\n' "$new_lines" | grep -qi "$marker"; then
            echo "  ✓ ${container} reloaded config"
            return 0
        fi
        sleep "$RELOAD_POLL_INTERVAL"
    done
    echo "❌ ${container} did not confirm config reload (no new '${marker}' log line)" >&2
    return 1
}

if $caddy_changed; then
    echo "🔁 config/caddy/Caddyfile changed, validating before restarting caddy-lan (file bind-mount; compose up -d won't recreate it)..."
    # The bind mount is live, so the container already sees the new file even
    # before a restart: validate it in place first. An invalid Caddyfile must
    # never take the proxy down, so a failed validation skips the restart
    # entirely and leaves caddy-lan serving the last-known-good config.
    if ! docker exec caddy-lan caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; then
        echo "❌ new Caddyfile fails \`caddy validate\`, refusing to restart caddy-lan (left running on the old, valid config)" >&2
        errors=$((errors + 1))
    else
        restart_count_before="$(docker inspect -f '{{.RestartCount}}' caddy-lan 2>/dev/null || echo 0)"
        if ! docker restart caddy-lan >/dev/null 2>&1; then
            echo "❌ failed to restart caddy-lan" >&2
            errors=$((errors + 1))
        else
            # Give a crash-looping container (restart: unless-stopped) a
            # moment to actually crash before we check.
            sleep "$RELOAD_POLL_INTERVAL"
            running="$(docker inspect -f '{{.State.Running}}' caddy-lan 2>/dev/null || echo false)"
            restart_count_after="$(docker inspect -f '{{.RestartCount}}' caddy-lan 2>/dev/null || echo 0)"
            host_hash="$(sha256_of < config/caddy/Caddyfile)"
            container_hash="$(docker exec caddy-lan cat /etc/caddy/Caddyfile 2>/dev/null | sha256_of)"
            if [[ "$running" != "true" ]]; then
                echo "❌ caddy-lan is not running after restart" >&2
                errors=$((errors + 1))
            elif [[ "$restart_count_after" != "$restart_count_before" ]]; then
                echo "❌ caddy-lan is crash-looping after restart (RestartCount ${restart_count_before} -> ${restart_count_after})" >&2
                errors=$((errors + 1))
            elif [[ -z "$container_hash" || "$host_hash" != "$container_hash" ]]; then
                echo "❌ caddy-lan is not serving the new Caddyfile (host sha256=${host_hash} container sha256=${container_hash:-<none>})" >&2
                errors=$((errors + 1))
            # Same probe as the compose healthcheck (compose/lan-proxy.yml):
            # a matching file hash only proves the bind mount is current, not
            # that caddy's own admin API (and therefore the LAN proxy) is up.
            elif ! docker exec caddy-lan wget -qO- --tries=1 http://127.0.0.1:2019/config/ >/dev/null 2>&1; then
                echo "❌ caddy-lan admin API is not answering after restart" >&2
                errors=$((errors + 1))
            else
                echo "  ✓ caddy-lan validated, restarted, running, admin API answering, and serving current Caddyfile (sha256=${host_hash})"
            fi
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
