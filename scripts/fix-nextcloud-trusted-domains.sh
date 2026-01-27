#!/bin/bash
# Fix Nextcloud trusted domains for mobile app access

set -euo pipefail

TAILSCALE_IP=$(grep TAILSCALE_IP .env 2>/dev/null | cut -d'=' -f2 || echo "100.64.0.10")
DOMAIN=$(grep DOMAIN .env 2>/dev/null | cut -d'=' -f2 || echo "homelab.example.com")
NEXTCLOUD_DOMAIN="cloud.${DOMAIN}"

echo "🔧 Fixing Nextcloud Trusted Domains"
echo "===================================="
echo ""
echo "Adding trusted domains:"
echo "  1. ${NEXTCLOUD_DOMAIN}"
echo "  2. ${TAILSCALE_IP}"
echo ""

# Check if Nextcloud container is running
if ! docker ps --filter "name=nextcloud" --format "{{.Names}}" | grep -q nextcloud; then
    echo "❌ Error: Nextcloud container is not running"
    exit 1
fi

echo "Setting trusted domain 0: ${NEXTCLOUD_DOMAIN}"
docker exec nextcloud php /var/www/html/occ config:system:set trusted_domains 0 --value="${NEXTCLOUD_DOMAIN}" 2>&1 || echo "⚠️  Domain may already be set"

echo "Setting trusted domain 1: ${TAILSCALE_IP}"
docker exec nextcloud php /var/www/html/occ config:system:set trusted_domains 1 --value="${TAILSCALE_IP}" 2>&1 || echo "⚠️  IP may already be set"

echo ""
echo "Current trusted domains:"
docker exec nextcloud php /var/www/html/occ config:system:get trusted_domains 2>&1

echo ""
echo "✅ Trusted domains configured!"
echo ""
echo "You can now access Nextcloud using:"
echo "  - Domain: https://${NEXTCLOUD_DOMAIN}"
echo "  - Direct IP: https://${TAILSCALE_IP}:443"
echo ""
echo "Test the connection:"
echo "  curl -I -k https://${NEXTCLOUD_DOMAIN}/status.php"
echo "  curl -I -k https://${TAILSCALE_IP}:443/status.php"
