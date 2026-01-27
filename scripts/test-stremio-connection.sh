#!/bin/bash
# Test Stremio server connection from different methods

set -euo pipefail

echo "🔍 Testing Stremio Server Connections"
echo "===================================="
echo ""

TAILSCALE_IP=$(grep TAILSCALE_IP .env 2>/dev/null | cut -d'=' -f2 || echo "100.64.0.10")

echo "1️⃣  Testing direct HTTP (bypassing Nginx):"
echo "   http://${TAILSCALE_IP}:11470"
curl -sI http://${TAILSCALE_IP}:11470/ 2>&1 | head -5
echo ""

echo "2️⃣  Testing HTTPS via domain:"
echo "   https://stremio.homelab.example.com"
curl -k -sI https://stremio.homelab.example.com/ 2>&1 | head -5
echo ""

echo "3️⃣  Testing direct container access:"
docker exec stremio-server curl -sI http://localhost:11470/ 2>&1 | head -5
echo ""

echo "4️⃣  Testing EngineFS endpoint:"
curl -k -s https://stremio.homelab.example.com/stremio/v1 2>&1 | head -10
echo ""

echo "5️⃣  Checking recent Stremio server logs:"
docker logs stremio-server --tail 20 2>&1 | grep -E "GET|POST|Error" | tail -5
echo ""

echo "💡 Connection URLs to try in Stremio app:"
echo "   - http://${TAILSCALE_IP}:11470"
echo "   - https://stremio.homelab.example.com"
echo "   - ${TAILSCALE_IP}:11470 (no protocol)"
echo ""
