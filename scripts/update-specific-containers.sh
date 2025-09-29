#!/bin/bash
# Targeted Container Update Script
# Safely updates specific containers with available updates

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Function to show usage
show_usage() {
    echo "Usage: $0 [container_name]"
    echo ""
    echo "Available containers:"
    echo "  homeassistant  - Home Assistant automation platform"
    echo "  homepage       - Homepage dashboard"
    echo "  grafana        - Grafana monitoring dashboard"
    echo "  filebrowser    - File browser (if running)"
    echo ""
    echo "Examples:"
    echo "  $0 homeassistant    # Update only Home Assistant"
    echo "  $0 all             # Update all containers"
    echo "  $0 status          # Show current container status"
}

# Function to check container status
check_status() {
    log "Current container status:"
    echo ""
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | grep -E "(homeassistant|homepage|grafana|filebrowser)" || echo "No target containers found"
    echo ""
    
    log "Available updates (from What's Up Docker):"
    echo "  - Homeassistant: sha256:3476d747"
    echo "  - Homepage: feature-deps-180425 (red - urgent)"
    echo "  - Filebrowser: sha256:0d9e79b1"
    echo "  - Grafana: sha256:60794dc1"
}

# Function to backup container data
backup_container() {
    local container_name=$1
    local backup_dir="./backups/$(date +%Y%m%d_%H%M%S)_${container_name}"
    
    log "Creating backup for $container_name in $backup_dir"
    mkdir -p "$backup_dir"
    
    case $container_name in
        "homeassistant")
            if [[ -d "./appdata/homeassistant" ]]; then
                cp -r ./appdata/homeassistant "$backup_dir/"
                success "Backed up Home Assistant config"
            fi
            ;;
        "homepage")
            if [[ -d "./appdata/homepage" ]]; then
                cp -r ./appdata/homepage "$backup_dir/"
                success "Backed up Homepage config"
            fi
            ;;
        "grafana")
            if [[ -d "./appdata/grafana" ]]; then
                cp -r ./appdata/grafana "$backup_dir/"
                success "Backed up Grafana config"
            fi
            ;;
    esac
}

# Function to update a single container
update_single_container() {
    local container_name=$1
    
    case $container_name in
        "homeassistant")
            log "Updating Home Assistant..."
            backup_container "homeassistant"
            docker-compose pull homeassistant
            docker-compose up -d homeassistant
            ;;
        "homepage")
            log "Updating Homepage..."
            backup_container "homepage"
            docker-compose pull homepage
            docker-compose up -d homepage
            ;;
        "grafana")
            log "Updating Grafana..."
            backup_container "grafana"
            docker-compose pull grafana
            docker-compose up -d grafana
            ;;
        "filebrowser")
            warning "Filebrowser is not in docker-compose.yml"
            log "Checking if filebrowser is running independently..."
            if docker ps --filter "name=filebrowser" --format "{{.Names}}" | grep -q "filebrowser"; then
                log "Found filebrowser running. Manual update required:"
                echo "  docker stop filebrowser"
                echo "  docker rm filebrowser"
                echo "  docker pull filebrowser/filebrowser:latest"
                echo "  # Then restart with your original command"
            else
                log "Filebrowser not found in running containers"
            fi
            ;;
        *)
            error "Unknown container: $container_name"
            return 1
            ;;
    esac
}

# Function to wait for container to be healthy
wait_for_container() {
    local container_name=$1
    local max_attempts=30
    local attempt=1
    
    log "Waiting for $container_name to be ready..."
    
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

# Main function
main() {
    local target=${1:-""}
    
    # Load environment
    if [[ -f .env ]]; then
        export $(grep -v '^#' .env | xargs)
    else
        error ".env file not found"
        exit 1
    fi
    
    case $target in
        "status")
            check_status
            ;;
        "all")
            log "Updating all containers..."
            update_single_container "homeassistant"
            wait_for_container "homeassistant"
            
            update_single_container "homepage"
            wait_for_container "homepage"
            
            update_single_container "grafana"
            wait_for_container "grafana"
            
            update_single_container "filebrowser"
            
            success "All containers updated!"
            ;;
        "homeassistant"|"homepage"|"grafana"|"filebrowser")
            log "Updating $target..."
            update_single_container "$target"
            if [[ "$target" != "filebrowser" ]]; then
                wait_for_container "$target"
            fi
            success "$target updated successfully!"
            ;;
        "")
            show_usage
            ;;
        *)
            error "Unknown option: $target"
            show_usage
            exit 1
            ;;
    esac
    
    # Show final status
    log "Final container status:"
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -E "(homeassistant|homepage|grafana|filebrowser)" || echo "No target containers running"
}

# Run main function
main "$@"
