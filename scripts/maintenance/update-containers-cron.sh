#!/bin/bash
# Wrapper script for container updates via cron
# Ensures correct working directory and environment

set -euo pipefail

HOMELAB_DIR="/home/luk-server/homelab"
cd "$HOMELAB_DIR" || exit 1

# Load environment if .env exists
if [[ -f "$HOMELAB_DIR/.env" ]]; then
    set -a
    source "$HOMELAB_DIR/.env" 2>/dev/null || true
    set +a
fi

# Run the update script
exec "$HOMELAB_DIR/scripts/maintenance/update-containers.sh" "$@"
