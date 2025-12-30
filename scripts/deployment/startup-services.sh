#!/bin/bash
# Start all homelab services manually

set -e

echo "Starting homelab services..."

# Check if services are enabled
if ! systemctl is-enabled --quiet homelab-docker.service 2>/dev/null; then
    echo "⚠ Warning: homelab-docker.service is not enabled"
    echo "  Run: sudo systemctl enable homelab-docker.service"
fi

if ! systemctl is-enabled --quiet satisfactory-server.service 2>/dev/null; then
    echo "⚠ Warning: satisfactory-server.service is not enabled"
    echo "  Run: sudo systemctl enable satisfactory-server.service"
fi

if ! systemctl is-enabled --quiet lukbot.service 2>/dev/null; then
    echo "⚠ Warning: lukbot.service is not enabled"
    echo "  Run: sudo systemctl enable lukbot.service"
fi

# Start services
echo ""
echo "Starting homelab-docker.service..."
sudo systemctl start homelab-docker.service

echo "Starting satisfactory-server.service..."
sudo systemctl start satisfactory-server.service

echo "Starting lukbot.service..."
sudo systemctl start lukbot.service

echo ""
echo "✓ All services started!"
echo ""
echo "Service status:"
systemctl status homelab-docker.service --no-pager -l | head -5
systemctl status satisfactory-server.service --no-pager -l | head -5
systemctl status lukbot.service --no-pager -l | head -5
