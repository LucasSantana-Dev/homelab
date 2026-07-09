#!/bin/bash
set -euo pipefail
# Homelab resilience watchdog:
# - Detects degraded host/service/container state
# - Runs a bounded recovery ladder
# - Escalates to reboot when enabled and needed

set -euo pipefail

HOMELAB_DIR="/home/luk-server/homelab"
ENV_FILE="${HOMELAB_DIR}/.env"
LOG_FILE="${HOMELAB_DIR}/logs/watchdog.log"

STATE_FILE="/var/lib/homelab-watchdog/state.json"
LOCK_FILE="${HOMELAB_DIR}/logs/homelab-watchdog.lock"

REBOOT_COOLDOWN_SECONDS=$((6 * 60 * 60))
OOM_LOOKBACK_MINUTES=5
OOM_THRESHOLD=3

# Services the watchdog expects to always be running.
# Keep in sync with actually-deployed services (see `docker ps`).
# For the LAN-wide stack the canonical set is: pihole, caddy-lan, lucky-*, craftvaria-*.
CRITICAL_CONTAINERS=(
    "pihole"
    "caddy-lan"
    "craftvaria-minecraft"
    "lucky-bot"
)

mkdir -p "$(dirname "${LOG_FILE}")"

log() {
    local message
    message="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "${message}" | tee -a "${LOG_FILE}"
}

get_env_value() {
    local key value
    key="$1"
    if [ ! -f "${ENV_FILE}" ]; then
        return 0
    fi

    value="$(grep -E "^${key}=" "${ENV_FILE}" 2>/dev/null | cut -d'=' -f2- | tr -d '\r' || true)"
    printf "%s" "${value}"
}

to_bool() {
    local raw
    raw="$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')"
    case "${raw}" in
        1|true|yes|on) echo "true" ;;
        *) echo "false" ;;
    esac
}

send_discord() {
    local msg payload http_code
    msg="$1"

    if [ -z "${LUCKY_NOTIFY_URL}" ] || [ -z "${LUCKY_NOTIFY_KEY}" ] || [ -z "${LUCKY_NOTIFY_CHANNEL_ID}" ]; then
        return 0
    fi

    payload=$(LUCKY_MSG="${msg}" LUCKY_CHAN="${LUCKY_NOTIFY_CHANNEL_ID}" python3 -c '
import json, os, socket
content = "[{}] {}".format(socket.gethostname(), os.environ["LUCKY_MSG"])
print(json.dumps({"channelId": os.environ["LUCKY_CHAN"], "content": content[:1900]}))
')

    http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 \
        -H "Content-Type: application/json" \
        -H "X-Notify-Key: ${LUCKY_NOTIFY_KEY}" \
        -d "${payload}" \
        "${LUCKY_NOTIFY_URL}" || echo "000")

    if [ "${http_code}" != "204" ] && [ "${http_code}" != "200" ]; then
        log "Lucky notify failed (HTTP ${http_code}) — check LUCKY_NOTIFY_* env + lucky-backend health"
    fi
}
ensure_state_path() {
    local state_dir
    state_dir="$(dirname "${STATE_FILE}")"

    if mkdir -p "${state_dir}" 2>/dev/null; then
        if [ -e "${STATE_FILE}" ] && [ -w "${STATE_FILE}" ]; then
            return
        fi
        if [ ! -e "${STATE_FILE}" ] && [ -w "${state_dir}" ]; then
            return
        fi
    fi

    STATE_FILE="${HOMELAB_DIR}/logs/watchdog-state.json"
    state_dir="$(dirname "${STATE_FILE}")"
    if mkdir -p "${state_dir}" 2>/dev/null; then
        if [ -e "${STATE_FILE}" ] && [ -w "${STATE_FILE}" ]; then
            log "Warning: using fallback state path ${STATE_FILE}"
            return
        fi
        if [ ! -e "${STATE_FILE}" ] && [ -w "${state_dir}" ]; then
            log "Warning: using fallback state path ${STATE_FILE}"
            return
        fi
    fi

    STATE_FILE="/tmp/homelab-watchdog/state.json"
    mkdir -p "$(dirname "${STATE_FILE}")" 2>/dev/null || true
    log "Warning: using fallback state path ${STATE_FILE}"
}

