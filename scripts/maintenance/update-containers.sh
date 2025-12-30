#!/bin/bash
# Safe Container Update Script for Homelab
# Performs rolling updates with health checks between container restarts
# Designed to run via systemd timer every 5 days

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$HOMELAB_DIR/logs/update.log"
BACKUP_DIR="$HOMELAB_DIR/backups"
LOCK_FILE="/tmp/homelab-update.lock"

# Load environment variables (handle special characters)
if [[ -f "$HOMELAB_DIR/.env" ]]; then
    # Only load specific variables we need, avoiding syntax issues with special chars
    DISCORD_WEBHOOK_URL=$(grep -E "^WUD_DISCORD_WEBHOOK_URL=" "$HOMELAB_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '\r' || echo "")
    TAILSCALE_IP=$(grep -E "^TAILSCALE_IP=" "$HOMELAB_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '\r' || echo "")
fi

# Discord webhook URL (loaded from .env above)
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Container groups for safe rolling updates (order matters)
declare -a GROUP_DATABASES=("nextcloud-db" "authentik-db" "paperless-db" "nextcloud-redis" "authentik-redis" "paperless-redis")
declare -a GROUP_CORE=("nginx-proxy" "homepage" "homeassistant" "vaultwarden")
declare -a GROUP_APPS=("jellyfin" "stremio-server" "n8n" "nextcloud" "paperless-ngx" "filebrowser")
declare -a GROUP_MONITORING=("prometheus" "grafana" "loki" "promtail" "alertmanager" "netdata" "blackbox-exporter" "node-exporter" "cadvisor")
declare -a GROUP_UTILITIES=("portainer" "uptime-kuma" "whats-up-docker" "pihole")

# Health check wait times per group (seconds)
declare -A GROUP_WAIT_TIMES=(
    ["databases"]=30
    ["core"]=20
    ["apps"]=20
    ["monitoring"]=15
    ["utilities"]=10
)

# Update statistics
UPDATED_CONTAINERS=0
FAILED_CONTAINERS=0
SKIPPED_CONTAINERS=0
declare -a UPDATED_LIST=()
declare -a FAILED_LIST=()

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$BACKUP_DIR"

# Logging functions
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "${BLUE}${message}${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $1"
    echo -e "${GREEN}${message}${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1"
    echo -e "${YELLOW}${message}${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1"
    echo -e "${RED}${message}${NC}" | tee -a "$LOG_FILE"
}

log_info() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] ℹ️  $1"
    echo -e "${CYAN}${message}${NC}" | tee -a "$LOG_FILE"
}

# Send Discord notification
send_discord_notification() {
    local title="$1"
    local description="$2"
    local color="$3"  # Decimal color: green=3066993, red=15158332, yellow=16776960
    local fields="$4"

    if [[ -z "$DISCORD_WEBHOOK_URL" ]]; then
        log_warning "Discord webhook URL not configured, skipping notification"
        return 0
    fi

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    local payload
    payload=$(cat <<EOF
{
    "embeds": [{
        "title": "$title",
        "description": "$description",
        "color": $color,
        "timestamp": "$timestamp",
        "footer": {
            "text": "Homelab Update System"
        },
        "fields": $fields
    }]
}
EOF
)

    if curl -s -H "Content-Type: application/json" -d "$payload" "$DISCORD_WEBHOOK_URL" > /dev/null 2>&1; then
        log "Discord notification sent"
    else
        log_warning "Failed to send Discord notification"
    fi
}

# Check if container exists
container_exists() {
    local container_name="$1"
    docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"
}

