#!/bin/bash
# Mirror the local (encrypted) kopia repo to an offsite target (#266).
#
# The kopia repo at /opt/kopia-repo is already encrypted at rest, so the offsite
# copy is safe to store anywhere (another host, a disk, or a cloud bucket) without
# additional encryption. Recovery needs both this mirror AND the repo password
# (KOPIA_REPO_PASSWORD, kept off-host in SOPS — see #272 / docs/secrets.md).
#
# Two backends, selected in .env (rclone takes precedence if both are set):
#   KOPIA_OFFSITE_RCLONE_REMOTE=gdrive:homelab-kopia   # rclone remote (Drive/S3/B2/…)
#   KOPIA_OFFSITE_TARGET=luk@host:/srv/kopia-offsite    # rsync (host/disk)
# Both empty → sync is DISABLED (this script exits 0 cleanly).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_FILE="${HOMELAB_DIR}/logs/kopia-offsite.log"
REPO="/opt/kopia-repo"

mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

envval() { grep -E "^$1=" "${HOMELAB_DIR}/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' || true; }
RCLONE_REMOTE="$(envval KOPIA_OFFSITE_RCLONE_REMOTE)"
TARGET="$(envval KOPIA_OFFSITE_TARGET)"
HC_URL="$(envval KOPIA_OFFSITE_HC_PING_URL)"

if [[ -z "${RCLONE_REMOTE}" && -z "${TARGET}" ]]; then
  log "No offsite target set (KOPIA_OFFSITE_RCLONE_REMOTE / KOPIA_OFFSITE_TARGET) — skipping."
  exit 0
fi

# Source guard (both backends): never mirror a missing/empty/invalid source over a
# good offsite copy — the mirror propagates deletes. Require the repo marker.
if [[ ! -s "${REPO}/kopia.repository.f" && ! -s "${REPO}/kopia.repository" ]]; then
  log "ERROR: ${REPO} has no kopia repository marker — refusing to sync (would risk wiping offsite)."
  exit 1
fi

ping_hc() { if [[ -n "${HC_URL}" ]]; then curl -fsS -m 10 "${HC_URL}" >/dev/null 2>&1 || true; fi; }
fail_hc() { if [[ -n "${HC_URL}" ]]; then curl -fsS -m 10 "${HC_URL}/fail" >/dev/null 2>&1 || true; fi; }
size_of() { du -sh "${REPO}" 2>/dev/null | cut -f1; }

if [[ -n "${RCLONE_REMOTE}" ]]; then
  # rclone remote must be "remote:path" with a non-empty remote name AND a path
  # that is not empty or the remote root (`remote:`, `remote:/`, `remote://` all
  # point at the drive/bucket root — rclone sync there mirror+deletes everything).
  rname="${RCLONE_REMOTE%%:*}"
  rpath="${RCLONE_REMOTE#*:}"
  if [[ "${RCLONE_REMOTE}" != *:* || -z "${rname}" ]]; then
    log "ERROR: KOPIA_OFFSITE_RCLONE_REMOTE must be 'remote:path' with a non-empty remote name; got '${RCLONE_REMOTE}'." ; exit 1
  fi
  if [[ -z "${rpath}" || "${rpath}" =~ ^/+$ ]]; then
    log "ERROR: KOPIA_OFFSITE_RCLONE_REMOTE path must not be empty or the remote root; got '${RCLONE_REMOTE}'." ; exit 1
  fi
  command -v rclone >/dev/null 2>&1 || { log "ERROR: rclone not installed."; exit 1; }
  log "Syncing ${REPO} → rclone:${RCLONE_REMOTE} (encrypted repo)"
  if rclone sync "${REPO}" "${RCLONE_REMOTE}" --transfers 4 --checkers 8 >>"$LOG_FILE" 2>&1; then
    log "Offsite rclone sync OK ($(size_of))"; ping_hc
  else
    log "ERROR: rclone sync to ${RCLONE_REMOTE} failed"; fail_hc; exit 1
  fi
else
  # rsync backend. Target guard (rsync --delete is destructive): require an absolute
  # local path or a remote with an absolute path; reject root/source/relative.
  if [[ "${TARGET%/}" == "${REPO%/}" ]]; then
    log "ERROR: KOPIA_OFFSITE_TARGET equals the source ${REPO} — refusing."; exit 1
  fi
  case "${TARGET}" in
    /)    log "ERROR: refusing KOPIA_OFFSITE_TARGET='/'." ; exit 1 ;;
    /*)   : ;;          # absolute local path with content — ok
    *:/)  log "ERROR: refusing remote root '${TARGET}'." ; exit 1 ;;
    *:/*) : ;;          # remote host:/absolute-path — ok
    *)    log "ERROR: KOPIA_OFFSITE_TARGET must be an absolute path (/...) or a remote with an absolute path (host:/...); got '${TARGET}'." ; exit 1 ;;
  esac
  log "Syncing ${REPO} → ${TARGET} (rsync --delete, encrypted repo)"
  if rsync -aH --delete --partial "${REPO}/" "${TARGET}/" >>"$LOG_FILE" 2>&1; then
    log "Offsite rsync OK ($(size_of))"; ping_hc
  else
    log "ERROR: rsync to ${TARGET} failed"; fail_hc; exit 1
  fi
fi