ensure_lock_path() {
    local lock_dir
    lock_dir="$(dirname "${LOCK_FILE}")"
    if mkdir -p "${lock_dir}" 2>/dev/null; then
        if [ -e "${LOCK_FILE}" ] && [ -w "${LOCK_FILE}" ]; then
            return
        fi
        if [ ! -e "${LOCK_FILE}" ] && [ -w "${lock_dir}" ]; then
            return
        fi
    fi

    LOCK_FILE="/tmp/homelab-watchdog.lock"
    mkdir -p "$(dirname "${LOCK_FILE}")" 2>/dev/null || true
    log "Warning: using fallback lock path ${LOCK_FILE}"
}

init_state_file() {
    if [ -f "${STATE_FILE}" ]; then
        return
    fi

    python3 - "${STATE_FILE}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
state = {
    "incident_active": False,
    "incident_start_epoch": 0,
    "last_reboot_epoch": 0,
    "last_status": "unknown",
    "last_check_epoch": 0,
    "steps": {
        "restart_containers_epoch": 0,
        "restart_docker_epoch": 0,
        "compose_up_epoch": 0,
        "reboot_epoch": 0,
    },
}
path.write_text(json.dumps(state, indent=2))
PY
}

load_state() {
    eval "$(python3 - "${STATE_FILE}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
state = json.loads(path.read_text())
steps = state.get("steps", {})

print(f"incident_active={1 if state.get('incident_active', False) else 0}")
print(f"incident_start_epoch={int(state.get('incident_start_epoch', 0) or 0)}")
print(f"last_reboot_epoch={int(state.get('last_reboot_epoch', 0) or 0)}")
print(f"last_check_epoch={int(state.get('last_check_epoch', 0) or 0)}")
print(f"last_status='{state.get('last_status', 'unknown')}'")
print(f"step_restart_containers_epoch={int(steps.get('restart_containers_epoch', 0) or 0)}")
print(f"step_restart_docker_epoch={int(steps.get('restart_docker_epoch', 0) or 0)}")
print(f"step_compose_up_epoch={int(steps.get('compose_up_epoch', 0) or 0)}")
print(f"step_reboot_epoch={int(steps.get('reboot_epoch', 0) or 0)}")
PY
)"
}

save_state() {
    python3 - "${STATE_FILE}" <<'PY'
import json
import os
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
state = {
    "incident_active": os.environ["WD_INCIDENT_ACTIVE"] == "1",
    "incident_start_epoch": int(os.environ["WD_INCIDENT_START"]),
    "last_reboot_epoch": int(os.environ["WD_LAST_REBOOT"]),
    "last_status": os.environ["WD_LAST_STATUS"],
    "last_check_epoch": int(os.environ["WD_LAST_CHECK"]),
    "steps": {
        "restart_containers_epoch": int(os.environ["WD_STEP_RESTART_CONTAINERS"]),
        "restart_docker_epoch": int(os.environ["WD_STEP_RESTART_DOCKER"]),
        "compose_up_epoch": int(os.environ["WD_STEP_COMPOSE_UP"]),
        "reboot_epoch": int(os.environ["WD_STEP_REBOOT"]),
    },
}
path.write_text(json.dumps(state, indent=2))
PY
}

update_state_env_and_save() {
    export WD_INCIDENT_ACTIVE="${incident_active}"
    export WD_INCIDENT_START="${incident_start_epoch}"
    export WD_LAST_REBOOT="${last_reboot_epoch}"
    export WD_LAST_STATUS="${last_status}"
    export WD_LAST_CHECK="${last_check_epoch}"
    export WD_STEP_RESTART_CONTAINERS="${step_restart_containers_epoch}"
    export WD_STEP_RESTART_DOCKER="${step_restart_docker_epoch}"
    export WD_STEP_COMPOSE_UP="${step_compose_up_epoch}"
    export WD_STEP_REBOOT="${step_reboot_epoch}"
    save_state
}

is_any_service_active() {
    local service_name
    for service_name in "$@"; do
        if systemctl is-active --quiet "${service_name}" >/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
}

