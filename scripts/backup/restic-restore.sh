#!/bin/bash
set -euo pipefail

# Restic restore script for homelab
# Usage: ./restic-restore.sh <snapshot-id> <restore-path>
#
# Lists available snapshots and restores to target path.
# Example: ./restic-restore.sh latest /tmp/homelab-restore

if [ $# -lt 2 ]; then
  echo "Usage: $0 <snapshot-id|latest> <restore-path>"
  echo ""
  echo "Available snapshots:"
  restic snapshots --compact
  exit 1
fi

SNAPSHOT_ID="$1"
RESTORE_PATH="$2"

if [ -z "${RESTIC_REPOSITORY:-}" ]; then
  echo "Error: RESTIC_REPOSITORY not set"
  exit 1
fi

export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

mkdir -p "$RESTORE_PATH"

echo "[$(date)] Restoring snapshot $SNAPSHOT_ID to $RESTORE_PATH..."
restic restore "$SNAPSHOT_ID" --target "$RESTORE_PATH"

echo "[$(date)] Restore completed to $RESTORE_PATH"
echo ""
echo "Contents:"
ls -lah "$RESTORE_PATH"
