#!/bin/bash
set -euo pipefail
# Project Cleanup Script
# Removes temporary files, caches, and stale backups
#
# Usage: ./scripts/maintenance/cleanup-project.sh [--dry-run] [--all]
#
# Options:
#   --dry-run    Show what would be deleted without actually deleting
#   --all        Also clean backups older than 7 days

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Flags
DRY_RUN=false
CLEAN_ALL=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --all)
            CLEAN_ALL=true
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--all]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be deleted without actually deleting"
            echo "  --all        Also clean backups older than 7 days"
            exit 0
            ;;
    esac
done

cd "$PROJECT_ROOT"

echo -e "${BLUE}🧹 Homelab Project Cleanup${NC}"
echo "=========================="
echo ""

if $DRY_RUN; then
    echo -e "${YELLOW}DRY RUN MODE - No files will be deleted${NC}"
    echo ""
fi

# Function to delete with size tracking
cleanup_item() {
    local path="$1"
    local description="$2"

    if [[ -e "$path" ]]; then
        local size
        size=$(du -sh "$path" 2>/dev/null | cut -f1)

        if $DRY_RUN; then
            echo -e "${YELLOW}Would delete:${NC} $path ($size) - $description"
        else
            echo -e "${GREEN}Deleting:${NC} $path ($size) - $description"
            rm -rf "$path"
        fi
    fi
}

# Function to cleanup directory pattern (only in project dirs, not venv/appdata)
cleanup_pycache() {
    local description="$1"

    # Only clean __pycache__ in homelab_manager, tests, scripts directories
    local dirs_to_clean=("homelab_manager" "tests" "scripts")
    local total_count=0

    for dir in "${dirs_to_clean[@]}"; do
        if [[ -d "$dir" ]]; then
            local count
            count=$(find "$dir" -name "__pycache__" -type d 2>/dev/null | wc -l)
            total_count=$((total_count + count))

            if [[ $count -gt 0 ]]; then
                if $DRY_RUN; then
                    echo -e "${YELLOW}Would delete:${NC} $count __pycache__ dirs in $dir/"
                else
                    echo -e "${GREEN}Deleting:${NC} $count __pycache__ dirs in $dir/"
                    find "$dir" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
                fi
            fi
        fi
    done

    if [[ $total_count -eq 0 ]]; then
        echo "  No __pycache__ directories found"
    fi
}

echo "📦 Python Caches"
echo "----------------"
cleanup_pycache "Python bytecode cache"
cleanup_item ".mypy_cache" "MyPy type checking cache"
cleanup_item ".pytest_cache" "Pytest cache"

echo ""
echo "📊 Generated Reports"
echo "--------------------"
cleanup_item "htmlcov" "HTML coverage report (regenerate with: make coverage)"
cleanup_item "bandit-report.json" "Outdated Bandit security report"
cleanup_item ".coverage" "Coverage data file"

echo ""
echo "🗑️  Temporary Files"
echo "-------------------"
# Find and clean various temp files in project directories only
temp_found=false
for ext in "*.pyc" "*.pyo" "*~" "*.swp" "*.swo"; do
    count=$(find homelab_manager tests scripts -name "$ext" -type f 2>/dev/null | wc -l)
    if [[ $count -gt 0 ]]; then
        temp_found=true
        if $DRY_RUN; then
            echo -e "${YELLOW}Would delete:${NC} $count files matching $ext"
        else
            echo -e "${GREEN}Deleting:${NC} $count files matching $ext"
            find homelab_manager tests scripts -name "$ext" -type f -delete 2>/dev/null || true
        fi
    fi
done
if ! $temp_found; then
    echo "  No temporary files found"
fi

echo ""
echo "📁 Broken Scripts"
echo "-----------------"
# Check for the broken homelab-tools script
if [[ -f "scripts/homelab-tools" ]]; then
    if ! python3 -c "from homelab_manager.cli_tools import main" 2>/dev/null; then
        cleanup_item "scripts/homelab-tools" "References non-existent cli_tools module"
    else
        echo "  No broken scripts found"
    fi
else
    echo "  No broken scripts found"
fi

echo ""
echo "📦 Binary Files (should be downloaded, not stored)"
echo "--------------------------------------------------"
if [[ -f "cloudflared" ]]; then
    cleanup_item "cloudflared" "Cloudflared binary (download via install script instead)"
else
    echo "  No binary files to clean"
fi

echo ""
echo "📋 Log Rotation"
echo "---------------"
# Keep last 1000 lines of each log file
log_rotated=false
if [[ -d "logs" ]]; then
    for log in logs/*.log; do
        if [[ -f "$log" ]]; then
            lines=$(wc -l < "$log")
            if [[ $lines -gt 1000 ]]; then
                log_rotated=true
                if $DRY_RUN; then
                    echo -e "${YELLOW}Would truncate:${NC} $log ($lines lines -> 1000 lines)"
                else
                    echo -e "${GREEN}Truncating:${NC} $log ($lines lines -> 1000 lines)"
                    tail -1000 "$log" > "$log.tmp" && mv "$log.tmp" "$log"
                fi
            fi
        fi
    done
fi
if ! $log_rotated; then
    echo "  No logs need rotation (all under 1000 lines)"
fi

if $CLEAN_ALL; then
    echo ""
    echo "🗃️  Old Backups (>7 days)"
    echo "-------------------------"
    old_backups=false
    if [[ -d "backups" ]]; then
        while IFS= read -r backup; do
            if [[ -n "$backup" ]]; then
                old_backups=true
                cleanup_item "$backup" "Backup older than 7 days"
            fi
        done < <(find backups -type f -mtime +7 2>/dev/null)
    fi
    if ! $old_backups; then
        echo "  No old backups found"
    fi

    echo ""
    echo "📝 Old Security Reports (>30 days)"
    echo "-----------------------------------"
    old_reports=false
    if [[ -d "security-reports" ]]; then
        while IFS= read -r report; do
            if [[ -n "$report" ]]; then
                old_reports=true
                cleanup_item "$report" "Security report older than 30 days"
            fi
        done < <(find security-reports -type f -mtime +30 2>/dev/null)
    fi
    if ! $old_reports; then
        echo "  No old security reports found"
    fi
fi

echo ""
echo "=========================="
if $DRY_RUN; then
    echo -e "${YELLOW}DRY RUN COMPLETE${NC} - Run without --dry-run to actually delete files"
else
    echo -e "${GREEN}✅ Cleanup complete!${NC}"
fi

# Show current disk usage
echo ""
echo "📊 Current project size:"
du -sh "$PROJECT_ROOT" 2>/dev/null | awk '{print "   Total: " $1}'
du -sh "$PROJECT_ROOT"/{venv,.git,backups} 2>/dev/null | awk '{print "   " $2 ": " $1}' | sed "s|$PROJECT_ROOT/||"
