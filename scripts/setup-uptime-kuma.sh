#!/bin/bash

# Uptime Kuma Setup Script
# This script helps configure Uptime Kuma monitoring for your homelab services

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Setting up Uptime Kuma Monitoring${NC}"
echo "================================================"

# Check if Uptime Kuma is running
if ! curl -s http://localhost:3001 > /dev/null; then
    echo -e "${RED}❌ Uptime Kuma is not running. Please start it first:${NC}"
    echo "   docker compose up -d uptime-kuma"
    exit 1
fi

echo -e "${GREEN}✅ Uptime Kuma is running!${NC}"
echo ""
echo -e "${YELLOW}📋 Manual Setup Instructions:${NC}"
echo "================================================"
echo ""
echo "1. 🌐 Access Uptime Kuma:"
echo "   • Local: http://localhost:3001"
echo "   • Public: https://uptime.${DOMAIN}"
echo ""
echo "2. 🔧 Initial Setup:"
echo "   • Create admin account"
echo "   • Set up your first monitoring targets"
echo ""
echo "3. 📊 Recommended Monitoring Targets:"
echo "   • Homepage: http://homepage:3000"
echo "   • Home Assistant: http://homeassistant:8123"
echo "   • Portainer: http://portainer:9000"
echo "   • Pi-hole: http://pihole:80"
echo "   • Stremio: http://stremio-server:11470"
echo "   • Grafana: http://grafana:3000"
echo "   • Prometheus: http://prometheus:9090"
echo "   • Uptime Kuma: http://uptime-kuma:3001"
echo ""
echo "4. 🔔 Notification Setup:"
echo "   • Discord Webhook (recommended)"
echo "   • Email notifications"
echo "   • Telegram bot"
echo "   • Slack webhook"
echo ""
echo "5. 📈 Advanced Features:"
echo "   • SSL certificate monitoring"
echo "   • Database monitoring"
echo "   • Custom metrics"
echo "   • Status pages"
echo ""
echo -e "${GREEN}🎉 Uptime Kuma is ready for configuration!${NC}"
echo ""
echo -e "${BLUE}💡 Pro Tips:${NC}"
echo "• Set up monitoring intervals (1-5 minutes)"
echo "• Configure retry attempts (2-3)"
echo "• Enable status pages for public monitoring"
echo "• Use tags to organize your services"
echo "• Set up maintenance windows for updates"
echo ""
echo -e "${YELLOW}🔗 Useful Links:${NC}"
echo "• Documentation: https://github.com/louislam/uptime-kuma"
echo "• Status Page: https://uptime.${DOMAIN}/status"
echo "• Dashboard: https://uptime.${DOMAIN}/dashboard"

