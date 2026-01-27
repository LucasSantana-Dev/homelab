#!/bin/bash
# Diagnostic script for Nextcloud DNS resolution issues

set -euo pipefail

TAILSCALE_IP=$(grep TAILSCALE_IP .env 2>/dev/null | cut -d'=' -f2 || echo "100.64.0.10")
DOMAIN="cloud.homelab.example.com"

echo "🔍 Nextcloud DNS Diagnostic Tool"
echo "=================================="
echo ""
echo "Target: $DOMAIN"
echo "Expected IP: $TAILSCALE_IP"
echo ""

# Check if running on server or client
if docker ps --filter "name=nginx-proxy" --format "{{.Names}}" | grep -q nginx-proxy; then
    echo "✅ Running on server (containers detected)"
    SERVER_MODE=true
else
    echo "ℹ️  Running on client device"
    SERVER_MODE=false
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. DNS Resolution Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test DNS resolution
if command -v nslookup &> /dev/null; then
    echo "Testing with nslookup..."
    NSLOOKUP_RESULT=$(nslookup $DOMAIN 2>&1 || echo "FAILED")
    echo "$NSLOOKUP_RESULT"
    echo ""
fi

if command -v dig &> /dev/null; then
    echo "Testing with dig..."
    DIG_RESULT=$(dig +short $DOMAIN 2>&1 || echo "FAILED")
    echo "Result: $DIG_RESULT"
    echo ""
fi

# Test with getent
if command -v getent &> /dev/null; then
    echo "Testing with getent..."
    GETENT_RESULT=$(getent hosts $DOMAIN 2>&1 || echo "FAILED")
    echo "Result: $GETENT_RESULT"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Tailscale Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if command -v tailscale &> /dev/null; then
    echo "Tailscale status:"
    tailscale status 2>&1 | head -5 || echo "Tailscale not running or not installed"
    echo ""
    
    echo "Tailscale IP check:"
    TAILSCALE_CURRENT_IP=$(tailscale ip -4 2>/dev/null || echo "NOT_FOUND")
    echo "Current Tailscale IP: $TAILSCALE_CURRENT_IP"
    echo "Expected IP: $TAILSCALE_IP"
    
    if [ "$TAILSCALE_CURRENT_IP" = "$TAILSCALE_IP" ]; then
        echo "✅ Tailscale IP matches"
    else
        echo "⚠️  Tailscale IP mismatch - this might be the issue!"
    fi
    echo ""
else
    echo "⚠️  Tailscale command not found"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Direct IP Connection Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if command -v curl &> /dev/null; then
    echo "Testing direct IP connection (bypassing DNS)..."
    echo "Note: This will fail SSL validation but tests connectivity"
    
    # Test HTTP on port 8300 (Nextcloud direct port)
    HTTP_RESULT=$(curl -I -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://$TAILSCALE_IP:8300 2>&1 || echo "FAILED")
    echo "HTTP (port 8300): $HTTP_RESULT"
    
    # Test HTTPS on port 443 (via nginx)
    HTTPS_RESULT=$(curl -I -k -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://$TAILSCALE_IP:443 2>&1 || echo "FAILED")
    echo "HTTPS (port 443): $HTTPS_RESULT"
    echo ""
else
    echo "⚠️  curl not found - cannot test connectivity"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Server-Side Checks (if running on server)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$SERVER_MODE" = true ]; then
    echo "Checking containers..."
    docker ps --filter "name=nginx-proxy" --format "{{.Names}} {{.Status}}" || echo "nginx-proxy not running"
    docker ps --filter "name=nextcloud" --format "{{.Names}} {{.Status}}" || echo "nextcloud not running"
    echo ""
    
    echo "Testing nginx configuration..."
    docker exec nginx-proxy nginx -t 2>&1 || echo "nginx config test failed"
    echo ""
    
    echo "Checking nginx can reach Nextcloud..."
    docker exec nginx-proxy ping -c 2 nextcloud 2>&1 || echo "Cannot ping nextcloud container"
    echo ""
    
    echo "Testing internal connection..."
    docker exec nginx-proxy curl -I http://nextcloud:80/status.php 2>&1 | head -3 || echo "Internal connection failed"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. DNS Configuration Solutions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🔧 Solution 1: Configure Tailscale MagicDNS (Recommended)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Go to: https://login.tailscale.com/admin/dns"
echo ""
echo "2. Add nameserver:"
echo "   Type: Custom"
echo "   Address: 100.100.100.100"
echo ""
echo "3. Add DNS records:"
echo "   Domain: homelab.example.com"
echo "   Type: A"
echo "   Value: $TAILSCALE_IP"
echo ""
echo "   Domain: *.homelab.example.com"
echo "   Type: A"
echo "   Value: $TAILSCALE_IP"
echo ""
echo "4. Enable MagicDNS for your tailnet"
echo ""
echo "5. On your device:"
echo "   - Open Tailscale app"
echo "   - Settings → Enable 'Use Tailscale DNS'"
echo "   - Restart Tailscale if needed"
echo ""

echo "🔧 Solution 2: Use /etc/hosts (Quick Fix)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Add this line to /etc/hosts (Linux/macOS) or C:\\Windows\\System32\\drivers\\etc\\hosts (Windows):"
echo ""
echo "$TAILSCALE_IP $DOMAIN"
echo ""
echo "On Linux/macOS: sudo nano /etc/hosts"
echo "On Windows: Run Notepad as Administrator"
echo ""

echo "🔧 Solution 3: Use Direct IP (Temporary)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "For testing, you can access Nextcloud directly via IP:"
echo "  https://$TAILSCALE_IP:443"
echo ""
echo "Note: You'll need to accept the SSL certificate warning"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. Mobile App Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "For Nextcloud mobile apps, you have two options:"
echo ""
echo "Option A: Use domain (requires DNS):"
echo "  Server URL: https://cloud.homelab.example.com"
echo ""
echo "Option B: Use direct IP (no DNS needed):"
echo "  Server URL: https://$TAILSCALE_IP:443"
echo "  Note: You may need to accept SSL certificate warning"
echo ""

echo "✅ Diagnostic complete!"
echo ""
echo "Most common issue: Tailscale MagicDNS not configured or not enabled on device"
echo "Quick fix: Add $DOMAIN to /etc/hosts pointing to $TAILSCALE_IP"
