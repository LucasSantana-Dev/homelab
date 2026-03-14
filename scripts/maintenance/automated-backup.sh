#!/bin/bash
# Automated Backup Script for Homelab
# Designed to be run via cron for automated backups

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_DIR="$HOMELAB_DIR/backups"
LOG_FILE="$HOMELAB_DIR/logs/backup.log"
VENV_DIR="$HOMELAB_DIR/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Create directories if they don't exist
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$BACKUP_DIR"

# Check if homelab manager is available
check_homelab_manager() {
    cd "$HOMELAB_DIR"

    if [ -f "$VENV_DIR/bin/activate" ]; then
        log "Using virtual environment for homelab manager"
        source "$VENV_DIR/bin/activate"
    elif command -v python3 &> /dev/null; then
        log "Using system Python for homelab manager"
    else
        error "Python3 not found. Cannot run homelab manager."
        exit 1
    fi

    # Check if homelab manager is installed
    if ! python3 -c "import homelab_manager" 2>/dev/null; then
        warning "Homelab manager not installed. Falling back to manual backup."
        return 1
    fi

    return 0
}

# Create backup using homelab manager
backup_with_manager() {
    log "Creating backup using homelab manager..."

    cd "$HOMELAB_DIR"

    if python3 -m homelab_manager backup; then
        success "Backup created successfully using homelab manager"
        return 0
    else
        error "Backup failed using homelab manager"
        return 1
    fi
}

# Create manual backup
manual_backup() {
    log "Creating manual backup..."

    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_name="homelab_backup_${timestamp}.tar.gz"
    local backup_path="$BACKUP_DIR/$backup_name"

    # Create backup of appdata and config directories
    if tar -czf "$backup_path" \
        -C "$HOMELAB_DIR" \
        --exclude="*.log" \
        --exclude="*.tmp" \
        --exclude="node_modules" \
        --exclude=".git" \
        appdata config docker-compose.yml .env; then

        success "Manual backup created: $backup_name"

        # Get backup size
        local backup_size=$(du -h "$backup_path" | cut -f1)
        log "Backup size: $backup_size"

        return 0
    else
        error "Manual backup failed"
        if [ -f "$backup_path" ]; then
            rm -f "$backup_path" || true
            warning "Removed incomplete backup artifact: $backup_name"
        fi
        return 1
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups..."

    # Keep backups from last 7 days, then keep weekly backups for 4 weeks
    local cleanup_count=0

    # Remove backups older than 7 days (except weekly ones)
    find "$BACKUP_DIR" -name "homelab_backup_*.tar.gz" -type f -mtime +7 \
        ! -name "homelab_backup_*_00_00_00.tar.gz" -delete && cleanup_count=$((cleanup_count + 1))

    # Remove weekly backups older than 28 days
    find "$BACKUP_DIR" -name "homelab_backup_*_00_00_00.tar.gz" -type f -mtime +28 -delete && cleanup_count=$((cleanup_count + 1))

    if [ $cleanup_count -gt 0 ]; then
        log "Cleaned up $cleanup_count old backup files"
    else
        log "No old backups to clean up"
    fi
}

# Verify backup integrity
verify_backup() {
    local backup_file="$1"

    log "Verifying backup integrity: $(basename "$backup_file")"

    if tar -tzf "$backup_file" >/dev/null 2>&1; then
        success "Backup integrity verified: $(basename "$backup_file")"
        return 0
    else
        error "Backup integrity check failed: $(basename "$backup_file")"
        return 1
    fi
}

# Send notification (if configured)
send_notification() {
    local status="$1"
    local message="$2"

    # Check if webhook URL is configured
    if [ -n "${BACKUP_WEBHOOK_URL:-}" ]; then
        local color="good"
        if [ "$status" = "error" ]; then
            color="danger"
        elif [ "$status" = "warning" ]; then
            color="warning"
        fi

        curl -X POST "$BACKUP_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{
                \"text\": \"Homelab Backup $status\",
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"fields\": [{
                        \"title\": \"Status\",
                        \"value\": \"$message\",
                        \"short\": false
                    }, {
                        \"title\": \"Server\",
                        \"value\": \"$(hostname)\",
                        \"short\": true
                    }, {
                        \"title\": \"Time\",
                        \"value\": \"$(date)\",
                        \"short\": true
                    }]
                }]
            }" 2>/dev/null || warning "Failed to send notification"
    fi
}

# Main execution
main() {
    log "Starting automated homelab backup..."

    local backup_status="success"
    local backup_message="Backup completed successfully"
    local latest_backup=""

    # Try to use homelab manager first
    if check_homelab_manager; then
        if backup_with_manager; then
            # Find the latest backup file
            latest_backup=$(find "$BACKUP_DIR" -name "homelab_backup_*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
        else
            warning "Backup with homelab manager failed. Falling back to manual backup."
            if manual_backup; then
                latest_backup=$(find "$BACKUP_DIR" -name "homelab_backup_*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
            else
                backup_status="error"
                backup_message="Backup failed using homelab manager and manual fallback"
            fi
        fi
    else
        # Fall back to manual backup
        if manual_backup; then
            # Find the latest backup file
            latest_backup=$(find "$BACKUP_DIR" -name "homelab_backup_*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
        else
            backup_status="error"
            backup_message="Manual backup failed"
        fi
    fi

    # Verify backup if one was created
    if [ -n "$latest_backup" ] && [ -f "$latest_backup" ]; then
        if ! verify_backup "$latest_backup"; then
            backup_status="error"
            backup_message="Backup created but integrity check failed"
        else
            local backup_size=$(du -h "$latest_backup" | cut -f1)
            backup_message="Backup completed successfully (Size: $backup_size)"
        fi
    fi

    # Cleanup old backups
    cleanup_old_backups

    # Send notification
    send_notification "$backup_status" "$backup_message"

    if [ "$backup_status" = "success" ]; then
        success "Automated backup completed successfully"
        exit 0
    else
        error "Automated backup failed: $backup_message"
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [--help|--verify <backup_file>]"
        echo ""
        echo "Options:"
        echo "  --help, -h          Show this help message"
        echo "  --verify <file>     Verify backup file integrity"
        echo ""
        echo "Environment variables:"
        echo "  BACKUP_WEBHOOK_URL  Webhook URL for notifications (optional)"
        exit 0
        ;;
    --verify)
        if [ -n "${2:-}" ] && [ -f "$2" ]; then
            verify_backup "$2"
            exit $?
        else
            error "Please provide a valid backup file path"
            exit 1
        fi
        ;;
    "")
        main
        ;;
    *)
        error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac
