#!/bin/bash
# Disable Tailscale exit node option if not needed
# This may fix the "Active: false" error in Tailscale admin console

set -euo pipefail

echo "🔧 Fixing Tailscale exit node configuration..."

# Check current status
CURRENT_EXIT_NODE=$(tailscale status --json 2>&1 | jq -r '.Self.ExitNodeOption // false')

if [ "$CURRENT_EXIT_NODE" = "true" ]; then
    echo "⚠️  Exit node option is currently enabled"
    echo "   This might be causing the 'Active: false' error"
    echo ""
    echo "   Disabling exit node option..."
    sudo tailscale set --advertise-exit-node=false

    sleep 2

    # Verify
    NEW_EXIT_NODE=$(tailscale status --json 2>&1 | jq -r '.Self.ExitNodeOption // false')
    if [ "$NEW_EXIT_NODE" = "false" ]; then
        echo "✅ Exit node option disabled successfully"
    else
        echo "⚠️  Exit node option still enabled (may need admin console approval)"
    fi
else
    echo "ℹ️  Exit node option is already disabled"
fi

echo ""
echo "📊 Current Tailscale status:"
tailscale status --json 2>&1 | jq -r '.Self | {ExitNodeOption, ExitNode, Active, Online, PrimaryRoutes}' | cat

echo ""
echo "💡 If the error persists, check the Tailscale admin console:"
echo "   https://login.tailscale.com/admin/machines/homelab-node-01"
