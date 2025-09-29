#!/bin/bash
# Deploy Complete Monitoring Stack with Sentry Integration
# This script deploys Grafana, Prometheus, and Node Exporter with proper Sentry integration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Complete Monitoring Stack with Sentry Integration...${NC}"

# Check if .env file exists
if [[ ! -f .env ]]; then
    echo -e "${RED}❌ Error: .env file not found. Please copy .env.example to .env and configure it.${NC}"
    exit 1
fi

# Load environment variables
source .env

# Check if required environment variables are set
required_vars=("GRAFANA_PASSWORD" "LUKBOT_SENTRY_DSN" "LUKBOT_SENTRY_AUTH_TOKEN")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        echo -e "${RED}❌ Error: $var is not set in .env file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ Environment variables validated${NC}"

# Create necessary directories
echo -e "${YELLOW}📁 Creating directories...${NC}"
mkdir -p appdata/grafana/provisioning/datasources
mkdir -p appdata/grafana/provisioning/dashboards/homelab
mkdir -p appdata/grafana/provisioning/dashboards/sentry
mkdir -p appdata/prometheus

# Set proper permissions
echo -e "${YELLOW}🔐 Setting permissions...${NC}"
chown -R ${PUID}:${PGID} appdata/grafana appdata/prometheus

# Stop existing monitoring stack if running
echo -e "${YELLOW}🛑 Stopping existing monitoring stack...${NC}"
docker compose down grafana prometheus node-exporter 2>/dev/null || true

# Deploy monitoring stack
echo -e "${YELLOW}🐳 Deploying monitoring containers...${NC}"
docker compose up -d grafana prometheus node-exporter

# Wait for services to start
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 15

# Check service health
echo -e "${YELLOW}🔍 Checking service health...${NC}"

# Check Grafana
timeout=60
counter=0
while ! curl -s http://localhost:${GRAFANA_PORT}/api/health > /dev/null; do
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}❌ Timeout waiting for Grafana to start${NC}"
        exit 1
    fi
    sleep 2
    counter=$((counter + 2))
done
echo -e "${GREEN}✅ Grafana is healthy${NC}"

# Check Prometheus
timeout=60
counter=0
while ! curl -s http://localhost:${PROMETHEUS_PORT}/-/healthy > /dev/null; do
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}❌ Timeout waiting for Prometheus to start${NC}"
        exit 1
    fi
    sleep 2
    counter=$((counter + 2))
done
echo -e "${GREEN}✅ Prometheus is healthy${NC}"

# Check Node Exporter
timeout=60
counter=0
while ! curl -s http://localhost:${NODE_EXPORTER_PORT}/metrics > /dev/null; do
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}❌ Timeout waiting for Node Exporter to start${NC}"
        exit 1
    fi
    sleep 2
    counter=$((counter + 2))
done
echo -e "${GREEN}✅ Node Exporter is healthy${NC}"

# Test Prometheus targets
echo -e "${YELLOW}🔍 Testing Prometheus targets...${NC}"
sleep 5
if curl -s "http://localhost:${PROMETHEUS_PORT}/api/v1/targets" | grep -q "UP"; then
    echo -e "${GREEN}✅ Prometheus targets are UP${NC}"
else
    echo -e "${YELLOW}⚠️  Some Prometheus targets may not be ready yet${NC}"
fi

# Test Sentry datasource
echo -e "${YELLOW}🔍 Testing Sentry datasource...${NC}"
sleep 5
if curl -s -u admin:${GRAFANA_PASSWORD} "http://localhost:${GRAFANA_PORT}/api/datasources" | grep -q "sentry"; then
    echo -e "${GREEN}✅ Sentry datasource configured${NC}"
else
    echo -e "${YELLOW}⚠️  Sentry datasource may need manual configuration${NC}"
fi

echo -e "${BLUE}📊 Monitoring Stack Deployment Complete!${NC}"
echo -e ""
echo -e "${GREEN}🎉 Your monitoring services are available:${NC}"
echo -e ""
echo -e "${BLUE}📋 Service URLs:${NC}"
echo -e "  • Grafana: https://grafana.${DOMAIN}"
echo -e "    Username: admin"
echo -e "    Password: \${GRAFANA_PASSWORD}"
echo -e ""
echo -e "  • Prometheus: https://prometheus.${DOMAIN}"
echo -e ""
echo -e "${BLUE}📊 Available Dashboards:${NC}"
echo -e "  • Homelab Infrastructure Overview - System metrics and service health"
echo -e "  • Sentry Error Monitoring - Application error tracking"
echo -e ""
echo -e "${YELLOW}📋 Next steps:${NC}"
echo -e "1. Access Grafana and navigate to the dashboard folders"
echo -e "2. Check that data is flowing from both Prometheus and Sentry"
echo -e "3. Configure alerting rules if needed"
echo -e "4. Set up notification channels for critical alerts"
echo -e ""
echo -e "${BLUE}🔧 Troubleshooting:${NC}"
echo -e "  • Check container logs: docker compose logs grafana prometheus node-exporter"
echo -e "  • Verify datasources in Grafana: Configuration > Data Sources"
echo -e "  • Test Prometheus targets: http://localhost:${PROMETHEUS_PORT}/targets"
echo -e ""
echo -e "${GREEN}✨ Monitoring stack is ready with Sentry integration!${NC}"
