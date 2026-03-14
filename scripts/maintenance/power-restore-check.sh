#!/bin/bash
# Validate host readiness for power-loss auto recovery.

set -euo pipefail

log() {
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

status_ok=0
status_warn=0
status_fail=0

ok() {
    status_ok=$((status_ok + 1))
    log "OK: $*"
}

warn() {
    status_warn=$((status_warn + 1))
    log "WARN: $*"
}

fail() {
    status_fail=$((status_fail + 1))
    log "FAIL: $*"
}

check_unit_enabled() {
    local unit="$1"
    local state
    state="$(systemctl is-enabled "${unit}" 2>/dev/null || true)"
    if [ "${state}" = "enabled" ]; then
        ok "${unit} is enabled"
    else
        fail "${unit} is not enabled (state=${state:-unknown})"
    fi
}

check_unit_active() {
    local unit="$1"
    local state
    state="$(systemctl is-active "${unit}" 2>/dev/null || true)"
    if [ "${state}" = "active" ]; then
        ok "${unit} is active"
    else
        warn "${unit} is not active right now (state=${state:-unknown})"
    fi
}

log "Power-restore readiness check"
log "============================"

if [ -r /sys/class/dmi/id/sys_vendor ]; then
    log "Hardware: $(cat /sys/class/dmi/id/sys_vendor 2>/dev/null) / $(cat /sys/class/dmi/id/product_name 2>/dev/null)"
    log "Firmware: $(cat /sys/class/dmi/id/bios_vendor 2>/dev/null) $(cat /sys/class/dmi/id/bios_version 2>/dev/null)"
else
    warn "DMI information is not readable on this host"
fi

log "Booted: $(uptime -s 2>/dev/null || echo unknown)"
log "Kernel: $(uname -r)"

check_unit_enabled "docker.service"
check_unit_enabled "tailscaled.service"
check_unit_enabled "homelab-docker.service"
check_unit_enabled "homelab-update.timer"
check_unit_enabled "homelab-watchdog.timer"

check_unit_active "docker.service"
check_unit_active "tailscaled.service"
check_unit_active "homelab-update.timer"
check_unit_active "homelab-watchdog.timer"

if command -v docker >/dev/null 2>&1; then
    running_containers="$(docker ps --format '{{.Names}}' | wc -l | tr -d ' ')"
    ok "Docker is reachable (running containers=${running_containers})"
else
    fail "docker command not found"
fi

log ""
log "Manual firmware verification required:"
log "1) Enter BIOS/UEFI and set Restore on AC/Power Loss = Power On"
log "2) Disable ErP/Deep Sleep (if present), otherwise auto power-on may be blocked"
log "3) Run a physical AC-loss drill and verify host boots without pressing power button"

log ""
log "Summary: ok=${status_ok} warn=${status_warn} fail=${status_fail}"

if [ "${status_fail}" -gt 0 ]; then
    exit 1
fi
