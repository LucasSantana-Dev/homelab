#!/usr/bin/env bash
# Convert Ubuntu Desktop host to Server-mode in place (no reinstall).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
PRECHECK_ROOT="${PROJECT_ROOT}/backups/host-stabilization/server-mode-preflight"

APPLY=false

SERVICES_TO_DISABLE=(
  gdm.service
  gdm3.service
  lightdm.service
  display-manager.service
  xrdp.service
  xrdp-sesman.service
  gnome-remote-desktop.service
  cups.service
  cups-browsed.service
  bluetooth.service
  ModemManager.service
  avahi-daemon.service
)

PACKAGE_REGEXES=(
  '^ubuntu-desktop$'
  '^ubuntu-desktop-minimal$'
  '^gdm3$'
  '^gnome-shell$'
  '^xorg$'
  '^xrdp$'
  '^gnome-remote-desktop$'
  '^cups$'
  '^cups-browsed$'
  '^bluez$'
  '^modemmanager$'
  '^avahi-daemon$'
  '^lightdm($|-)'
  '^xserver-xorg($|-)'
  '^x11-'
  '^xorgxrdp$'
  '^xorg-docs-core$'
  '^gnome-'
)

usage() {
  cat <<'EOF'
Usage: convert-to-server-mode.sh [--apply]

Default mode is a preview (no changes). Use --apply to execute package and systemd changes.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=true
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

run_sudo() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

create_preflight_snapshot() {
  local timestamp run_dir
  timestamp="$(date +%Y%m%d_%H%M%S)"
  run_dir="${PRECHECK_ROOT}/${timestamp}"
  mkdir -p "${run_dir}"

  dpkg -l >"${run_dir}/dpkg-l.txt" 2>&1 || true
  systemctl list-unit-files --no-pager >"${run_dir}/systemd-unit-files.txt" 2>&1 || true
  apt-mark showmanual | sort >"${run_dir}/apt-mark-manual.txt" 2>&1 || true

  echo "Saved pre-flight package/service snapshot: ${run_dir}"
}

is_package_installed() {
  dpkg -s "$1" >/dev/null 2>&1
}

collect_installed_gui_packages() {
  local rg_args=()
  local expr
  for expr in "${PACKAGE_REGEXES[@]}"; do
    rg_args+=(-e "${expr}")
  done

  dpkg-query -W -f='${Package}\n' 2>/dev/null \
    | rg "${rg_args[@]}" \
    | sort -u
}

mapfile -t installed_packages < <(collect_installed_gui_packages || true)
create_preflight_snapshot

echo "Server-mode conversion plan"
echo "==========================="
echo "Will install: ubuntu-server-minimal"
echo "Will set default target: multi-user.target"
echo "Will disable services:"
printf '  - %s\n' "${SERVICES_TO_DISABLE[@]}"
echo "Detected installed packages to purge:"
if [[ ${#installed_packages[@]} -eq 0 ]]; then
  echo "  (none)"
else
  printf '  - %s\n' "${installed_packages[@]}"
fi

if [[ ${#installed_packages[@]} -gt 0 ]]; then
  echo
  echo "Dry-run purge preview (apt-get -s purge):"
  apt-get -s purge -y "${installed_packages[@]}" | sed -n '1,120p'
fi

if [[ "${APPLY}" != "true" ]]; then
  echo
  echo "Preview only. Re-run with --apply to execute."
  exit 0
fi

echo
echo "Applying server-mode conversion..."
run_sudo apt-get update
run_sudo apt-get install -y ubuntu-server-minimal
run_sudo systemctl set-default multi-user.target

for unit in "${SERVICES_TO_DISABLE[@]}"; do
  run_sudo systemctl disable --now "${unit}" >/dev/null 2>&1 || true
done

if [[ ${#installed_packages[@]} -gt 0 ]]; then
  echo "Running purge dry-run as root before apply..."
  run_sudo apt-get -s purge -y "${installed_packages[@]}" | sed -n '1,120p'
  run_sudo apt-get purge -y "${installed_packages[@]}"
fi
run_sudo apt-get autoremove --purge -y
run_sudo apt-get clean

echo
echo "Server-mode conversion completed."
echo "Reboot required to fully apply target/session changes."
