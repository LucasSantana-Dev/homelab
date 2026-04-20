#!/usr/bin/env bash
# Validate host and homelab state after server-mode reboot.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"

FAILURES=0

ok() {
  printf '✅ %s\n' "$*"
}

fail() {
  printf '❌ %s\n' "$*"
  FAILURES=$((FAILURES + 1))
}

check_eq() {
  local label="$1"
  local actual="$2"
  local expected="$3"
  if [[ "${actual}" == "${expected}" ]]; then
    ok "${label}: ${actual}"
  else
    fail "${label}: expected '${expected}', got '${actual}'"
  fi
}

check_active() {
  local unit="$1"
  if systemctl is-active --quiet "${unit}"; then
    ok "${unit} is active"
  else
    fail "${unit} is not active"
  fi
}

check_inactive() {
  local unit="$1"
  if ! systemctl is-active --quiet "${unit}" 2>/dev/null; then
    ok "${unit} is inactive"
  else
    fail "${unit} should be inactive"
  fi
}

echo "Post-reboot validation"
echo "======================"

DEFAULT_TARGET="$(systemctl get-default)"
check_eq "Default target" "${DEFAULT_TARGET}" "multi-user.target"

check_inactive gdm.service
check_inactive gdm3.service
check_inactive lightdm.service
check_inactive display-manager.service
check_inactive xrdp.service
check_inactive xrdp-sesman.service
check_inactive gnome-remote-desktop.service

GUI_PACKAGE_REGEXES=(
  '^lightdm($|-)'
  '^xserver-xorg($|-)'
  '^x11-'
  '^xorgxrdp$'
  '^xorg-docs-core$'
  '^gnome-'
)

rg_args=()
for expr in "${GUI_PACKAGE_REGEXES[@]}"; do
  rg_args+=(-e "${expr}")
done

mapfile -t remaining_gui_packages < <(
  dpkg-query -W -f='${Package}\n' 2>/dev/null \
    | rg "${rg_args[@]}" \
    | sort -u
)

if [[ "${#remaining_gui_packages[@]}" -eq 0 ]]; then
  ok "GUI anchor packages are not installed"
else
  if [[ "${#remaining_gui_packages[@]}" -gt 12 ]]; then
    fail "GUI anchor packages still installed (${#remaining_gui_packages[@]}): ${remaining_gui_packages[*]:0:12} ..."
  else
    fail "GUI anchor packages still installed (${#remaining_gui_packages[@]}): ${remaining_gui_packages[*]}"
  fi
fi

check_active docker.service
check_active ssh.service
check_active tailscaled.service

if systemctl is-active --quiet homelab-update.timer; then
  ok "homelab-update.timer is active"
else
  fail "homelab-update.timer is not active"
fi

if systemctl is-active --quiet homelab-watchdog.timer; then
  ok "homelab-watchdog.timer is active"
else
  fail "homelab-watchdog.timer is not active"
fi

if "${PROJECT_ROOT}/scripts/homelab" health >/dev/null 2>&1; then
  ok "homelab health command succeeded"
else
  fail "homelab health command failed"
fi

echo
if [[ "${FAILURES}" -eq 0 ]]; then
  echo "All checks passed."
  exit 0
fi

echo "${FAILURES} check(s) failed."
exit 1