# Check container health
check_container_health() {
    local container_name="$1"
    local timeout="${2:-30}"

    if ! container_exists "$container_name"; then
        return 1
    fi

    local status
    status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "not_found")

    if [[ "$status" != "running" ]]; then
        return 1
    fi

    # Check if container has health check defined
    local health_status
    health_status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_name" 2>/dev/null || echo "none")

    if [[ "$health_status" == "none" ]]; then
        # No health check defined, container is running so consider healthy
        return 0
    elif [[ "$health_status" == "healthy" ]]; then
        return 0
    else
        # Wait for health check with timeout
        local elapsed=0
        while [[ $elapsed -lt $timeout ]]; do
            sleep 5
            elapsed=$((elapsed + 5))
            health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "unhealthy")
            if [[ "$health_status" == "healthy" ]]; then
                return 0
            fi
        done
        return 1
    fi
}

# Get current image digest for a container
get_image_digest() {
    local container_name="$1"
    docker inspect --format='{{.Image}}' "$container_name" 2>/dev/null || echo ""
}

# Update a single container
update_container() {
    local container_name="$1"
    local service_name="$2"

    if ! container_exists "$container_name"; then
        log_warning "Container $container_name does not exist, skipping"
        ((SKIPPED_CONTAINERS++))
        return 0
    fi

    local old_digest
    old_digest=$(get_image_digest "$container_name")

    log "Updating $container_name..."

    # Pull new image
    if ! docker compose -f "$HOMELAB_DIR/docker-compose.yml" pull "$service_name" 2>&1 | tee -a "$LOG_FILE"; then
        log_error "Failed to pull image for $container_name"
        FAILED_LIST+=("$container_name")
        ((FAILED_CONTAINERS++))
        return 1
    fi

    # Restart container with new image
    if ! docker compose -f "$HOMELAB_DIR/docker-compose.yml" up -d --no-deps "$service_name" 2>&1 | tee -a "$LOG_FILE"; then
        log_error "Failed to restart $container_name"
        FAILED_LIST+=("$container_name")
        ((FAILED_CONTAINERS++))
        return 1
    fi

    local new_digest
    new_digest=$(get_image_digest "$container_name")

    if [[ "$old_digest" != "$new_digest" ]]; then
        log_success "$container_name updated to new image"
        UPDATED_LIST+=("$container_name")
        ((UPDATED_CONTAINERS++))
    else
        log_info "$container_name already up to date"
    fi

    return 0
}

# Update a group of containers
update_group() {
    local group_name="$1"
    local wait_time="$2"
    shift 2
    local containers=("$@")

    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Updating group: $group_name"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for container in "${containers[@]}"; do
        # Derive service name from container name (remove suffixes like -server, -proxy)
        local service_name="${container%-server}"
        service_name="${service_name%-proxy}"

        # Handle special cases where container name differs from service name
        case "$container" in
            "nginx-proxy") service_name="nginx" ;;
            "stremio-server") service_name="stremio" ;;
            *) ;;
        esac

        update_container "$container" "$service_name"

        # Wait and check health
        log "Waiting ${wait_time}s for $container health check..."
        sleep "$wait_time"

        if ! check_container_health "$container" "$wait_time"; then
            log_warning "$container may not be fully healthy yet"
        else
            log_success "$container is healthy"
        fi
    done

    log "Group $group_name update complete"
    echo "" | tee -a "$LOG_FILE"
}

