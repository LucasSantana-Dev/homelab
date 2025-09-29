# Changelog

## [2.3.2] - 2025-01-09

### 🔔 DISCORD WEBHOOK INTEGRATION

#### Added
- **Discord Webhook Support**: Real-time notifications for container updates
- **What's up Docker? Discord Integration**: Automatic Discord notifications when container updates are available
- **Uptime Kuma Discord Integration**: Discord alerts for service downtime and recovery
- **Unified Notification System**: Centralized Discord notifications for homelab monitoring

#### Features
- **Container Update Alerts**: Get notified immediately when Docker container updates are available
- **Service Status Alerts**: Receive Discord notifications when services go down or come back up
- **Real-time Monitoring**: Stay informed about your homelab status without checking dashboards
- **Customizable Notifications**: Configure Discord webhook URLs for different notification channels

#### Configuration
- **Discord Webhook URL**: Configure Discord webhook in environment variables
- **Uptime Kuma Webhook**: Configure Discord webhook in Uptime Kuma settings
- **Notification Channels**: Use different Discord channels for different types of alerts
- **Message Formatting**: Rich Discord embeds with service information and status

## [2.3.1] - 2025-01-09

### 🧹 PROJECT CLEANUP & SECURITY IMPROVEMENTS

#### Cleaned Up
- **Temporary Scripts Removed**: Cleaned up 5 temporary scripts from `/scripts/` directory
- **Security Hardening**: Removed hardcoded secrets from configuration files
- **Code Organization**: Streamlined scripts directory with only permanent, production-ready scripts

#### Removed Temporary Scripts
- `fix-datasource-issue.sh` - Temporary Grafana datasource fix
- `verify-working-dashboards.sh` - Temporary dashboard verification
- `fix-docker-permissions.sh` - Temporary Docker permission fix
- `deploy-sentry-dashboards.sh` - Temporary Sentry deployment
- `setup-sentry-integration.sh` - Temporary Sentry setup

#### Security Improvements
- **Environment Variables**: All sensitive data moved to environment variables
- **No Hardcoded Secrets**: Removed hardcoded passwords, tokens, and URLs
- **Git Safety**: Confirmed `.env` file is properly gitignored
- **Best Practices**: Implemented secure configuration management

#### Permanent Scripts Retained
- `container-status.sh` - Container monitoring and status checking
- `update-containers.sh` - Automated container updates
- `update-specific-containers.sh` - Targeted container updates
- `deploy-monitoring-stack.sh` - Monitoring stack deployment
- `setup-uptime-kuma.sh` - Uptime Kuma configuration
- `setup.py` - Python management system
- `install_python_homelab.sh` - Python environment setup
- `requirements.txt` - Python dependencies
- `homelab_manager/` - Python package directory

## [2.3.0] - 2025-01-09

### 🐳 WHAT'S UP DOCKER? SERVICE RELEASE

#### Added
- **What's up Docker? (WUD) Service**: Container update monitoring and notification system
- **Docker Container Monitoring**: Automatic detection of available container updates
- **Scheduled Update Checks**: Runs every Saturday at 6 PM to check for updates
- **Multiple Notification Methods**: Discord webhook and SMTP email notifications support
- **Discord Integration**: Real-time notifications for container updates via Discord webhook
- **Web Interface**: Accessible dashboard for monitoring container update status
- **Docker Socket Integration**: Direct access to Docker daemon for container monitoring

#### Configuration
- **Port**: 3003 (configurable via WUD_PORT environment variable)
- **Schedule**: Every Saturday at 6 PM (configurable via WUD_WATCHER_LOCAL_CRON)
- **Notifications**: Discord webhook and SMTP email support
- **Data Persistence**: Volume mounted for configuration and data storage
- **Security**: Read-only Docker socket access for monitoring

#### Environment Variables
- Service port configuration
- Discord webhook for notifications
- SMTP server for email notifications
- Email authentication settings
- Notification recipient configuration

#### Documentation
- **Official Documentation**: https://fmartinou.github.io/whats-up-docker/
- **GitHub Repository**: https://github.com/fmartinou/whats-up-docker
- **Web Interface**: Accessible at http://localhost:3003 or https://wud.homelab.example.com

#### Integration
- **Homepage Integration**: Added to management tools section
- **Docker Compose**: Integrated into homelab stack
- **Monitoring**: Part of comprehensive homelab monitoring solution
- **Discord Notifications**: Real-time alerts for container updates and service status
- **Uptime Kuma Integration**: Discord webhook notifications for service downtime

## [2.2.0] - 2025-01-09

### 📊 COMPREHENSIVE SENTRY DASHBOARDS RELEASE

#### Added
- **Sentry Error Overview Dashboard**: Comprehensive error monitoring with real-time metrics
- **Sentry Performance Dashboard**: Application performance monitoring with response times and throughput
- **Sentry Alerting Dashboard**: Incident response and alert management
- **Homelab Comprehensive Dashboard**: Combined infrastructure and Sentry monitoring
- **Automated Dashboard Deployment**: Script-based dashboard provisioning

