#!/bin/bash
# Install systemd units for homelab services and timers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
UNITS_DIR="${PROJECT_ROOT}/scripts/systemd"
SYSTEMD_DIR="/etc/systemd/system"

echo "Installing systemd units from ${UNITS_DIR}..."

# Check if running as root or with sudo
if [ "${EUID}" -ne 0 ]; then
    echo "This script must be run with sudo"
    exit 1
fi

unit_files=(
    "homelab-docker.service"
    "satisfactory-server.service"
    "lukbot.service"
    "homelab-update.service"
    "homelab-update.timer"
    "homelab-watchdog.service"
    "homelab-watchdog.timer"
)
installed_units=()

# Install managed unit files
for unit_file in "${unit_files[@]}"; do
    src="${UNITS_DIR}/${unit_file}"
    dst="${SYSTEMD_DIR}/${unit_file}"

    if [ ! -f "${src}" ]; then
        echo "  ⚠ Skipping missing unit: ${unit_file}"
        continue
    fi

    echo "Installing ${unit_file}..."
    install -m 644 "${src}" "${dst}"
    installed_units+=("${unit_file}")
    echo "  ✓ Installed ${unit_file}"
done

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling managed services and timers..."
enable_units=(
    "homelab-docker.service"
    "satisfactory-server.service"
    "lukbot.service"
)

for timer_unit in homelab-update.timer homelab-watchdog.timer; do
    if [[ " ${installed_units[*]} " == *" ${timer_unit} "* ]]; then
        enable_units+=("${timer_unit}")
    fi
done

systemctl enable "${enable_units[@]}"

echo "Starting timers..."
for timer_unit in homelab-update.timer homelab-watchdog.timer; do
    if [[ " ${installed_units[*]} " == *" ${timer_unit} "* ]]; then
        systemctl start "${timer_unit}"
    fi
done

echo ""
echo "✓ Managed units installed and enabled"
echo ""
echo "Current enablement status:"
systemctl is-enabled homelab-docker.service || echo "  ⚠ homelab-docker.service not enabled"
systemctl is-enabled satisfactory-server.service || echo "  ⚠ satisfactory-server.service not enabled"
systemctl is-enabled lukbot.service || echo "  ⚠ lukbot.service not enabled"
systemctl is-enabled homelab-update.timer || echo "  ⚠ homelab-update.timer not enabled"
systemctl is-enabled homelab-watchdog.timer || echo "  ⚠ homelab-watchdog.timer not enabled"

echo ""
echo "To start services now, run:"
echo "  sudo systemctl start homelab-docker"
echo "  sudo systemctl start satisfactory-server"
echo "  sudo systemctl start lukbot"
