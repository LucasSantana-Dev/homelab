#!/usr/bin/env bash
# Shared logging utilities for homelab scripts
# Source this after setting LOG_FILE and set -euo pipefail

# Colors for console output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
	local msg="$1"
	echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} [INFO] $msg" | tee -a "${LOG_FILE:-/dev/null}"
}

log_warn() {
	local msg="$1"
	echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} [WARN] $msg" | tee -a "${LOG_FILE:-/dev/null}" >&2
}

log_error() {
	local msg="$1"
	echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} [ERROR] $msg" | tee -a "${LOG_FILE:-/dev/null}" >&2
}

log_debug() {
	if [[ "${DEBUG:-0}" == "1" ]]; then
		echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} [DEBUG] $1" >&2
	fi
}

die() {
	local msg="$1"
	local code="${2:-1}"
	log_error "$msg"
	exit "$code"
}

export -f log_info log_warn log_error log_debug die