#### Enhanced
- **Error Monitoring**: Real-time error tracking with level-based filtering
- **Performance Metrics**: Response time trends, throughput, and Apdex scores
- **Alert Management**: Critical issue tracking and assignment status
- **Infrastructure Integration**: Combined Sentry + Prometheus monitoring
- **Interactive Dashboards**: Dynamic filtering and time range selection

#### New Dashboard Features
- **Error Distribution**: Visual breakdown by level and status
- **Performance Trends**: Historical performance data visualization
- **Alert Volume**: Time-series alert monitoring
- **Service Health**: Combined infrastructure and application status
- **Critical Issues Table**: Prioritized issue management

#### Scripts
- `deploy-sentry-dashboards.sh` - Automated dashboard deployment
- Enhanced Sentry integration setup with comprehensive dashboards

#### Documentation
- **Dashboard Overview**: Complete guide to new monitoring capabilities
- **Setup Instructions**: Step-by-step dashboard deployment
- **Feature Descriptions**: Detailed explanation of each dashboard

---

## [2.1.0] - 2025-01-09

### 🔧 MONITORING ENHANCEMENT RELEASE

#### Added
- **Grafana with Sentry Integration**: Complete monitoring stack with error tracking
- **Prometheus Service Discovery**: Automatic detection of homelab services
- **Sentry Data Source**: Error tracking and performance monitoring
- **Comprehensive Dashboards**: Pre-built monitoring dashboards
- **Cloudflare Tunnel Integration**: Secure access to monitoring services

#### Enhanced
- **Monitoring Stack**: Added Grafana, Prometheus, and Node Exporter
- **Service Health Monitoring**: Real-time status of all homelab services
- **Error Tracking**: Sentry integration for application error monitoring
- **Performance Metrics**: CPU, Memory, Disk usage monitoring
- **Automated Configuration**: Provisioned datasources and dashboards

#### New Services
- `grafana` - Metrics visualization with Sentry integration
- `prometheus` - Metrics collection and service discovery
- `node-exporter` - System metrics collection

#### Security
- **Secure Monitoring**: All monitoring services accessible via HTTPS
- **Environment Variables**: Sensitive data properly managed
- **Access Control**: Grafana admin authentication

#### Documentation
- **Setup Scripts**: Automated Sentry integration setup
- **Configuration Guides**: Step-by-step monitoring setup
- **Service Access**: Updated service URLs and access methods

---

## [2.0.0] - 2025-09-28

### 🚀 MAJOR OPTIMIZATION RELEASE

#### Added
- **Cloudflare Tunnel Integration**: Secure HTTPS access with automatic SSL/TLS
- **Python Automation System**: Comprehensive Python-based homelab management
- **Subdomain Routing**: Clean URLs for all services
- **Ultra-Minimal Architecture**: Reduced from 15 to 8 services (47% reduction)

#### Changed
- **Removed Caddy**: Cloudflare Tunnel handles all reverse proxy functionality
- **Streamlined Monitoring**: Kept only Grafana + Prometheus
- **Single Streaming Service**: Replaced Jellyfin + Jellyseerr with Stremio
- **Removed File Browser**: Simplified file management approach

#### Removed
- **Jellyfin**: Replaced by Stremio for streaming
- **Jellyseerr**: No longer needed with Stremio
- **Caddy**: Redundant with Cloudflare Tunnel
- **cAdvisor**: Container metrics now handled by Prometheus
- **Node Exporter**: System metrics simplified
- **Uptime Kuma**: Service monitoring handled by Grafana
- **File Browser**: Web-based file management removed

#### Performance Improvements
- **Memory Usage**: Reduced by ~600MB (37% reduction)
- **Service Count**: Reduced from 15 to 8 services (47% reduction)
- **Startup Time**: Faster container startup
- **Maintenance**: Significantly simplified management

#### Security Enhancements
- **Cloudflare WAF**: Automatic DDoS protection
- **Automatic SSL/TLS**: Cloudflare handles all SSL certificates
- **Secure Tunneling**: No direct port exposure

### Services Retained
- `homepage` - Main dashboard
- `stremio` - Streaming service
- `homeassistant` - Home automation
- `pihole` - DNS sinkhole
- `grafana` - Metrics visualization
- `prometheus` - Metrics collection
- `portainer` - Docker management
- `cloudflared` - Secure access

---

## [1.0.0] - 2025-08-14

### Initial Release
- Complete homelab setup with Docker Compose
- Caddy reverse proxy with DuckDNS integration
- Jellyfin media server with Jellyseerr
- Home Assistant automation
- Grafana monitoring stack
- Pi-hole DNS sinkhole
- Portainer Docker management
- File Browser for file management
