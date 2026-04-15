#!/bin/bash
set -euo pipefail
# Reconcile homelab automation wiring:
# - Remove stale user crontab entries with dead paths
# - Sync managed systemd units from repository into /etc/systemd/system

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
UNITS_DIR="${PROJECT_ROOT}/scripts/systemd"
SYSTEMD_DIR="/etc/systemd/system"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

run_root() {
    if [ "${EUID}" -eq 0 ]; then
        "$@"
        return
    fi

    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo is required for systemd reconciliation" >&2
        exit 1
    fi

    sudo "$@"
}

cleanup_stale_user_cron() {
    local tmp_current tmp_filtered
    tmp_current="$(mktemp)"
    tmp_filtered="$(mktemp)"

    if ! crontab -l > "${tmp_current}" 2>/dev/null; then
        log "No user crontab found; skipping stale cron cleanup"
        rm -f "${tmp_current}" "${tmp_filtered}"
        return
    fi

    cp "${tmp_current}" "${tmp_filtered}"

    local stale_paths=(
        "/home/luk-server/homelab/scripts/homelab_manager/cli.py"
        "/home/luk-server/scripts/homelab_manager/cli.py"
        "/home/luk-server/satisfactory-server/scripts/monitor.sh"
    )

    local removed=0
    local next_file
    for stale_path in "${stale_paths[@]}"; do
        next_file="$(mktemp)"
        if grep -Fq "${stale_path}" "${tmp_filtered}"; then
            removed=$((removed + 1))
        fi
        grep -Fv "${stale_path}" "${tmp_filtered}" > "${next_file}" || true
        mv "${next_file}" "${tmp_filtered}"
    done

    if ! cmp -s "${tmp_current}" "${tmp_filtered}"; then
        crontab "${tmp_filtered}"
        log "Removed stale crontab entries referencing missing paths"
    else
        log "No stale crontab entries found"
    fi

    if [ "${removed}" -gt 0 ]; then
        log "Stale entry patterns removed: ${removed}"
    fi

    rm -f "${tmp_current}" "${tmp_filtered}"
}

sync_systemd_units() {
    local managed_units=(
        "homelab-docker.service"
        "satisfactory-server.service"
        "lukbot.service"
        "homelab-update.service"
        "homelab-update.timer"
        "homelab-watchdog.service"
        "homelab-watchdog.timer"
    )

    if [ ! -d "${UNITS_DIR}" ]; then
        echo "Unit directory not found: ${UNITS_DIR}" >&2
        exit 1
    fi

    log "Syncing managed systemd units to ${SYSTEMD_DIR}"
    for unit in "${managed_units[@]}"; do
        local src dst
        src="${UNITS_DIR}/${unit}"
        dst="${SYSTEMD_DIR}/${unit}"

        if [ ! -f "${src}" ]; then
            log "Skipping missing unit in repo: ${unit}"
            continue
        fi

        run_root install -m 644 "${src}" "${dst}"
        log "Installed ${unit}"
    done

    run_root systemctl daemon-reload
    run_root systemctl enable homelab-update.timer homelab-watchdog.timer
    run_root systemctl restart homelab-update.timer homelab-watchdog.timer
    log "Reloaded systemd and ensured update/watchdog timers are enabled"
}

main() {
    log "Starting automation reconciliation"
    cleanup_stale_user_cron
    sync_systemd_units
    log "Automation reconciliation completed"
}

main "$@"
