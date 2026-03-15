#!/bin/bash
# Burn-in health summary for homelab resilience rollout.

# This is a status-report command: prefer resilient output over fail-fast exits.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
ENV_FILE="${PROJECT_ROOT}/.env"

SINCE="24 hours ago"

usage() {
    cat <<'EOF'
Usage: burnin-status.sh [--since "<journalctl time expression>"]

Examples:
  ./scripts/maintenance/burnin-status.sh
  ./scripts/maintenance/burnin-status.sh --since "2026-03-10 12:00:00"
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --since)
            if [ $# -lt 2 ]; then
                echo "Missing value for --since" >&2
                exit 1
            fi
            SINCE="$2"
            shift 2
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

get_env_value() {
    local key="$1"
    if [ ! -f "${ENV_FILE}" ]; then
        return
    fi
    awk -F= -v wanted="${key}" '
        $0 ~ /^[[:space:]]*#/ { next }
        $1 == wanted { print substr($0, index($0, "=") + 1); exit }
    ' "${ENV_FILE}" | tr -d '\r'
}

status_line() {
    local label="$1"
    local value="$2"
    printf "%-36s %s\n" "${label}:" "${value}"
}

count_matches() {
    local text="$1"
    local pattern="$2"
    local count
    count="$(printf "%s\n" "${text}" | rg -c "${pattern}" || true)"
    echo "${count:-0}"
}

watchdog_reboot_enabled="$(get_env_value WATCHDOG_REBOOT_ENABLED)"
watchdog_recovery_window="$(get_env_value WATCHDOG_RECOVERY_WINDOW_MINUTES)"
alert_webhook="$(get_env_value ALERTMANAGER_DISCORD_WEBHOOK)"
watchdog_webhook="$(get_env_value WATCHDOG_DISCORD_WEBHOOK)"

timer_active="$(systemctl is-active homelab-watchdog.timer 2>/dev/null || true)"
timer_enabled="$(systemctl is-enabled homelab-watchdog.timer 2>/dev/null || true)"
service_result="$(systemctl show homelab-watchdog.service -p Result --value 2>/dev/null || true)"
service_exec_status="$(systemctl show homelab-watchdog.service -p ExecMainStatus --value 2>/dev/null || true)"
service_last_exit="$(systemctl show homelab-watchdog.service -p ExecMainExitTimestamp --value 2>/dev/null || true)"

watchdog_journal="$(journalctl -u homelab-watchdog.service --since "${SINCE}" --no-pager 2>/dev/null || true)"
watchdog_success_count="$(count_matches "${watchdog_journal}" 'Watchdog check completed: healthy')"
watchdog_action_count="$(count_matches "${watchdog_journal}" 'Running action:')"
watchdog_degraded_count="$(count_matches "${watchdog_journal}" 'Degraded state detected:')"
watchdog_discord_fail_count="$(count_matches "${watchdog_journal}" 'failed to send Discord notification')"
watchdog_failure_count="$(count_matches "${watchdog_journal}" 'status=1/FAILURE|Failed to start homelab-watchdog.service')"

alert_logs="$(docker logs --since "${SINCE}" alertmanager 2>&1 || true)"
alert_perm_denied_count="$(count_matches "${alert_logs}" 'permission denied')"
alert_notify_error_count="$(count_matches "${alert_logs}" 'Notify for alerts failed|Cannot send an empty message')"

discord_metrics="$(docker exec alertmanager wget -qO- http://localhost:9093/metrics 2>/dev/null || true)"
discord_total="$(printf "%s\n" "${discord_metrics}" | awk '/^alertmanager_notifications_total{integration="discord"}/ {print $2; exit}')"
discord_total="${discord_total:-0}"
discord_failed_total="$(printf "%s\n" "${discord_metrics}" | awk '/^alertmanager_notifications_failed_total{integration="discord"/ {sum += $2} END {print sum + 0}')"

kernel_logs="$(journalctl -k --since "${SINCE}" --no-pager 2>/dev/null || true)"
cadvisor_oom_count="$(count_matches "${kernel_logs}" 'Memory cgroup out of memory: Killed process .*cadvisor')"

overall="PASS"
if [ "${timer_active}" != "active" ] || [ "${timer_enabled}" != "enabled" ]; then
    overall="FAIL"
elif [ "${watchdog_failure_count}" -gt 0 ] || [ "${alert_perm_denied_count}" -gt 0 ] || [ "${alert_notify_error_count}" -gt 0 ]; then
    overall="FAIL"
elif [ "${watchdog_discord_fail_count}" -gt 0 ] || [ "${cadvisor_oom_count}" -gt 0 ]; then
    overall="WARN"
fi

echo "Homelab Burn-in Status (since: ${SINCE})"
echo "======================================="
status_line "Overall" "${overall}"
status_line "Watchdog timer active" "${timer_active}"
status_line "Watchdog timer enabled" "${timer_enabled}"
status_line "Watchdog last result" "${service_result:-n/a} (exit=${service_exec_status:-n/a})"
status_line "Watchdog last exit time" "${service_last_exit:-n/a}"
status_line "Watchdog healthy cycles" "${watchdog_success_count}"
status_line "Watchdog degraded detections" "${watchdog_degraded_count}"
status_line "Watchdog recovery actions" "${watchdog_action_count}"
status_line "Watchdog discord send failures" "${watchdog_discord_fail_count}"
status_line "Watchdog service failures" "${watchdog_failure_count}"
status_line "Alertmanager permission errors" "${alert_perm_denied_count}"
status_line "Alertmanager notify errors" "${alert_notify_error_count}"
status_line "Discord notifications attempted" "${discord_total}"
status_line "Discord notification failures" "${discord_failed_total}"
status_line "cAdvisor OOM events (kernel)" "${cadvisor_oom_count}"
status_line "WATCHDOG_REBOOT_ENABLED" "${watchdog_reboot_enabled:-unset}"
status_line "WATCHDOG_RECOVERY_WINDOW_MINUTES" "${watchdog_recovery_window:-unset}"
status_line "ALERTMANAGER webhook in .env" "$([ -n "${alert_webhook}" ] && echo configured || echo unset)"
status_line "WATCHDOG webhook override in .env" "$([ -n "${watchdog_webhook}" ] && echo configured || echo unset/fallback)"

exit 0
