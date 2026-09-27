#!/usr/bin/env bash
# Weekly Docker storage reclamation.
#
# Prunes build cache and unused images older than 30 days. Leaves volumes
# alone (they may hold running-service state). Safe to re-run; idempotent.
#
# Why 30d cutoff: protects the working set that developers pull between runs
# while still reclaiming long-dead layers. The unbounded `-af` form this
# script replaces was only used once manually to recover from a 64 GB build
# cache buildup (2026-04-20) and is too aggressive for a scheduled job.

set -euo pipefail

LOG_DIR="${LOG_DIR:-/var/log/homelab}"
LOG_FILE="${LOG_DIR}/docker-prune.log"
mkdir -p "$LOG_DIR"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG_FILE"; }

log "=== docker-prune start ==="
log "before: $(docker system df --format '{{.Type}}:{{.Size}}/{{.Reclaimable}}' | tr '\n' ' ')"

log "pruning build cache older than 30d..."
docker builder prune -af --filter "until=720h" 2>&1 | tail -3 | tee -a "$LOG_FILE"

log "pruning dangling + unused images older than 30d..."
docker image prune -af --filter "until=720h" 2>&1 | tail -3 | tee -a "$LOG_FILE"

# Never compose-managed containers: a stopped one is a failure to investigate, not
# garbage. On 2026-09-20 homeassistant and nextcloud failed to start at boot, this
# timer caught up minutes later (Persistent=true) and removed them, then their
# images went too; both stayed down for 6 days with the data intact but no container.
# Compose one-off containers (`docker compose run`) are disposable and still go.
# Selected here, not with `container prune`: Docker 29 rejects `label!=` on
# container filters ("invalid filter 'label!'").
log "removing stopped non-compose and one-off containers older than 30d..."
cutoff=$(date -d '30 days ago' +%s)
mapfile -t stopped < <(docker ps -aq --filter status=exited --filter status=created --filter status=dead)
stale=()
if [ ${#stopped[@]} -gt 0 ]; then
  while IFS='|' read -r id created project oneoff; do
    if [ -n "$project" ] && [ "$oneoff" != "True" ]; then
      continue
    fi
    if [ "$(date -d "$created" +%s)" -lt "$cutoff" ]; then
      stale+=("$id")
    fi
  done < <(docker inspect -f '{{.Id}}|{{.Created}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.oneoff"}}' "${stopped[@]}")
fi
if [ ${#stale[@]} -gt 0 ]; then
  docker rm "${stale[@]}" 2>&1 | tail -3 | tee -a "$LOG_FILE"
fi
log "removed ${#stale[@]} containers"

log "after:  $(docker system df --format '{{.Type}}:{{.Size}}/{{.Reclaimable}}' | tr '\n' ' ')"
log "=== docker-prune done ==="