collect_degradation_reasons() {
    local reasons=()

    if ! is_any_service_active "docker.service"; then
        reasons+=("docker.service is inactive")
    fi
    if ! is_any_service_active "ssh.service" "sshd.service"; then
        reasons+=("ssh service is inactive")
    fi
    if ! is_any_service_active "tailscaled.service"; then
        reasons+=("tailscaled.service is inactive")
    fi

    if is_any_service_active "docker.service"; then
        local container status
        for container in "${CRITICAL_CONTAINERS[@]}"; do
            status="$(docker inspect --format='{{.State.Status}}' "${container}" 2>/dev/null || echo "missing")"
            if [ "${status}" != "running" ]; then
                reasons+=("container ${container} is ${status}")
            fi
        done
    fi

    local oom_count
    oom_count="$(journalctl -k --since "${OOM_LOOKBACK_MINUTES} minutes ago" --no-pager 2>/dev/null | grep -Ec 'Memory cgroup out of memory: Killed process .*\(cadvisor\)' || true)"
    if [ "${oom_count}" -ge "${OOM_THRESHOLD}" ]; then
        reasons+=("cadvisor OOM kill loop (${oom_count} events in ${OOM_LOOKBACK_MINUTES}m)")
    fi

    if [ "${WATCHDOG_FORCE_DEGRADED}" = "true" ]; then
        reasons+=("forced degraded mode enabled")
    fi

    printf "%s\n" "${reasons[@]}"
}

run_action() {
    local action_name
    action_name="$1"
    shift

    log "Running action: ${action_name}"
    if "$@" >> "${LOG_FILE}" 2>&1; then
        log "Action succeeded: ${action_name}"
        send_discord "Watchdog action succeeded: ${action_name}"
        return 0
    fi

    log "Action failed: ${action_name}"
    send_discord "Watchdog action failed: ${action_name}"
    return 1
}

action_restart_cadvisor_loki() {
    local targets=()
    local candidate
    for candidate in cadvisor loki; do
        if docker inspect "${candidate}" >/dev/null 2>&1; then
            targets+=("${candidate}")
        fi
    done

    if [ "${#targets[@]}" -eq 0 ]; then
        log "No cadvisor/loki containers found to restart"
        return 1
    fi

    docker restart "${targets[@]}"
}

action_restart_docker() {
    systemctl restart docker.service
}

action_compose_up() {
    cd "${HOMELAB_DIR}"
    docker compose up -d
}

action_reboot_host() {
    if [ "${WATCHDOG_REBOOT_ENABLED}" != "true" ]; then
        log "Dry-run mode: reboot suppressed (WATCHDOG_REBOOT_ENABLED=false)"
        send_discord "Watchdog dry-run: reboot suppressed (WATCHDOG_REBOOT_ENABLED=false)"
        return 2
    fi

    send_discord "Watchdog escalating to host reboot"
    systemctl reboot
}

