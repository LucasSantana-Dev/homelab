#!/bin/bash
# Comprehensive Stremio server diagnostic script

set -euo pipefail

echo "🔍 Stremio Server Diagnostic Tool"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check Stremio container status
echo "1️⃣  Checking Stremio container..."
if docker ps --filter "name=stremio-server" --format "{{.Status}}" | grep -q "Up"; then
    echo -e "${GREEN}✅ Stremio container is running${NC}"
    docker ps --filter "name=stremio-server" --format "  Status: {{.Status}}"
else
    echo -e "${RED}❌ Stremio container is not running${NC}"
    exit 1
fi
echo ""

# 2. Check Stremio service health
echo "2️⃣  Checking Stremio service health..."
if docker exec stremio-server curl -s http://localhost:11470/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Stremio service is responding internally${NC}"
else
    echo -e "${RED}❌ Stremio service is not responding${NC}"
fi
echo ""

# 3. Check port binding
echo "3️⃣  Checking port binding..."
PORT_BINDING=$(docker port stremio-server 2>&1 | grep 11470 || echo "Not found")
if [[ "$PORT_BINDING" != "Not found" ]]; then
    echo -e "${GREEN}✅ Port binding: $PORT_BINDING${NC}"
else
    echo -e "${RED}❌ Port 11470 is not bound${NC}"
fi
echo ""

# 4. Check Nginx proxy
echo "4️⃣  Checking Nginx proxy..."
if docker ps --filter "name=nginx-proxy" --format "{{.Status}}" | grep -q "Up"; then
    echo -e "${GREEN}✅ Nginx container is running${NC}"

    # Test DNS resolution
    STREMIO_IP=$(docker exec nginx-proxy getent hosts stremio 2>&1 | awk '{print $1}' || echo "Failed")
    if [[ "$STREMIO_IP" != "Failed" && "$STREMIO_IP" != "" ]]; then
        echo -e "${GREEN}✅ Nginx can resolve stremio service: $STREMIO_IP${NC}"
    else
        echo -e "${RED}❌ Nginx cannot resolve stremio service${NC}"
    fi
else
    echo -e "${RED}❌ Nginx container is not running${NC}"
fi
echo ""

# 5. Test HTTPS access
echo "5️⃣  Testing HTTPS access..."
HTTPS_RESPONSE=$(curl -sI http://stremio.home 2>&1 | head -1)
if echo "$HTTPS_RESPONSE" | grep -q "HTTP"; then
    echo -e "${GREEN}✅ HTTPS endpoint is accessible${NC}"
    echo "  Response: $HTTPS_RESPONSE"
else
    echo -e "${RED}❌ HTTPS endpoint is not accessible${NC}"
    echo "  Error: $HTTPS_RESPONSE"
fi
echo ""

# 6. Test direct Tailscale IP access
echo "6️⃣  Testing direct Tailscale IP access..."
TAILSCALE_IP=$(grep TAILSCALE_IP .env 2>/dev/null | cut -d'=' -f2 || echo "")
if [[ -n "$TAILSCALE_IP" ]]; then
    DIRECT_RESPONSE=$(curl -sI "http://${TAILSCALE_IP}:11470" 2>&1 | head -1)
    if echo "$DIRECT_RESPONSE" | grep -q "HTTP"; then
        echo -e "${GREEN}✅ Direct Tailscale IP access works${NC}"
        echo "  Response: $DIRECT_RESPONSE"
    else
        echo -e "${YELLOW}⚠️  Direct Tailscale IP access issue${NC}"
        echo "  Response: $DIRECT_RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠️  Could not find TAILSCALE_IP in .env${NC}"
fi
echo ""

# 7. Check Tailscale status
echo "7️⃣  Checking Tailscale status..."
if command -v tailscale > /dev/null 2>&1; then
    TAILSCALE_ONLINE=$(tailscale status --json 2>&1 | jq -r '.Self.Online // false')
    TAILSCALE_ROUTES=$(tailscale status --json 2>&1 | jq -r '.Self.PrimaryRoutes[]? // empty' | tr '\n' ',' | sed 's/,$//')

    if [[ "$TAILSCALE_ONLINE" == "true" ]]; then
        echo -e "${GREEN}✅ Tailscale is online${NC}"
    else
        echo -e "${RED}❌ Tailscale is offline${NC}"
    fi

    if [[ -n "$TAILSCALE_ROUTES" ]]; then
        echo -e "${GREEN}✅ Tailscale routes active: $TAILSCALE_ROUTES${NC}"
    else
        echo -e "${YELLOW}⚠️  No Tailscale routes active${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Tailscale command not found${NC}"
fi
echo ""

# 8. Check recent errors
echo "8️⃣  Checking for recent errors..."
echo "Stremio logs (last 10 lines with errors):"
docker logs stremio-server --tail 100 2>&1 | grep -i "error\|fail" | tail -5 || echo "  No recent errors found"
echo ""

echo "Nginx logs (last 10 lines with stremio errors):"
docker logs nginx-proxy --tail 100 2>&1 | grep -i "stremio.*error\|error.*stremio" | tail -5 || echo "  No recent errors found"
echo ""

# 9. Configuration summary
STREMIO_PUBLIC_URL=$(grep '^STREMIO_PUBLIC_URL=' .env 2>/dev/null | cut -d'=' -f2 || echo "https://server-do-luk.tailab88e9.ts.net")
echo "9️⃣  Configuration Summary:"
echo "  LAN URL (Stremio Desktop):  http://stremio.home"
echo "  Tailscale IP:               http://${TAILSCALE_IP}:11470"
echo "  Public HTTPS (Stremio Web): ${STREMIO_PUBLIC_URL}"
echo "  Container Port:             11470"
echo ""

# 10. Recommendations
echo "🔟 Recommendations:"
echo ""
echo "Stremio Web (web.stremio.com / app.strem.io):"
echo "  → Use the public HTTPS URL (browser blocks HTTP mixed content):"
echo "    ${STREMIO_PUBLIC_URL}"
echo ""
echo "Stremio Desktop / mobile app on LAN:"
echo "  → http://stremio.home  (or http://${TAILSCALE_IP}:11470 over Tailscale)"
echo ""
echo "For Tailscale error:"
echo "  - Check admin console: https://login.tailscale.com/admin/machines"
echo "  - 'Active: false' is normal for server machines"
echo "  - Important status is 'Online: true'"
echo ""
