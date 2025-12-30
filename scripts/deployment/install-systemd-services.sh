#!/bin/bash
# Install systemd services for auto-starting Docker Compose stacks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_DIR="${SCRIPT_DIR}/systemd-services"
SYSTEMD_DIR="/etc/systemd/system"

echo "Installing systemd services for auto-start..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run with sudo"
    exit 1
fi

# Install each service file
for service_file in "${SERVICES_DIR}"/*.service; do
    if [ -f "$service_file" ]; then
        service_name=$(basename "$service_file")
        echo "Installing $service_name..."
        cp "$service_file" "${SYSTEMD_DIR}/${service_name}"
        chmod 644 "${SYSTEMD_DIR}/${service_name}"
        echo "  ✓ Installed $service_name"
    fi
done

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo "Enabling services..."
systemctl enable homelab-docker.service
systemctl enable satisfactory-server.service
systemctl enable lukbot.service

echo ""
echo "✓ All services installed and enabled!"
echo ""
echo "Service status:"
systemctl is-enabled homelab-docker.service || echo "  ⚠ homelab-docker.service not enabled"
systemctl is-enabled satisfactory-server.service || echo "  ⚠ satisfactory-server.service not enabled"
systemctl is-enabled lukbot.service || echo "  ⚠ lukbot.service not enabled"
echo ""
echo "To start services now, run:"
echo "  sudo systemctl start homelab-docker"
echo "  sudo systemctl start satisfactory-server"
echo "  sudo systemctl start lukbot"
