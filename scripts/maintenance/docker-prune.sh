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
log "pruning stopped non-compose containers older than 30d..."
docker container prune -f --filter "until=720h" --filter "label!=com.docker.compose.project" 2>&1 | tail -3 | tee -a "$LOG_FILE"
# Filters AND together, so compose one-off containers (`docker compose run`) get
# their own pass; they are disposable, unlike a stopped service container.
docker container prune -f --filter "until=720h" --filter "label=com.docker.compose.oneoff=True" 2>&1 | tail -3 | tee -a "$LOG_FILE"

log "after:  $(docker system df --format '{{.Type}}:{{.Size}}/{{.Reclaimable}}' | tr '\n' ' ')"
log "=== docker-prune done ==="
