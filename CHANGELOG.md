# Changelog

All notable changes to Luk's Homelab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Alertmanager** - Alert routing and notification management
  - Accessible at https://alertmanager.homelab.example.com (Tailscale only)
  - Integrated with Prometheus for alert management
  - Configured for Discord/Email/Slack webhook notifications (webhook URL must be configured in .env)
  - Alert grouping by severity (critical/warning) with smart repeat intervals
  - Inhibition rules to prevent alert flooding
  - Resource limits: 256M RAM max, 0.25 CPU max

- **Blackbox Exporter** - HTTP/TCP endpoint monitoring
  - Probes service availability and response times
  - Configured for HTTP 2xx status checks, POST requests, and TCP connectivity
  - Integrated with Prometheus for endpoint monitoring
  - Resource limits: 128M RAM max, 0.1 CPU max

- **Nextcloud** - Self-hosted cloud storage and productivity platform
  - Accessible at https://cloud.homelab.example.com (Tailscale only)
  - Integrated with MariaDB for database and Redis for caching
  - Configured with trusted domains and proxy settings
  - Resource limits: Nextcloud (1G RAM max, 1.0 CPU max), MariaDB (512M RAM max, 0.5 CPU max), Redis (128M RAM max, 0.25 CPU max)

### Fixed

- **Vaultwarden Health Check**: Changed from `wget` to `curl` for health check compatibility
- **Promtail**: Recreated container to clear unhealthy status (no health endpoint by design)
- **Container Cleanup**: Removed old Discord bot containers (discord-bot, discord-bot-postgres, discord-bot-redis)
- **Nextcloud SSL**: Updated nginx configuration to use correct SSL certificate paths (`/etc/nginx/ssl/`)

### Changed

- **Prometheus Configuration**: Enhanced with Alertmanager integration and new scrape targets
  - Added alerting configuration pointing to Alertmanager (alertmanager:9093)
  - Added Alertmanager metrics scraping (15s interval)
  - Added Blackbox Exporter scraping (30s interval)
  - Prepared for Nginx Exporter integration (commented out, pending deployment)

- **Promtail Log Processing**: Significantly enhanced log parsing capabilities
  - Added log level extraction (ERROR, WARN, INFO, DEBUG)
  - Added HTTP status code detection and labeling
  - Added structured labels for better filtering (container_name, log_level, status_code)
  - Added multiline log support for stack traces and exceptions
  - Added timestamp parsing from logs
  - Added JSON log parsing for Docker container logs

- **Homepage Dashboard**: Updated monitoring section to include Alertmanager

- **Security Updates**: Updated Python dependencies to fix vulnerabilities
  - requests: 2.31.0 → 2.32.3 (fixes CVE-2024-35195)
  - typer: 0.9.0 → 0.12.5
  - rich: 13.7.0 → 13.8.1
  - docker: 7.0.0 → 7.1.0
  - pytest: 7.4.3 → 8.3.3
  - Other development dependencies updated to latest stable versions

- **Certbot SSL**: Documented incompatibility with Tailscale-only DNS setup
  - Certbot requires public DNS resolution for HTTP-01 challenge
  - Domain `homelab.example.com` is intentionally private (Tailscale-only)
  - Current setup uses existing wildcard SSL certificates
  - Future: Configure DNS-01 challenge with DNS provider API integration

## [2.2.0] - 2025-11-02

### 🚀 Major Expansion: New Services and Infrastructure Improvements

#### Added

- **Vaultwarden** - Self-hosted password manager (Bitwarden-compatible)
  - Accessible at https://vault.homelab.example.com (Tailscale only)
  - Admin panel with token authentication
  - WebSocket support for real-time notifications
  - Resource limits: 256M RAM max, 0.25 CPU max

- **Jellyfin** - Media server for streaming content
  - Accessible at https://jellyfin.homelab.example.com (Tailscale only)
  - Read-only media directory mounting
  - WebSocket support for live interface updates
  - Optimized proxy settings for streaming (no buffering, 300s timeouts)
  - Resource limits: 2G RAM max, 1.0 CPU max

- **n8n** - Workflow automation platform (configuration ready)
  - Accessible at https://n8n.homelab.example.com (Tailscale only)
  - Basic authentication enabled
  - WebSocket support for real-time workflow updates
  - Resource limits: 512M RAM max, 0.5 CPU max
  - Deployment pending Docker Hub rate limit reset

#### Fixed

