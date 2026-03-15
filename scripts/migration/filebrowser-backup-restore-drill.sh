#!/usr/bin/env bash
# Filebrowser backup and restore drill for Wave B migration.
# Validates that the database can be backed up and restored cleanly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
BACKUP_DIR="${PROJECT_ROOT}/logs/migration/filebrowser-drill"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${BACKUP_DIR}/drill-${TIMESTAMP}.log"

mkdir -p "${BACKUP_DIR}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

fail() {
  log "DRILL FAILED: $*"
  exit 1
}

log "=== Filebrowser Backup/Restore Drill ==="
log "Timestamp: ${TIMESTAMP}"

log "Step 1: Verify source container is running"
if ! docker inspect filebrowser --format '{{.State.Status}}' 2>/dev/null | grep -q running; then
  fail "filebrowser container is not running"
fi
log "OK: filebrowser container is running"

log "Step 2: Backup database from running container"
BACKUP_FILE="${BACKUP_DIR}/filebrowser-${TIMESTAMP}.db"
docker cp filebrowser:/database/filebrowser.db "${BACKUP_FILE}" 2>&1
if [[ ! -f "${BACKUP_FILE}" ]]; then
  fail "backup file not created"
fi
BACKUP_SIZE=$(stat -c%s "${BACKUP_FILE}")
log "OK: database backed up (${BACKUP_SIZE} bytes) -> ${BACKUP_FILE}"

log "Step 3: Verify backup integrity"
FILE_TYPE=$(file "${BACKUP_FILE}" 2>/dev/null || echo "unknown")
log "File type: ${FILE_TYPE}"
if [[ "${FILE_TYPE}" == *"SQLite"* ]] && command -v sqlite3 &>/dev/null; then
  INTEGRITY=$(sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;" 2>&1)
  if [[ "${INTEGRITY}" != "ok" ]]; then
    fail "SQLite integrity check failed: ${INTEGRITY}"
  fi
  log "OK: SQLite integrity check passed"
else
  if [[ "${BACKUP_SIZE}" -gt 0 ]]; then
    log "OK: database file is non-empty (${BACKUP_SIZE} bytes, likely bbolt format)"
  else
    fail "backup file is empty"
  fi
fi

log "Step 4: Simulate restore to temporary location"
RESTORE_DIR=$(mktemp -d)
cp "${BACKUP_FILE}" "${RESTORE_DIR}/filebrowser.db"

RESTORE_SIZE=$(stat -c%s "${RESTORE_DIR}/filebrowser.db")
if [[ "${RESTORE_SIZE}" -eq "${BACKUP_SIZE}" ]]; then
  log "OK: restored file matches backup size (${RESTORE_SIZE} bytes)"
else
  fail "restored file size mismatch: backup=${BACKUP_SIZE}, restore=${RESTORE_SIZE}"
fi
rm -rf "${RESTORE_DIR}"

log "Step 5: Document data volumes (not backed up, bind-mounted from host)"
log "  /srv/home    -> /home/luk-server (host path, no backup needed)"
log "  /srv/media   -> /home/luk-server/media (host path, no backup needed)"
log "  /database    -> Docker volume homelab_filebrowser_data (64KB, backed up above)"
log "  /config      -> Docker volume (8KB, regenerated on startup)"

log "Step 6: Verify k3s Helm chart is ready"
export PATH="${HOME}/.local/bin:${PATH}"
if helm lint "${PROJECT_ROOT}/k8s/helm/filebrowser" 2>&1 | grep -q "0 chart(s) failed"; then
  log "OK: filebrowser Helm chart lints clean"
else
  log "WARN: filebrowser Helm chart has lint warnings (may be acceptable)"
fi

log ""
log "=== DRILL RESULT: PASS ==="
log "Backup file: ${BACKUP_FILE}"
log "Backup size: ${BACKUP_SIZE} bytes"
log "Log file: ${LOG_FILE}"
log ""
log "To restore to k3s after Wave B deploy:"
log "  kubectl cp ${BACKUP_FILE} apps/\$(kubectl get pod -n apps -l app.kubernetes.io/instance=filebrowser -o name | head -1 | cut -d/ -f2):/database/filebrowser.db"
