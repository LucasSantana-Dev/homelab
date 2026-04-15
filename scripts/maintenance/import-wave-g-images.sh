#!/bin/bash
set -euo pipefail
# Import Wave G Docker images into k3s containerd
# Run as: bash scripts/maintenance/import-wave-g-images.sh
# Or: nohup bash scripts/maintenance/import-wave-g-images.sh > /tmp/import-wave-g.log 2>&1 &

set -e

LOG=/tmp/import-wave-g.log

echo "$(date): Starting Wave G image imports" | tee -a "$LOG"

echo "$(date): Importing nextcloud:latest..." | tee -a "$LOG"
docker save nextcloud:latest | sudo k3s ctr images import - 2>&1 | tee -a "$LOG"
echo "$(date): nextcloud done" | tee -a "$LOG"

echo "$(date): Importing ghcr.io/paperless-ngx/paperless-ngx:latest..." | tee -a "$LOG"
docker save ghcr.io/paperless-ngx/paperless-ngx:latest | sudo k3s ctr images import - 2>&1 | tee -a "$LOG"
echo "$(date): paperless done" | tee -a "$LOG"

echo "$(date): All Wave G images imported successfully" | tee -a "$LOG"
