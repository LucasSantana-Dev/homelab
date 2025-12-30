#!/bin/bash
# Homelab Security Scanner
# Comprehensive security scanning for Docker containers and configurations

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOMELAB_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$HOMELAB_DIR/logs/security-scan.log"
TRIVY_REPORT_DIR="$HOMELAB_DIR/security-reports"

# Create directories if they don't exist
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$TRIVY_REPORT_DIR"

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

# Check if Trivy is available
check_trivy() {
    if ! command -v trivy &> /dev/null; then
        log "Trivy not found. Installing via Docker..."
        # Use Docker to run Trivy if not installed locally
        TRIVY_CMD="docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasecurity/trivy"
    else
        TRIVY_CMD="trivy"
    fi
}

# Scan Docker Compose configuration
scan_docker_compose() {
    log "Scanning Docker Compose configuration..."

    if [ -f "$HOMELAB_DIR/docker-compose.yml" ]; then
        $TRIVY_CMD config --severity HIGH,CRITICAL "$HOMELAB_DIR/docker-compose.yml" \
            --format json --output "$TRIVY_REPORT_DIR/docker-compose-scan-$(date +%Y%m%d-%H%M%S).json" || {
            warning "Docker Compose configuration scan found issues"
            return 1
        }
        success "Docker Compose configuration scan completed"
    else
        error "docker-compose.yml not found"
        return 1
    fi
}

# Scan all container images
scan_container_images() {
    log "Scanning container images..."

    # Get list of images from docker-compose
    cd "$HOMELAB_DIR"
    images=$(docker compose config --images 2>/dev/null || docker-compose config --images 2>/dev/null)

    if [ -z "$images" ]; then
        error "Could not get container images from docker-compose"
        return 1
    fi

    local scan_failed=false

    while IFS= read -r image; do
        if [ -n "$image" ] && [ "$image" != "<none>" ]; then
            log "Scanning image: $image"

            # Create safe filename for report
            safe_name=$(echo "$image" | sed 's/[^a-zA-Z0-9._-]/_/g')
            report_file="$TRIVY_REPORT_DIR/image-scan-${safe_name}-$(date +%Y%m%d-%H%M%S).json"

            if ! $TRIVY_CMD image --severity HIGH,CRITICAL "$image" \
                --format json --output "$report_file"; then
                warning "High/Critical vulnerabilities found in $image"
                scan_failed=true
            else
                success "No high/critical vulnerabilities in $image"
            fi
        fi
    done <<< "$images"

    if [ "$scan_failed" = true ]; then
        warning "Some container images have high/critical vulnerabilities"
        return 1
    fi

    success "All container images scanned successfully"
}

# Scan running containers
scan_running_containers() {
    log "Scanning running containers..."

    local scan_failed=false

    # Get list of running containers
    containers=$(docker ps --format "{{.Names}}" | grep -E "(homeassistant|grafana|prometheus|nginx|portainer|pihole|uptime-kuma|stremio|filebrowser|whats-up-docker)")

    for container in $containers; do
        log "Scanning running container: $container"

        report_file="$TRIVY_REPORT_DIR/container-scan-${container}-$(date +%Y%m%d-%H%M%S).json"

        if ! $TRIVY_CMD container --severity HIGH,CRITICAL "$container" \
            --format json --output "$report_file"; then
            warning "High/Critical vulnerabilities found in container $container"
            scan_failed=true
        else
            success "No high/critical vulnerabilities in container $container"
        fi
    done

    if [ "$scan_failed" = true ]; then
        warning "Some running containers have high/critical vulnerabilities"
        return 1
    fi

    success "All running containers scanned successfully"
}

# Check for security best practices
check_security_practices() {
    log "Checking security best practices..."

    local issues=0

    # Check if containers are running as root
    log "Checking for containers running as root..."
    root_containers=$(docker ps --format "table {{.Names}}\t{{.Command}}" | grep -v "USER" | grep -v "user" | wc -l)
    if [ "$root_containers" -gt 0 ]; then
        warning "Some containers may be running as root"
        ((issues++))
    fi

    # Check for privileged containers
    log "Checking for privileged containers..."
    privileged_containers=$(docker ps --format "table {{.Names}}\t{{.Command}}" | grep "privileged" | wc -l)
    if [ "$privileged_containers" -gt 0 ]; then
        warning "Some containers are running in privileged mode"
        ((issues++))
    fi

    # Check for exposed ports
    log "Checking for exposed ports..."
    exposed_ports=$(docker ps --format "table {{.Names}}\t{{.Ports}}" | grep "0.0.0.0" | wc -l)
    if [ "$exposed_ports" -gt 0 ]; then
        warning "Some containers have ports exposed to all interfaces"
        ((issues++))
    fi

    if [ $issues -eq 0 ]; then
        success "Security best practices check passed"
    else
        warning "Found $issues security practice issues"
        return 1
    fi
}

# Generate security report
generate_report() {
    log "Generating security report..."

    local report_file="$TRIVY_REPORT_DIR/security-report-$(date +%Y%m%d-%H%M%S).txt"

    {
        echo "=== Homelab Security Scan Report ==="
        echo "Generated: $(date)"
        echo "Hostname: $(hostname)"
        echo ""
        echo "=== Docker Compose Configuration ==="
        echo "File: $HOMELAB_DIR/docker-compose.yml"
        echo ""
        echo "=== Container Images ==="
        cd "$HOMELAB_DIR"
        docker compose config --images 2>/dev/null || docker-compose config --images 2>/dev/null
        echo ""
        echo "=== Running Containers ==="
        docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        echo "=== Security Scan Results ==="
        echo "Check $TRIVY_REPORT_DIR/ for detailed JSON reports"
        echo ""
        echo "=== Recommendations ==="
        echo "1. Regularly update container images"
        echo "2. Run containers as non-root users when possible"
        echo "3. Avoid privileged containers unless necessary"
        echo "4. Limit exposed ports to necessary services only"
        echo "5. Monitor security advisories for used images"
    } > "$report_file"

    success "Security report generated: $report_file"
}

# Main execution
main() {
    log "Starting homelab security scan..."

    check_trivy

    local overall_status=0

    # Run all scans
    scan_docker_compose || overall_status=1
    scan_container_images || overall_status=1
    scan_running_containers || overall_status=1
    check_security_practices || overall_status=1

    generate_report

    if [ $overall_status -eq 0 ]; then
        success "Security scan completed successfully - no critical issues found"
    else
        warning "Security scan completed with issues - check reports for details"
    fi

    log "Security scan completed. Reports available in: $TRIVY_REPORT_DIR"
    exit $overall_status
}

# Run main function
main "$@"
