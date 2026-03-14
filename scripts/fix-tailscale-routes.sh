#!/bin/bash
# Fix Tailscale subnet routing configuration
# This script fixes the mismatch between advertised routes and actual network

set -euo pipefail

echo "🔧 Fixing Tailscale subnet routing configuration..."

# Get actual local network
LOCAL_NETWORK=$(ip route | grep -E "192\.168\.[0-9]+\.[0-9]+/24" | head -1 | awk '{print $1}' | cut -d'/' -f1 | sed 's/\.[0-9]*$//')".0/24"

if [ -z "$LOCAL_NETWORK" ]; then
    echo "❌ Could not detect local network. Please specify manually."
    exit 1
fi

echo "📡 Detected local network: $LOCAL_NETWORK"

# Get current advertised routes (handle null/empty safely)
CURRENT_ROUTES=$(tailscale status --json 2>&1 | jq -r '.Self.PrimaryRoutes[]? // empty' | tr '\n' ',' | sed 's/,$//')

if [ -z "$CURRENT_ROUTES" ]; then
    echo "ℹ️  No routes currently advertised"
else
    echo "📋 Current advertised routes: $CURRENT_ROUTES"
fi

# Fix the routes
echo "🔨 Updating advertised routes to: $LOCAL_NETWORK"
sudo tailscale set --advertise-routes="$LOCAL_NETWORK"

# Wait a moment for changes to propagate
sleep 2

# Verify the change (handle null/empty safely)
NEW_ROUTES=$(tailscale status --json 2>&1 | jq -r '.Self.PrimaryRoutes[]? // empty' | tr '\n' ',' | sed 's/,$//')

if [ -z "$NEW_ROUTES" ]; then
    echo "⚠️  Routes updated but not yet active (may need approval in admin console)"
    echo "   Check advertised routes status:"
    tailscale status --json 2>&1 | jq -r '.Self.PrimaryRoutes // "None"' || echo "None"
else
    echo "✅ New advertised routes: $NEW_ROUTES"
fi

echo ""
echo "⚠️  IMPORTANT: You must approve these routes in the Tailscale admin console:"
echo "   1. Go to https://login.tailscale.com/admin/machines/homelab-node-01"
echo "   2. Click 'Edit route settings...'"
echo "   3. Approve the route for $LOCAL_NETWORK"
echo ""
echo "✅ Route configuration updated successfully!"
