#!/usr/bin/env bash
# Create recovery artifacts and baseline diagnostics before host-level changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
BACKUP_ROOT="${PROJECT_ROOT}/backups/host-stabilization"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
LOG_FILE="${RUN_DIR}/run.log"

SKIP_APP_BACKUP=false
NO_SUDO=false

usage() {
  cat <<'EOF'
Usage: stabilize-host-prep.sh [--skip-app-backup] [--no-sudo]

Options:
  --skip-app-backup   Skip homelab appdata backup step
  --no-sudo           Skip privileged /etc snapshot collection
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-app-backup)
      SKIP_APP_BACKUP=true
      shift
      ;;
    --no-sudo)
      NO_SUDO=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "${RUN_DIR}"

log() {
  local message="$1"
  echo "[${TIMESTAMP}] ${message}" | tee -a "${LOG_FILE}"
}

capture_cmd() {
  local output_name="$1"
  shift
  log "Capturing ${output_name}"
  "$@" >"${RUN_DIR}/${output_name}.txt" 2>&1 || true
}

run_privileged_snapshot() {
  local archive_path="${RUN_DIR}/etc-config-snapshot.tar.gz"

  if [[ "${NO_SUDO}" == "true" ]]; then
    log "Skipping privileged snapshot (--no-sudo enabled)"
    return 0
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    log "sudo is not available; skipping privileged snapshot"
    return 0
  fi

  if ! sudo -v >/dev/null 2>&1; then
    log "sudo authentication unavailable; skipping privileged snapshot"
    return 0
  fi

  log "Creating privileged config snapshot at ${archive_path}"
  sudo tar -czf "${archive_path}" \
    /etc/fstab \
    /etc/default \
    /etc/netplan \
    /etc/ssh \
    /etc/systemd/system \
    /etc/rancher \
    /etc/crontab \
    /etc/cron.d \
    /etc/cron.daily \
    /etc/cron.hourly \
    /etc/cron.weekly \
    /etc/cron.monthly >/dev/null 2>&1 || {
      log "Privileged snapshot failed"
      return 1
    }
}

run_homelab_backup() {
  local backup_script="${PROJECT_ROOT}/scripts/maintenance/automated-backup.sh"
  local used_sudo=false

  if [[ "${NO_SUDO}" == "false" ]] && [[ "${EUID}" -ne 0 ]] && command -v sudo >/dev/null 2>&1; then
    log "Authenticating sudo for privileged backup access"
    if sudo -v >/dev/null 2>&1; then
      log "Running homelab backup with sudo (required for root-owned container volumes)"
      if sudo "${backup_script}"; then
        used_sudo=true
        log "Homelab backup completed with sudo"
      else
        log "Privileged homelab backup failed; retrying without sudo"
      fi
    else
      log "sudo authentication unavailable; retrying backup without sudo"
    fi
  fi

  if [[ "${used_sudo}" == "false" ]]; then
    log "Running homelab backup without sudo"
    "${backup_script}"
    log "Homelab backup completed without sudo"
  fi

  # If backup artifacts were created by root, hand ownership back to the
  # current operator for easier lifecycle management.
  if [[ "${used_sudo}" == "true" ]] && command -v sudo >/dev/null 2>&1; then
    sudo find "${PROJECT_ROOT}/backups" \
      -maxdepth 1 \
      -name "homelab_backup_*.tar.gz" \
      -mmin -10 \
      -exec chown "$(id -u):$(id -g)" {} + >/dev/null 2>&1 || true
  fi
}

log "Starting host stabilization prep"
log "Run directory: ${RUN_DIR}"

if [[ "${SKIP_APP_BACKUP}" == "false" ]]; then
  run_homelab_backup
else
  log "Skipping app backup (--skip-app-backup enabled)"
fi

capture_cmd baseline_memory bash -lc 'free -h; echo; swapon --show'
capture_cmd baseline_vmstat vmstat 1 10
capture_cmd top_processes bash -lc 'ps -eo pid,user,comm,rss,%mem --sort=-rss | sed -n "1,80p"'
capture_cmd running_services systemctl list-units --type=service --state=running --no-pager
capture_cmd enabled_units systemctl list-unit-files --state=enabled --no-pager
capture_cmd active_timers systemctl list-timers --no-pager
capture_cmd docker_ps docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
capture_cmd package_list bash -lc 'dpkg-query -W -f="${Package}\t${Version}\n" | sort'

if command -v kubectl >/dev/null 2>&1; then
  capture_cmd kubectl_context bash -lc 'kubectl config current-context 2>/dev/null || true'
  capture_cmd kubectl_nodes bash -lc 'kubectl get nodes -o wide 2>/dev/null || true'
fi

if [[ -f "${HOME}/.kube/config" ]]; then
  cp "${HOME}/.kube/config" "${RUN_DIR}/kubeconfig.snapshot"
  log "Saved kubeconfig snapshot"
fi

run_privileged_snapshot || true

log "Host stabilization prep complete"
log "Artifacts saved under ${RUN_DIR}"