- **SSL Certificate Renewal** - Added Let's Encrypt ACME challenge exception to nginx IP restrictions
- **Prometheus Monitoring** - Removed FileBrowser from scrape targets (no metrics endpoint)
- **Container Updates** - Updated all 11 existing containers to latest versions
- **Security** - Enhanced nginx IP restrictions to allow only Tailscale network and localhost access

#### Manual Tasks Required

- **Home Assistant**: Xiaomi OAuth integration requires token refresh via UI (Settings > Devices & Services)
- **Uptime Kuma**: Monitor timeout adjustments needed via UI for Home Page monitor (increase to 120s)

### Infrastructure Notes

- All new services bound exclusively to Tailscale IP for secure access
- Nginx reverse proxy configured for all new subdomains with SSL support
- Health checks and resource limits applied to all new services
- Comprehensive logging configured for all services

## [2.1.0] - 2025-01-09

### 🔧 Bug Fixes and Improvements

#### Removed

- **DuckDNS Integration**: Completely removed DuckDNS cron job and dependencies
- **Legacy Scripts**: Removed DuckDNS update script and log files
- **Environment Variables**: Cleaned up DuckDNS token from system environment
- **Cron Jobs**: Streamlined crontab to only include homelab automation tasks

#### Fixed

- **Security Issue**: Replaced `os.system()` with `subprocess.run()` for better security
- **Test Issues**: Fixed hardcoded paths in test classes to use test directories
- **Type Annotations**: Added missing type annotations for better type checking
- **Test Mocking**: Improved test fixtures and mocking for more reliable tests

#### Added

- **Development Documentation**: Comprehensive development guide with best practices
- **Fixed Test Files**: Separate test files with proper test directory handling
- **Security Improvements**: Better subprocess handling and input validation

#### Changed

- **Test Architecture**: Tests now properly use temporary directories
- **Security Scanning**: Enhanced security checks with better subprocess handling
- **Development Workflow**: Improved development commands and documentation

## [2.0.0] - 2025-01-09

### 🎉 Major Release: Python-Based Automation System

#### Added

- **Python Automation System** - Complete rewrite in Python for better maintainability
- **Rich CLI Interface** - Beautiful, colored command-line interface
- **Comprehensive Health Monitoring** - Service health checks with system resource monitoring
- **Advanced Update Management** - Automated update checking and deployment
- **Configuration Validation** - Environment variable validation with security checks
- **Automated Backup System** - Docker volume backups with retention policies
- **Cron Integration** - Automated task scheduling for maintenance
- **Service Version Tracking** - Current version monitoring for all services

#### Changed

- **Converted from Shell to Python** - All automation scripts now use Python
- **Simplified Architecture** - Removed overkill components (Terraform, Ansible, complex monitoring)
- **Enhanced Error Handling** - Comprehensive exception handling and user feedback
- **Improved Logging** - Structured logging with file and console output
- **Better Documentation** - Comprehensive README with examples and architecture

#### Removed

- **Terraform Infrastructure** - Too complex for homelab use case
- **Ansible Playbooks** - Overkill for single-server deployment
- **Complex Monitoring Stack** - ELK stack, Alertmanager, complex Prometheus alerts
- **GitHub Actions CI/CD** - Not needed for personal homelab
- **Shell Scripts** - Converted to Python equivalents
- **DevOps Analysis Documentation** - Analysis complete, no longer needed

#### Fixed

- **Environment Variable Loading** - Safer parsing with special character support
- **Docker Container Management** - Better error handling and status reporting
- **Backup System** - Improved reliability and error handling
- **Service Health Checks** - More robust HTTP endpoint checking

#### Security

- **Environment Variable Validation** - Comprehensive validation with security checks
- **Secure Configuration Templates** - `.env.example` with placeholder values
- **Improved Secret Management** - All sensitive data in environment variables
- **Docker Security** - Non-root execution and network isolation
- **Zero Hardcoded Secrets** - All sensitive data properly externalized
- **Password Strength Validation** - Automatic password complexity checks
- **Token Format Validation** - Ensures proper API token formats
- **Secure Subprocess Handling** - Uses `subprocess.run()` instead of `os.system()`

## [1.0.0] - 2025-01-09

### 🏠 Initial Release: Home Assistant Dashboard Setup

#### Added

- **Home Assistant Dashboard** - Custom dashboard with HACS components
- **HACS Integration** - Home Assistant Community Store setup
- **Mushroom Cards** - Modern card collection for Lovelace
- **Button Card** - Highly customizable button card
- **Mini Graph Card** - Minimalistic graph card for sensor data
- **UI Lovelace Minimalist** - Clean theme and card collection
- **Docker Compose Setup** - Container orchestration for homelab services
- **Environment Configuration** - Secure environment variable management
- **Basic Automation** - Shell scripts for container management

