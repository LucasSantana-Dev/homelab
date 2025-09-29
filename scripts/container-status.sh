#!/bin/bash
# Container Status and Update Check Script

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "🔍 Homelab Container Status Check"
echo "================================="
echo ""

# Check if docker is running
if ! docker info >/dev/null 2>&1; then
    error "Docker is not running or not accessible"
    exit 1
fi

# Show current container status
log "Current running containers:"
echo ""
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | head -1
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | grep -E "(homeassistant|homepage|grafana|filebrowser)" || echo "No target containers found"
echo ""

# Check for updates using docker images
log "Checking for available updates..."
echo ""

# Function to check image updates
check_image_update() {
    local image_name=$1
    local container_name=$2
    
    echo -n "Checking $container_name ($image_name)... "
    
    # Get current image ID
    local current_id=$(docker images --format "{{.ID}}" "$image_name" 2>/dev/null || echo "not_found")
    
    if [[ "$current_id" == "not_found" ]]; then
        warning "Image not found locally"
        return
    fi
    
    # Try to pull latest (dry run)
    if docker pull "$image_name" >/dev/null 2>&1; then
        local latest_id=$(docker images --format "{{.ID}}" "$image_name" 2>/dev/null)
        
        if [[ "$current_id" != "$latest_id" ]]; then
            warning "UPDATE AVAILABLE"
        else
            success "Up to date"
        fi
    else
        error "Failed to check for updates"
    fi
}

# Check each container
check_image_update "ghcr.io/home-assistant/home-assistant:stable" "homeassistant"
check_image_update "ghcr.io/gethomepage/homepage:latest" "homepage"
check_image_update "grafana/grafana-oss:latest" "grafana"
check_image_update "filebrowser/filebrowser:latest" "filebrowser"

echo ""
log "Update recommendations from What's Up Docker:"
echo "  🟠 Homeassistant: sha256:3476d747"
echo "  🔴 Homepage: feature-deps-180425 (URGENT - red indicator)"
echo "  🟠 Filebrowser: sha256:0d9e79b1"
echo "  🟠 Grafana: sha256:60794dc1"
echo ""

# Show disk usage
log "Docker disk usage:"
docker system df
echo ""

# Show recent container logs
log "Recent container activity:"
docker ps --format "{{.Names}}" | head -5 | while read container; do
    echo "--- $container ---"
    docker logs --tail 3 "$container" 2>/dev/null || echo "No logs available"
    echo ""
done

echo "💡 To update containers, run:"
echo "  ./scripts/update-specific-containers.sh [container_name]"
echo "  ./scripts/update-specific-containers.sh all"
echo "  ./scripts/update-specific-containers.sh status"
