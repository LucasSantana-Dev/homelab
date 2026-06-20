#!/bin/bash
# Mirror the local (encrypted) kopia repo to an offsite target via rsync (#266).
#
# The kopia repo at /opt/kopia-repo is already encrypted at rest, so the offsite
# copy is safe to store on another host without additional encryption. Recovery
# needs both this mirror AND the repo password (KOPIA_REPO_PASSWORD, kept
# off-host in SOPS — see #272 / docs/secrets.md).
#
# Target is operator-configured via KOPIA_OFFSITE_TARGET in .env, e.g.:
#   KOPIA_OFFSITE_TARGET=luk@pc-do-luk:/srv/kopia-offsite
#   KOPIA_OFFSITE_TARGET=/mnt/usb-backup/kopia-offsite   (a mounted disk)
# Empty/unset → sync is DISABLED (this script exits 0 cleanly), so installing the
# timer before choosing a target is harmless.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_FILE="${HOMELAB_DIR}/logs/kopia-offsite.log"
REPO="/opt/kopia-repo"

mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

TARGET="$(grep -E '^KOPIA_OFFSITE_TARGET=' "${HOMELAB_DIR}/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"
HC_URL="$(grep -E '^KOPIA_OFFSITE_HC_PING_URL=' "${HOMELAB_DIR}/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)"

if [[ -z "${TARGET}" ]]; then
  log "KOPIA_OFFSITE_TARGET not set — offsite sync disabled, skipping. Set it in .env to enable."
  exit 0
fi

# Sanity guard: never mirror a missing/empty/invalid source over a good offsite
# copy (rsync --delete would otherwise wipe it). Require the repo's format marker.
if [[ ! -s "${REPO}/kopia.repository.f" && ! -s "${REPO}/kopia.repository" ]]; then
  log "ERROR: ${REPO} has no kopia repository marker — refusing to sync (would risk wiping offsite)."
  exit 1
fi

log "Syncing ${REPO} → ${TARGET} (rsync --delete, encrypted repo)"
# -a archive, -H hardlinks, --delete mirror, --partial resume; rsync over ssh for
# a remote target, plain path for a mounted disk (rsync handles both).
if rsync -aH --delete --partial "${REPO}/" "${TARGET}/" >>"$LOG_FILE" 2>&1; then
  size="$(du -sh "${REPO}" 2>/dev/null | cut -f1)"
  log "Offsite sync OK (${size})"
  if [[ -n "${HC_URL}" ]]; then curl -fsS -m 10 "${HC_URL}" >/dev/null 2>&1 || true; fi
else
  log "ERROR: rsync to ${TARGET} failed"
  if [[ -n "${HC_URL}" ]]; then curl -fsS -m 10 "${HC_URL}/fail" >/dev/null 2>&1 || true; fi
  exit 1
fi
