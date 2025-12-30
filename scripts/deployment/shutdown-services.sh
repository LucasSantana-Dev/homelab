#!/bin/bash
# Gracefully shutdown all homelab services

set -e

echo "Shutting down homelab services gracefully..."

# Stop services in reverse order (dependencies first)
echo "Stopping lukbot.service..."
sudo systemctl stop lukbot.service || echo "  ⚠ lukbot.service not running or failed to stop"

echo "Stopping satisfactory-server.service..."
sudo systemctl stop satisfactory-server.service || echo "  ⚠ satisfactory-server.service not running or failed to stop"

echo "Stopping homelab-docker.service..."
sudo systemctl stop homelab-docker.service || echo "  ⚠ homelab-docker.service not running or failed to stop"

echo ""
echo "✓ All services stopped!"
echo ""
echo "Service status:"
systemctl status homelab-docker.service --no-pager -l | head -3 || echo "  homelab-docker.service: inactive"
systemctl status satisfactory-server.service --no-pager -l | head -3 || echo "  satisfactory-server.service: inactive"
systemctl status lukbot.service --no-pager -l | head -3 || echo "  lukbot.service: inactive"
