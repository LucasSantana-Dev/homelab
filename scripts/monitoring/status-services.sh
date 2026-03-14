#!/bin/bash
# Check status of all auto-start services

echo "=== Homelab Auto-Start Services Status ==="
echo ""

# Check systemd services
echo "Systemd Services:"
echo "---------------"

services=(
    "homelab-docker"
    "satisfactory-server"
    "lukbot"
    "docker"
    "tailscaled"
)

for service in "${services[@]}"; do
    if systemctl is-enabled --quiet "${service}.service" 2>/dev/null; then
        enabled_status="✓ enabled"
    else
        enabled_status="✗ disabled"
    fi

    if systemctl is-active --quiet "${service}.service" 2>/dev/null; then
        active_status="✓ active"
    else
        active_status="✗ inactive"
    fi

    printf "  %-25s %-15s %s\n" "${service}.service" "$enabled_status" "$active_status"
done

echo ""
echo "Docker Containers:"
echo "-----------------"

# Check homelab containers
cd /home/luk-server/homelab 2>/dev/null || exit 1
if [ -f docker-compose.yml ]; then
    echo "  Homelab stack:"
    docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null | tail -n +2 | sed 's/^/    /' || echo "    ⚠ Unable to check containers"
fi

# Check satisfactory containers
cd /home/luk-server/satisfactory-server 2>/dev/null || exit 1
if [ -f docker-compose.yml ]; then
    echo "  Satisfactory stack:"
    docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null | tail -n +2 | sed 's/^/    /' || echo "    ⚠ Unable to check containers"
fi

# Check Lucky containers
cd /home/luk-server/Lucky 2>/dev/null || exit 1
if [ -f docker-compose.yml ]; then
    echo "  Lucky stack:"
    docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null | tail -n +2 | sed 's/^/    /' || echo "    ⚠ Unable to check containers"
fi

echo ""
echo "Network Services:"
echo "----------------"

# Check Tailscale
if command -v tailscale >/dev/null 2>&1; then
    tailscale_status=$(tailscale status 2>/dev/null | head -1 || echo "offline")
    echo "  Tailscale: $tailscale_status"
else
    echo "  Tailscale: ⚠ not installed"
fi

# Check Docker
if systemctl is-active --quiet docker.service 2>/dev/null; then
    docker_version=$(docker --version 2>/dev/null || echo "unknown")
    echo "  Docker: $docker_version"
else
    echo "  Docker: ⚠ not running"
fi

echo ""
echo "For detailed logs, run:"
echo "  sudo journalctl -u homelab-docker -n 50"
echo "  sudo journalctl -u satisfactory-server -n 50"
echo "  sudo journalctl -u lukbot -n 50"