# Pre-flight checks
preflight_checks() {
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Running pre-flight checks..."
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running or not accessible"
        return 1
    fi
    log_success "Docker is running"

    # Check if docker-compose.yml exists
    if [[ ! -f "$HOMELAB_DIR/docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found at $HOMELAB_DIR"
        return 1
    fi
    log_success "docker-compose.yml found"

    # Check disk space (require at least 5GB free)
    local free_space
    free_space=$(df -BG "$HOMELAB_DIR" | awk 'NR==2 {print $4}' | tr -d 'G')
    if [[ "$free_space" -lt 5 ]]; then
        log_error "Insufficient disk space: ${free_space}GB free (need 5GB minimum)"
        return 1
    fi
    log_success "Disk space OK: ${free_space}GB free"

    # Check running containers count
    local running_count
    running_count=$(docker ps -q | wc -l)
    log_info "Currently running containers: $running_count"

    echo "" | tee -a "$LOG_FILE"
    return 0
}

# Create pre-update backup
create_backup() {
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Creating pre-update backup..."
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local timestamp
    timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_name="pre_update_${timestamp}.tar.gz"
    local backup_path="$BACKUP_DIR/$backup_name"

    # Backup critical configs only (not full appdata for speed)
    if tar -czf "$backup_path" \
        -C "$HOMELAB_DIR" \
        --exclude="*.log" \
        --exclude="*.tmp" \
        --exclude="cache" \
        --exclude="logs" \
        docker-compose.yml .env config 2>&1 | tee -a "$LOG_FILE"; then

        local backup_size
        backup_size=$(du -h "$backup_path" | cut -f1)
        log_success "Pre-update backup created: $backup_name ($backup_size)"
    else
        log_warning "Failed to create backup, continuing anyway"
    fi

    echo "" | tee -a "$LOG_FILE"
}

# Pull all images first
pull_all_images() {
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Pulling all container images..."
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cd "$HOMELAB_DIR"

    if docker compose pull 2>&1 | tee -a "$LOG_FILE"; then
        log_success "All images pulled successfully"
    else
        log_warning "Some images may have failed to pull"
    fi

    echo "" | tee -a "$LOG_FILE"
}

# Cleanup old images
cleanup_old_images() {
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Cleaning up old images..."
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local before_size
    before_size=$(docker system df --format '{{.Size}}' | head -1)

    # Remove dangling images
    docker image prune -f 2>&1 | tee -a "$LOG_FILE"

    local after_size
    after_size=$(docker system df --format '{{.Size}}' | head -1)

    log_success "Cleanup complete (Before: $before_size, After: $after_size)"
    echo "" | tee -a "$LOG_FILE"
}

# Generate update summary
generate_summary() {
    local duration="$1"

    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Update Summary"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Duration: ${duration}s"
    log "Updated containers: $UPDATED_CONTAINERS"
    log "Failed containers: $FAILED_CONTAINERS"
    log "Skipped containers: $SKIPPED_CONTAINERS"

    if [[ ${#UPDATED_LIST[@]} -gt 0 ]]; then
        log "Updated: ${UPDATED_LIST[*]}"
    fi

    if [[ ${#FAILED_LIST[@]} -gt 0 ]]; then
        log_error "Failed: ${FAILED_LIST[*]}"
    fi

    echo "" | tee -a "$LOG_FILE"
}

# Send final notification
send_final_notification() {
    local duration="$1"
    local status="success"
    local color=3066993  # Green

    if [[ $FAILED_CONTAINERS -gt 0 ]]; then
        status="partial"
        color=16776960  # Yellow
    fi

    if [[ $UPDATED_CONTAINERS -eq 0 && $FAILED_CONTAINERS -gt 0 ]]; then
        status="failed"
        color=15158332  # Red
    fi

    local updated_text="None"
    if [[ ${#UPDATED_LIST[@]} -gt 0 ]]; then
        updated_text="${UPDATED_LIST[*]}"
    fi

    local failed_text="None"
    if [[ ${#FAILED_LIST[@]} -gt 0 ]]; then
        failed_text="${FAILED_LIST[*]}"
    fi

    local fields
    fields=$(cat <<EOF
[
    {"name": "Status", "value": "$status", "inline": true},
    {"name": "Duration", "value": "${duration}s", "inline": true},
    {"name": "Updated", "value": "$UPDATED_CONTAINERS containers", "inline": true},
    {"name": "Failed", "value": "$FAILED_CONTAINERS containers", "inline": true},
    {"name": "Updated Containers", "value": "$updated_text", "inline": false},
    {"name": "Failed Containers", "value": "$failed_text", "inline": false}
]
EOF
)

    send_discord_notification "🔄 Homelab Container Update Complete" "Scheduled update finished on $(hostname)" "$color" "$fields"
}

# Acquire lock
acquire_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local lock_pid
        lock_pid=$(cat "$LOCK_FILE")
        if kill -0 "$lock_pid" 2>/dev/null; then
            log_error "Another update is already running (PID: $lock_pid)"
            exit 1
        else
            log_warning "Removing stale lock file"
            rm -f "$LOCK_FILE"
        fi
    fi
    echo $$ > "$LOCK_FILE"
}

# Release lock
release_lock() {
    rm -f "$LOCK_FILE"
}

# Cleanup on exit
cleanup() {
    release_lock
}

trap cleanup EXIT

# Main execution
main() {
    local start_time
    start_time=$(date +%s)

    log "╔════════════════════════════════════════════════════════════╗"
    log "║        HOMELAB CONTAINER UPDATE - SAFE MODE                ║"
    log "╚════════════════════════════════════════════════════════════╝"
    log "Started at: $(date)"
    log "Host: $(hostname)"
    echo "" | tee -a "$LOG_FILE"

    # Acquire lock to prevent concurrent runs
    acquire_lock

    # Send start notification
    send_discord_notification "🚀 Homelab Update Started" "Beginning scheduled container update on $(hostname)" 3447003 "[]"

    # Pre-flight checks
    if ! preflight_checks; then
        log_error "Pre-flight checks failed, aborting update"
        send_discord_notification "❌ Homelab Update Failed" "Pre-flight checks failed" 15158332 "[]"
        exit 1
    fi

    # Create backup
    create_backup

    # Pull all images first
    pull_all_images

    # Update groups in safe order
    update_group "databases" "${GROUP_WAIT_TIMES[databases]}" "${GROUP_DATABASES[@]}"
    update_group "core" "${GROUP_WAIT_TIMES[core]}" "${GROUP_CORE[@]}"
    update_group "apps" "${GROUP_WAIT_TIMES[apps]}" "${GROUP_APPS[@]}"
    update_group "monitoring" "${GROUP_WAIT_TIMES[monitoring]}" "${GROUP_MONITORING[@]}"
    update_group "utilities" "${GROUP_WAIT_TIMES[utilities]}" "${GROUP_UTILITIES[@]}"

    # Cleanup old images
    cleanup_old_images

    # Calculate duration
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Generate summary
    generate_summary "$duration"

    # Send final notification
    send_final_notification "$duration"

    log "╔════════════════════════════════════════════════════════════╗"
    log "║              UPDATE COMPLETE                                ║"
    log "╚════════════════════════════════════════════════════════════╝"
    log "Finished at: $(date)"

    # Exit with appropriate code
    if [[ $FAILED_CONTAINERS -gt 0 ]]; then
        exit 1
    fi
    exit 0
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Safe container update script for homelab services."
        echo "Updates containers in groups with health checks between restarts."
        echo ""
        echo "Options:"
        echo "  --help, -h      Show this help message"
        echo "  --dry-run       Show what would be updated without making changes"
        echo "  --force         Force update even if lock file exists"
        echo ""
        echo "Environment variables:"
        echo "  WUD_DISCORD_WEBHOOK_URL   Discord webhook for notifications"
        exit 0
        ;;
    --dry-run)
        log "DRY RUN MODE - No changes will be made"
        preflight_checks
        log "Would update the following groups:"
        log "  Databases: ${GROUP_DATABASES[*]}"
        log "  Core: ${GROUP_CORE[*]}"
        log "  Apps: ${GROUP_APPS[*]}"
        log "  Monitoring: ${GROUP_MONITORING[*]}"
        log "  Utilities: ${GROUP_UTILITIES[*]}"
        exit 0
        ;;
    --force)
        rm -f "$LOCK_FILE"
        main
        ;;
    "")
        main
        ;;
    *)
        log_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac
