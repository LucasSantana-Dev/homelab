#!/bin/bash
set -euo pipefail
# Start all homelab services manually

set -e

echo "Starting homelab services..."

# Check if services are enabled
if ! systemctl is-enabled --quiet homelab-docker.service 2>/dev/null; then
    echo "⚠ Warning: homelab-docker.service is not enabled"
    echo "  Run: sudo systemctl enable homelab-docker.service"
fi

if ! systemctl is-enabled --quiet lukbot.service 2>/dev/null; then
    echo "⚠ Warning: lukbot.service is not enabled"
    echo "  Run: sudo systemctl enable lukbot.service"
fi

# Start services
echo ""
echo "Starting homelab-docker.service..."
sudo systemctl start homelab-docker.service

echo "Starting lukbot.service..."
sudo systemctl start lukbot.service

echo ""
echo "✓ All services started!"
echo ""
echo "Service status:"
systemctl status homelab-docker.service --no-pager -l | head -5
systemctl status lukbot.service --no-pager -l | head -5