#### Services

- **Home Assistant** - Home automation hub
- **Grafana** - Monitoring and dashboards
- **Portainer** - Container management
- **Pi-hole** - Network-wide ad blocking
- **Uptime Kuma** - Uptime monitoring
- **Prometheus** - Metrics collection
- **What's Up Docker** - Container update monitoring

#### Features

- **Dashboard Configuration** - YAML-based dashboard setup
- **Theme Integration** - Brazilian theme for Home Assistant
- **Service Health Monitoring** - Basic health checks
- **Backup System** - Manual backup functionality
- **Update Management** - Container update checking

---

## Version History

- **v2.0.0** - Python-based automation system with comprehensive features
- **v1.0.0** - Initial Home Assistant dashboard setup with basic automation

## Migration Guide

### From v1.0.0 to v2.0.0

1. **Environment Variables** - No changes needed, all existing variables are compatible
2. **Docker Compose** - No changes needed, same configuration
3. **Application Data** - No changes needed, all data preserved
4. **New Commands** - Use `./homelab` instead of individual scripts
5. **Python Dependencies** - Run `pip install -r scripts/requirements.txt` in virtual environment

### Breaking Changes

- **Shell Scripts Removed** - All shell automation scripts converted to Python
- **Terraform/Ansible Removed** - Infrastructure as Code components removed
- **Complex Monitoring Removed** - ELK stack and complex monitoring removed

### New Features

- **Rich CLI** - Beautiful command-line interface
- **Automated Tasks** - Cron job integration
- **Configuration Validation** - Environment variable validation
- **Service Version Tracking** - Current version monitoring
- **Enhanced Health Monitoring** - Comprehensive service health checks

## Future Roadmap

### Planned Features

- **Web Dashboard** - Web-based management interface
- **Mobile App** - Mobile management application
- **Advanced Monitoring** - Custom Grafana dashboards
- **Backup Encryption** - Encrypted backup storage
- **Service Dependencies** - Dependency-aware updates
- **Health Alerts** - Email/Discord notifications
- **Performance Metrics** - Detailed performance monitoring

### Potential Improvements

- **Kubernetes Support** - Optional Kubernetes deployment
- **Multi-Node Support** - Distributed homelab setup
- **Advanced Security** - Security scanning and hardening
- **Backup Verification** - Automated backup testing
- **Service Discovery** - Automatic service detection
- **Plugin System** - Extensible automation system

---

*This changelog follows [Keep a Changelog](https://keepachangelog.com/) format and [Semantic Versioning](https://semver.org/) principles.*


##  [2.3.0] - Infrastructure Cleanup and Security Hardening

### Removed

- **nginx-proxy-manager** - Redundant reverse proxy service (consumed resources, exposed public ports)
- **certbot** service - Incompatible with Tailscale-only DNS setup
- **28 dangling Docker volumes** - Reclaimed ~2GB disk space
- **Orphaned containers** - Removed 2 github-mcp-server containers
- **Lukbot resources** - Removed old Discord bot volumes (postgres_data, redis_data) and network

### Added

- **Network Segmentation** - Advanced Docker network architecture:
  - `frontend` (172.20.0.0/24) - User-facing services
  - `backend` (172.21.0.0/24, internal) - Processing services with no internet access
  - `monitoring` (172.22.0.0/24) - Observability stack
  - `database` (172.23.0.0/24, internal) - Database services with no internet access

### Security

- **Sentry Token** - Moved hardcoded token from Grafana datasources to environment variable
- **What's Up Docker Authentication** - Added HTTP Basic Auth (requires htpasswd setup)
  - Manual setup required: `sudo htpasswd -c config/nginx/auth/wud.htpasswd admin`
  - Critical: WUD has Docker socket access and can trigger container updates

### Changed

- Cleaned up 4 duplicate volumes (portainer_data, prometheus_data, uptime_kuma_data, whats_up_docker_data)
- Removed unused Docker networks

### Manual Actions Required

1. Generate WUD htpasswd file: `cd /home/luk-server/homelab && sudo htpasswd -c config/nginx/auth/wud.htpasswd admin`
2. Reload Nginx after htpasswd creation: `docker compose restart nginx-proxy`
3. Service network assignments pending (to be applied in next maintenance window)

### Notes

- Backup created: `backups/homelab_pre-cleanup_TIMESTAMP.tar.gz`
- Docker cleanup savings: ~2GB disk space, reduced from 50 to 14 volumes
- Network segmentation defined but service assignments deferred to prevent disruption