main() {
    local now elapsed_seconds degraded reason_text oom_only_incident
    now="$(date +%s)"

    WATCHDOG_FORCE_DEGRADED="false"
    while [ "${#}" -gt 0 ]; do
        case "$1" in
            --force-degraded)
                WATCHDOG_FORCE_DEGRADED="true"
                shift
                ;;
            *)
                log "Ignoring unknown argument: $1"
                shift
                ;;
        esac
    done

    WATCHDOG_REBOOT_ENABLED="$(to_bool "$(get_env_value WATCHDOG_REBOOT_ENABLED)")"
    WATCHDOG_RECOVERY_WINDOW_MINUTES="$(get_env_value WATCHDOG_RECOVERY_WINDOW_MINUTES)"
    WATCHDOG_RECOVERY_WINDOW_MINUTES="${WATCHDOG_RECOVERY_WINDOW_MINUTES:-10}"
    if ! [[ "${WATCHDOG_RECOVERY_WINDOW_MINUTES}" =~ ^[0-9]+$ ]]; then
        WATCHDOG_RECOVERY_WINDOW_MINUTES=10
    fi
    LUCKY_NOTIFY_URL="$(get_env_value LUCKY_NOTIFY_URL)"
    LUCKY_NOTIFY_KEY="$(get_env_value LUCKY_NOTIFY_KEY)"
    LUCKY_NOTIFY_CHANNEL_ID="$(get_env_value LUCKY_NOTIFY_CHANNEL_ID)"
    if [ "${WATCHDOG_FORCE_DEGRADED}" != "true" ]; then
        WATCHDOG_FORCE_DEGRADED="$(to_bool "$(get_env_value WATCHDOG_FORCE_DEGRADED)")"
    fi

    ensure_state_path
    init_state_file
    load_state

    ensure_lock_path
    exec 9>"${LOCK_FILE}"
    if ! flock -n 9; then
        log "Another watchdog run is still active; skipping"
        exit 0
    fi

    last_check_epoch="${now}"

    mapfile -t reasons < <(collect_degradation_reasons)
    degraded=0
    if [ "${#reasons[@]}" -gt 0 ] && [ -n "${reasons[0]}" ]; then
        degraded=1
    fi
    oom_only_incident=0
    if [ "${#reasons[@]}" -eq 1 ] && [[ "${reasons[0]}" == cadvisor\ OOM\ kill\ loop* ]]; then
        oom_only_incident=1
    fi

    if [ "${degraded}" -eq 1 ]; then
        reason_text="$(IFS='; '; echo "${reasons[*]}")"
        log "Degraded state detected: ${reason_text}"

        if [ "${incident_active}" -eq 0 ]; then
            incident_active=1
            incident_start_epoch="${now}"
            step_restart_containers_epoch=0
            step_restart_docker_epoch=0
            step_compose_up_epoch=0
            step_reboot_epoch=0
            send_discord "Watchdog incident detected: ${reason_text}"
        fi

        elapsed_seconds=$((now - incident_start_epoch))

        if [ "${step_restart_containers_epoch}" -eq 0 ]; then
            run_action "restart cadvisor+loki" action_restart_cadvisor_loki || true
            step_restart_containers_epoch="${now}"
        fi

        if [ "${oom_only_incident}" -eq 0 ] && [ "${elapsed_seconds}" -ge $((3 * 60)) ] && [ "${step_restart_docker_epoch}" -eq 0 ]; then
            run_action "restart docker.service" action_restart_docker || true
            step_restart_docker_epoch="${now}"
        fi

        if [ "${oom_only_incident}" -eq 0 ] && [ "${elapsed_seconds}" -ge $((6 * 60)) ] && [ "${step_compose_up_epoch}" -eq 0 ]; then
            run_action "docker compose up -d (homelab)" action_compose_up || true
            step_compose_up_epoch="${now}"
        fi

        if [ "${oom_only_incident}" -eq 0 ] && [ "${elapsed_seconds}" -ge $((WATCHDOG_RECOVERY_WINDOW_MINUTES * 60)) ] && [ "${step_reboot_epoch}" -eq 0 ]; then
            if [ "${last_reboot_epoch}" -gt 0 ] && [ $((now - last_reboot_epoch)) -lt "${REBOOT_COOLDOWN_SECONDS}" ]; then
                log "Reboot suppressed by cooldown gate"
                send_discord "Watchdog reboot suppressed: cooldown window active"
                step_reboot_epoch="${now}"
            else
                step_reboot_epoch="${now}"
                if action_reboot_host; then
                    last_reboot_epoch="${now}"
                elif [ "$?" -ne 2 ]; then
                    log "Watchdog reboot action failed"
                fi
            fi
        fi

        if [ "${oom_only_incident}" -eq 1 ]; then
            log "OOM-only degradation detected; skipping docker/compose/reboot escalation this cycle"
        fi

        last_status="degraded"
        update_state_env_and_save
        exit 0
    fi

    if [ "${incident_active}" -eq 1 ]; then
        elapsed_seconds=$((now - incident_start_epoch))
        send_discord "Watchdog recovery complete after ${elapsed_seconds}s"
        log "Recovery complete after ${elapsed_seconds}s"
    fi

    incident_active=0
    incident_start_epoch=0
    step_restart_containers_epoch=0
    step_restart_docker_epoch=0
    step_compose_up_epoch=0
    step_reboot_epoch=0
    last_status="healthy"
    update_state_env_and_save

    log "Watchdog check completed: healthy"
}

main "$@"
