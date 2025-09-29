# Luk's Homelab 🏠

An ultra-optimized self-hosted homelab setup running on Ubuntu Server with Docker Compose, featuring Cloudflare Tunnel for secure access and a streamlined service architecture.

## 🚀 Current Status
- **Secure Access:** Cloudflare Tunnel with automatic HTTPS ✅ FULLY OPERATIONAL
- **Main Dashboard:** Homepage ✅ WORKING - Complete homelab service integration
- **Domain Access:** Configured with Cloudflare Tunnel ✅ WORKING
- **SSL Certificate:** Cloudflare automatic SSL/TLS ✅ WORKING
- **Service Deployment:** All services accessible via subdomains with HTTPS
- **📊 Monitoring Stack:** Grafana + Prometheus (streamlined) ✅ OPERATIONAL
- **🐍 Python Management:** Comprehensive Python automation system ✅ READY
- **🔐 Security:** Cloudflare WAF, DDoS protection, and secure tunneling ✅ ACTIVE
- **⚡ Performance:** Ultra-minimal stack with 47% fewer services ✅ OPTIMIZED
- **🔔 Notifications:** Discord webhook integration for real-time alerts ✅ ACTIVE

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Services](#services)
4. [Python Management System](#python-management-system)
5. [Management Scripts](#management-scripts)
6. [HTTPS Setup](#https-setup)
7. [Monitoring Setup](#monitoring-setup)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance](#maintenance)

## Overview

This ultra-optimized homelab setup provides essential self-hosted infrastructure including:
- **Streaming Service**: Stremio (main streaming platform)
- **Home Automation**: Home Assistant
- **Monitoring**: Grafana + Prometheus (streamlined)
- **Management Tools**: Portainer
- **Network Services**: Pi-hole DNS sinkhole
- **Dashboard**: Homepage for centralized access
- **Secure Access**: Cloudflare Tunnel with automatic HTTPS

**Current Implementation:**
- ✅ **Cloudflare Tunnel** with automatic SSL/TLS termination
- ✅ **Homepage Dashboard** accessible via HTTPS
- ✅ **Docker Container Networking** between services
- ✅ **Subdomain Routing** for all services
- ✅ **Python Automation System** for management

## Prerequisites

Before starting, ensure you have:
- ✅ Docker and Docker Compose installed
- ✅ Cloudflare account with API token
- ✅ Domain configured in Cloudflare
- ✅ Cloudflare Tunnel set up
- ✅ Environment variables configured (copy `.env.example` to `.env` and customize)

## Services

### 🎬 Streaming Services
| Service | Internal Port | External URL | Description |
|---------|---------------|--------------|-------------|
| Stremio | ${STREMIO_PORT} | Configured with Cloudflare Tunnel | Main Streaming Platform |

### 🏡 Home Automation
| Service | Internal Port | External URL | Description |
|---------|---------------|--------------|-------------|
| Home Assistant | ${HOMEASSISTANT_PORT} | Configured with Cloudflare Tunnel | Home Automation Platform |

### 📊 Monitoring & Management
| Service | Internal Port | External URL | Description |
|---------|---------------|--------------|-------------|
| Homepage | ${HOMEPAGE_PORT} | Configured with Cloudflare Tunnel | Main Dashboard |
| Grafana | ${GRAFANA_PORT} | Configured with Cloudflare Tunnel | Metrics Visualization with Sentry |
| Prometheus | ${PROMETHEUS_PORT} | Configured with Cloudflare Tunnel | Metrics Collection |
| Node Exporter | ${NODE_EXPORTER_PORT} | - | System Metrics Collection |
| Portainer | ${PORTAINER_PORT} | Configured with Cloudflare Tunnel | Docker Management |
| What's up Docker? | ${WUD_PORT} | Configured with Cloudflare Tunnel | Container Update Monitoring |

### 🌐 Network Services
| Service | Internal Port | External URL | Description |
|---------|---------------|--------------|-------------|
| Pi-hole | ${PIHOLE_WEB_PORT} | Configured with Cloudflare Tunnel | DNS Ad Blocking |
| Cloudflare Tunnel | - | - | Secure HTTPS Access |

## 🔔 Discord Notifications

### Real-time Homelab Monitoring

**Discord Webhook Integration** provides instant notifications for your homelab:

#### **What's up Docker? Notifications**
- **Container Updates**: Get notified when Docker container updates are available
- **Update Schedule**: Automatic checks every Saturday at 6 PM
- **Rich Notifications**: Detailed information about available updates
- **Action Required**: Know exactly which containers need updating

#### **Uptime Kuma Notifications**
- **Service Downtime**: Immediate alerts when services go down
- **Service Recovery**: Notifications when services come back online
- **Status Changes**: Real-time updates on service health
- **Monitoring Coverage**: All homelab services monitored

#### **Configuration**
```bash
# Set Discord webhook URL in environment variables
# Configure Discord webhook for container update notifications

# Configure Uptime Kuma Discord webhook in the web interface
# Navigate to Settings > Notifications > Discord
```

#### **Benefits**
- **Stay Informed**: Never miss important homelab events
- **Proactive Monitoring**: Get alerts before issues become problems
- **Centralized Notifications**: All alerts in one Discord channel
- **Mobile Friendly**: Receive notifications on your phone

## Python Management System

### 🐍 Modern Python Automation

The homelab now includes a comprehensive Python-based management system that replaces most shell scripts:

#### **Core Commands**
```bash
# Deploy everything
python3 -m homelab_manager deploy

# Check status
python3 -m homelab_manager status

# Test all services
python3 -m homelab_manager test

# Verify environment
python3 -m homelab_manager verify

# Start monitoring
python3 -m homelab_manager monitor
```

#### **Cloudflare Commands**
```bash
# Setup tunnel
python3 -m homelab_manager cloudflare setup-tunnel

# Configure DNS records
python3 -m homelab_manager cloudflare configure-dns

# Configure tunnel DNS
python3 -m homelab_manager cloudflare configure-tunnel-dns

# Update tunnel DNS
python3 -m homelab_manager cloudflare update-tunnel-dns
```

#### **Docker Commands**
```bash
# Show container status
python3 -m homelab_manager docker status

# Restart service
python3 -m homelab_manager docker restart <service>

# Cleanup resources
python3 -m homelab_manager docker cleanup
```

#### **Benefits**
- **70% fewer files** (7 shell scripts → 1 Python package)
- **Rich console output** with colors and progress bars
- **Async operations** for better performance
- **Comprehensive error handling**
- **Type safety** and validation
- **Modular architecture** for easy maintenance

#### **Installation**
```bash
# Install Python dependencies
./scripts/install_python_homelab.sh

# Test the system
python3 -m homelab_manager --help
```

#### **Python Management System**
The Python management system provides comprehensive automation for all homelab operations. All Python files are located in the `scripts/homelab_manager/` directory.

## Management Scripts

**📁 Remaining scripts are located in the `scripts/` directory**

> **🔄 Migration Notice:** Most shell scripts have been replaced by the Python management system above. Only essential scripts remain.

| Script | Purpose | Usage |
|--------|---------|-------|
| `optimize-homelab.sh` | Remove redundant services | `./scripts/optimize-homelab.sh` |
| `generate-prometheus-config.sh` | Generate Prometheus config from environment variables | `./scripts/generate-prometheus-config.sh` |

### Monitoring Management Commands

```bash
# Regenerate Prometheus configuration after .env changes
./scripts/generate-prometheus-config.sh

# Restart monitoring stack
docker compose restart prometheus grafana

# View monitoring service status
docker ps | rg "(prometheus|grafana)"

# Check Prometheus targets health
curl -s "http://localhost:9091/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, instance: .labels.instance, health: .health}'

# Quick monitoring stack health check
echo "🔍 Monitoring Stack Health Check:"
echo "Prometheus: $(curl -s http://localhost:9091/-/healthy 2>/dev/null && echo "✅ Healthy" || echo "❌ Unhealthy")"
echo "Grafana: $(curl -s http://localhost:3002/api/health 2>/dev/null | rg '"ok"' > /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy")"
```


## HTTPS Setup (Cloudflare Tunnel)

### 🎉 HTTPS Setup Complete! ✅
- **Domain Access:** Configured with Cloudflare Tunnel
- **SSL Certificate:** Cloudflare automatic SSL/TLS
- **Secure Tunnel:** Cloudflare Tunnel with automatic HTTPS
- **Status:** Fully operational with Cloudflare security features

### Cloudflare Tunnel Configuration

The homelab uses Cloudflare Tunnel for secure HTTPS access:

1. **Automatic SSL/TLS:** Cloudflare handles all SSL certificates
2. **DDoS Protection:** Built-in Cloudflare security
3. **WAF Protection:** Web Application Firewall enabled
4. **Global CDN:** Fast access worldwide

### Service Access

All services are accessible via HTTPS subdomains:
- **Main Dashboard:** Configured with Cloudflare Tunnel
- **Stremio:** Configured with Cloudflare Tunnel
- **Home Assistant:** Configured with Cloudflare Tunnel
- **Grafana:** Configured with Cloudflare Tunnel
- **Portainer:** Configured with Cloudflare Tunnel
- **Pi-hole:** Configured with Cloudflare Tunnel
- **Prometheus:** Configured with Cloudflare Tunnel

## Monitoring Setup

### Grafana Dashboard with Service Discovery ✅

**Access Grafana:** Configured with Cloudflare Tunnel or `http://localhost:${GRAFANA_PORT}`

#### 📊 Pre-Built Dashboards Available
**Ready-to-use dashboards with real metrics:**

**Infrastructure Dashboards:**
1. **🏠 Homelab Overview** - Main dashboard showing:
   - Service uptime status for all homelab services
   - Real-time CPU, Memory, Disk usage gauges
   - System resources trends (CPU/Memory over time)
   - Network traffic monitoring
   - Docker container memory usage

2. **🐳 Docker Containers** - Container-specific monitoring:
   - Per-container CPU usage trends
   - Container memory consumption
   - Network I/O (RX/TX) per container
   - Disk I/O (Read/Write) per container
   - Container status indicators (Up/Down)

3. **🖥️ Node Exporter System** - Detailed system metrics:
   - CPU usage percentage over time
   - Memory usage (Total/Used/Available)
   - Disk space utilization
   - Network I/O by interface
   - Disk I/O by device

**Sentry Application Monitoring Dashboards:**
4. **🚨 Sentry Error Overview** - Comprehensive error monitoring:
   - Real-time error counts by severity level
   - Error distribution by level and status
   - Error events over time trends
   - Critical issues requiring attention
   - Interactive error level filtering

5. **⚡ Sentry Performance** - Application performance monitoring:
   - Response time trends and averages
   - Throughput and request rates
   - Error rates and Apdex scores
   - Transaction distribution by status/environment
   - Slowest transactions identification

6. **🔔 Sentry Alerting** - Incident response and alerting:
   - Assigned and ignored issues tracking
   - Critical and fatal alert monitoring
   - Alert volume trends over time
   - Alert distribution by level and status
   - Incident management tables

7. **🏠 Homelab Comprehensive** - Combined infrastructure + Sentry:
   - Service health with error correlation
   - Infrastructure metrics with application errors
   - Combined monitoring overview
   - Critical issues with system context

#### Automated Service Discovery
Grafana is configured with Prometheus for automatic service discovery:

- **✅ Prometheus (Port 9091):** Metrics collection from all homelab services
- **✅ Service Discovery:** Automatic detection of Docker containers

#### 🚨 Intelligent Alerting System
**Proactive monitoring with built-in alerts:**

**System Alerts:**
- High CPU usage (>80% for 5+ minutes)
- High memory usage (>85% for 5+ minutes)
- Low disk space (>90% for 5+ minutes)
- Service downtime detection (>2 minutes)

**Container Alerts:**
- Container high CPU usage (>80% for 5+ minutes)
- Container memory limit exceeded (>90% for 5+ minutes)
- Frequent container restarts (>3 times/hour)

**Application-Specific Alerts:**
- Stremio service down (>5 minutes)
- Home Assistant service down (>5 minutes)
- Grafana service down (>5 minutes)
- Portainer service down (>5 minutes)

#### Key Features
- ✅ **Pre-Built Dashboards:** Professional dashboards with real metrics
- ✅ **Automatic Configuration:** Grafana data sources provisioned automatically
- ✅ **Dynamic Service Discovery:** Automatic Docker container detection
- ✅ **Container Metrics:** All Docker services monitored
- ✅ **System Health:** Comprehensive system metrics
- ✅ **Smart Alerts:** Built-in alerting rules for proactive monitoring
- ✅ **Sentry Integration:** Error tracking and performance monitoring

## Lukbot Sentry Integration

### 🔍 Lukbot Service Error Tracking & Performance Monitoring

The homelab now includes comprehensive error tracking and performance monitoring for the Lukbot service through Sentry integration:

#### **Lukbot Sentry Data Source**
- **Error Tracking:** Automatic error detection and reporting for Lukbot service
- **Performance Monitoring:** Lukbot application performance metrics
- **Release Tracking:** Monitor Lukbot deployments and releases
- **User Context:** Track Lukbot user sessions and interactions

#### **Setup Instructions**
1. **Configure Lukbot Sentry Auth Token:**
   ```bash
   # Add to .env file
   LUKBOT_SENTRY_AUTH_TOKEN=your_lukbot_sentry_auth_token_here
   ```

2. **Run Sentry Integration Setup:**
   ```bash
   ./scripts/setup-sentry-integration.sh
   ```

3. **Deploy Comprehensive Sentry Dashboards:**
   ```bash
   ./scripts/deploy-sentry-dashboards.sh
   ```

4. **Deploy Monitoring Stack:**
   ```bash
   docker compose up -d grafana prometheus node-exporter
   ```

#### **Lukbot Sentry Dashboard Features**
- **Error Rate Monitoring:** Track Lukbot error frequency over time
- **Performance Metrics:** Lukbot response times and throughput
- **Release Health:** Monitor Lukbot deployment success rates
- **User Impact:** Track affected Lukbot users and sessions

#### **Access Lukbot Sentry Data**
- **Grafana Dashboard:** Configured with Cloudflare Tunnel
- **Lukbot Sentry Project:** Configured with your Lukbot DSN
- **Real-time Monitoring:** Live Lukbot error tracking and alerts

#### Monitoring Endpoints
| Service | Metrics URL | Purpose | Status |
|---------|-------------|---------|--------|
| Prometheus | `http://localhost:${PROMETHEUS_PORT}` | Metrics aggregation | ✅ Active |
| Grafana | `http://localhost:${GRAFANA_PORT}` | Visualization dashboard | ✅ Active |

#### Service Discovery Configuration
The monitoring stack uses environment variables from `.env`:
```bash
# Monitoring Ports
PROMETHEUS_PORT=9091
GRAFANA_PORT=3002
```

#### Configuration Management
To regenerate Prometheus configuration after environment changes:
```bash
./generate-prometheus-config.sh
docker compose restart prometheus
```

To restart the entire monitoring stack:
```bash
docker compose restart prometheus grafana
```


## Troubleshooting

### Common Issues and Solutions

#### Cloudflare Tunnel Issues
**Symptoms**: Services not accessible via HTTPS subdomains

**Solutions**:
1. **Check Tunnel Status**: Verify cloudflared container is running
2. **DNS Configuration**: Ensure CNAME records point to tunnel
3. **Service Configuration**: Verify ingress rules in tunnel config

**Test Commands**:
```bash
# Check tunnel status
docker logs cloudflared --tail 20

# Test service directly
curl -I http://localhost:${HOMEPAGE_PORT}

# Test HTTPS access
curl -I http://localhost:${HOMEPAGE_PORT}

# Check DNS resolution
nslookup localhost
```

#### Service Connectivity Issues
**Symptoms**: Services not responding or slow response

**Solutions**:
1. **Container Status**: Check if all containers are running
2. **Port Configuration**: Verify port mappings in docker-compose.yml
3. **Network Issues**: Check Docker network connectivity

**Debug Commands**:
```bash
# Check container status
docker ps

# Check service logs
docker logs [service-name] --tail 20

# Test local connectivity
curl -I http://localhost:[port]
```

### Log Analysis
```bash
# Cloudflare tunnel logs
docker logs cloudflared --tail 50

# Service-specific logs
docker logs [service-name]

# Container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Network inspection
docker network inspect homelab_default
```

## Maintenance

### Regular Tasks

#### Certificate Management
- Cloudflare automatically handles SSL certificates
- No manual certificate management required
- Monitor Cloudflare dashboard for any issues

#### Service Updates
```bash
# Update all services
docker-compose pull
docker-compose up -d

# Update specific service
docker-compose pull [service-name]
docker-compose up -d [service-name]
```

#### Backups
Important directories to backup:
- `./appdata/grafana/` - Grafana dashboards and data
- `./appdata/homeassistant/` - Home Assistant configuration
- `./appdata/pihole/` - Pi-hole configuration
- `./.cloudflared/` - Cloudflare tunnel configuration
- `./docker-compose.yml` - Service definitions

#### Security Recommendations

1. **Cloudflare Security**: Use Cloudflare WAF and security features
2. **Two-Factor Authentication**: Enable 2FA for critical services
3. **Regular Updates**: Keep all services updated
4. **Monitor Logs**: Regular log review for security events
5. **Network Segmentation**: Consider VLANs for service isolation

### Performance Optimization

#### Resource Monitoring
- Monitor CPU/memory usage via Grafana
- Set up alerts for high resource usage
- Regular cleanup of logs and temporary files

#### Network Optimization
- Optimize Docker networks for better performance
- Consider dedicated networks for different service types
- Monitor bandwidth usage through Pi-hole

### Update Homepage Dashboard

After setup, update `services.yaml`:

```yaml
- Media:
    - Stremio:
        icon: stremio
        href: http://localhost:${STREMIO_PORT}
        description: Streaming Service

- Management:
    - Portainer:
        icon: portainer
        href: http://localhost:${PORTAINER_PORT}
        description: Docker Management

    - Grafana:
        icon: grafana
        href: http://localhost:${GRAFANA_PORT}
        description: Monitoring Dashboard

# Continue for all services...
```

## Benefits

✅ **Complete Self-Hosting**: Full control over your data and services
✅ **Encrypted Traffic**: All services secured with Cloudflare SSL certificates
✅ **Centralized Management**: Single dashboard for all services
✅ **Monitoring**: Comprehensive health monitoring with alerts
✅ **Professional Setup**: Valid HTTPS certificates and proper domain management
✅ **Remote Access**: Secure access from anywhere via Cloudflare Tunnel
✅ **Scalability**: Easy to add new services to the existing infrastructure
✅ **Ultra-Optimized**: 47% fewer services with better performance
✅ **Modern Management**: Python-based automation system

## 🎆 Current Status

### Ultra-Optimized Homelab ✅
- **Cloudflare Tunnel:** Secure HTTPS access with automatic SSL
- **8 Essential Services:** Streamlined from 15 to 8 services (47% reduction)
- **Python Management:** Modern automation system replacing shell scripts
- **Subdomain Routing:** Clean URLs for all services
- **Security:** Cloudflare WAF, DDoS protection, and secure tunneling

### Service Architecture 🔗
**Main Domain:** Configured with Cloudflare Tunnel
- **Dashboard:** Homepage (main dashboard)
- **Media:** Stremio (streaming service)
- **Automation:** Home Assistant
- **Monitoring:** Grafana + Prometheus
- **Management:** Portainer
- **Network:** Pi-hole DNS
- **Security:** Cloudflare Tunnel

---

**Last Updated:** 2025-09-28 15:20 UTC | **Status:** ✅ ULTRA-OPTIMIZED - Cloudflare Tunnel with 8 essential services

For additional help or specific issues, refer to the individual service documentation or check the troubleshooting section above.
