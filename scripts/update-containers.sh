#!/bin/bash
# Container Update Script for Homelab
# Updates containers with available updates while maintaining safety and monitoring

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root for security reasons"
   exit 1
fi

# Load environment variables
if [[ -f .env ]]; then
    log "Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
else
    error ".env file not found"
    exit 1
fi

# Validate required environment variables
required_vars=("PUID" "PGID" "TIMEZONE")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        error "Required environment variable $var is not set"
        exit 1
    fi
done

# Create backup directory
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

log "Starting container update process..."

# Function to backup container data
backup_container_data() {
    local container_name=$1
    log "Creating backup for $container_name..."
    
    # Create container-specific backup
    mkdir -p "$BACKUP_DIR/$container_name"
    
    # Backup volumes if they exist
    case $container_name in
        "homeassistant")
            if [[ -d "./appdata/homeassistant" ]]; then
                cp -r ./appdata/homeassistant "$BACKUP_DIR/$container_name/"
                success "Backed up Home Assistant configuration"
            fi
            ;;
        "homepage")
            if [[ -d "./appdata/homepage" ]]; then
                cp -r ./appdata/homepage "$BACKUP_DIR/$container_name/"
                success "Backed up Homepage configuration"
            fi
            ;;
        "grafana")
            if [[ -d "./appdata/grafana" ]]; then
                cp -r ./appdata/grafana "$BACKUP_DIR/$container_name/"
                success "Backed up Grafana configuration"
            fi
            ;;
        "filebrowser")
            # Filebrowser might be running outside compose, check for common paths
            if [[ -d "./appdata/filebrowser" ]]; then
                cp -r ./appdata/filebrowser "$BACKUP_DIR/$container_name/"
                success "Backed up Filebrowser configuration"
            fi
            ;;
    esac
}

# Function to check container health
check_container_health() {
    local container_name=$1
    local max_attempts=30
    local attempt=1
    
    log "Checking health of $container_name..."
    
    while [[ $attempt -le $max_attempts ]]; do
        if docker ps --filter "name=$container_name" --filter "status=running" --format "{{.Names}}" | grep -q "^${container_name}$"; then
            success "$container_name is running"
            return 0
        fi
        
        warning "Attempt $attempt/$max_attempts: $container_name not ready yet..."
        sleep 2
        ((attempt++))
    done
    
    error "$container_name failed to start properly"
    return 1
}

# Function to update a specific container
update_container() {
    local container_name=$1
    local image_name=$2
    
    log "Updating $container_name..."
    
    # Stop the container
    log "Stopping $container_name..."
    docker stop "$container_name" || warning "Container $container_name was not running"
    
    # Remove the old container
    log "Removing old $container_name container..."
    docker rm "$container_name" || warning "Container $container_name was not found"
    
    # Pull the latest image
    log "Pulling latest image for $image_name..."
    docker pull "$image_name"
    
    # Start the container using docker-compose
    log "Starting $container_name with updated image..."
    docker-compose up -d "$container_name"
    
    # Check if container started successfully
    if check_container_health "$container_name"; then
        success "$container_name updated successfully"
    else
        error "Failed to update $container_name"
        return 1
    fi
}

# Main update process
main() {
    log "🚀 Starting homelab container updates..."
    
    # Create backup before any updates
    log "Creating backups..."
    backup_container_data "homeassistant"
    backup_container_data "homepage"
    backup_container_data "grafana"
    backup_container_data "filebrowser"
    
    success "Backups created in $BACKUP_DIR"
    
    # Update containers in order of dependency
    log "Updating containers..."
    
    # 1. Update Home Assistant
    log "=== Updating Home Assistant ==="
    update_container "homeassistant" "ghcr.io/home-assistant/home-assistant:stable"
    
    # 2. Update Homepage
    log "=== Updating Homepage ==="
    update_container "homepage" "ghcr.io/gethomepage/homepage:latest"
    
    # 3. Update Grafana
    log "=== Updating Grafana ==="
    update_container "grafana" "grafana/grafana-oss:latest"
    
    # 4. Handle Filebrowser (might be running outside compose)
    log "=== Checking Filebrowser ==="
    if docker ps --filter "name=filebrowser" --format "{{.Names}}" | grep -q "filebrowser"; then
        log "Filebrowser found running outside docker-compose"
        warning "Filebrowser appears to be running independently. Manual update may be required."
        log "To update filebrowser manually:"
        log "  docker stop filebrowser"
        log "  docker rm filebrowser"
        log "  docker pull filebrowser/filebrowser:latest"
        log "  # Then restart with your original command"
    else
        log "Filebrowser not found in running containers"
    fi
    
    # Final health check
    log "=== Final Health Check ==="
    check_container_health "homeassistant"
    check_container_health "homepage"
    check_container_health "grafana"
    
    # Clean up old images
    log "Cleaning up old Docker images..."
    docker image prune -f
    
    success "🎉 All container updates completed successfully!"
    log "Backups are available in: $BACKUP_DIR"
    
    # Show running containers
    log "Current running containers:"
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
}

# Run main function
main "$@"
