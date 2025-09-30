# 🏠 Luk's Homelab

A modern, Python-based homelab automation system that provides enterprise-grade features without the complexity.

## 🚀 Quick Start

```bash
# Deploy your homelab
./homelab deploy

# Check status
./homelab status

# Setup automation
./homelab setup

# Check for updates
./homelab update-check
```

## 📋 Available Commands

### 🚀 Deployment
- `./homelab deploy` - Deploy homelab services
- `./homelab down` - Stop homelab services
- `./homelab restart` - Restart homelab services

### 🔄 Updates
- `./homelab update` - Update all services
- `./homelab update-check` - Check for available updates
- `./homelab update-all` - Update all services
- `./homelab versions` - Show current versions

### 💾 Backup
- `./homelab backup` - Create backup
- `./homelab restore <path>` - Restore from backup

### 📊 Monitoring
- `./homelab status` - Quick status check
- `./homelab check` - Full health check
- `./homelab monitor` - Continuous monitoring
- `./homelab logs <service>` - Show service logs

### 🧹 Maintenance
- `./homelab cleanup` - Clean up unused resources
- `./homelab setup` - Setup automated tasks
- `./homelab validate` - Validate configuration
- `./homelab config` - Show configuration summary

## 🏗️ Architecture

### Core Components
- **Docker Compose** - Container orchestration
- **Python Automation** - Modern automation system
- **Environment Variables** - Secure configuration management
- **Rich CLI** - Beautiful command-line interface

### Services

#### 🏠 **Dashboard & Management**
- **Homepage** (3000) - Main dashboard and service overview
- **Portainer** (9000) - Docker container management interface
- **Uptime Kuma** (3001) - Service uptime monitoring and alerts
- **What's Up Docker** (3003) - Container update monitoring and notifications

#### 🏡 **Home Automation**
- **Home Assistant** (8123) - Smart home automation hub

#### 📊 **Monitoring Stack**
- **Grafana** (3002) - Metrics visualization and dashboards
- **Prometheus** (9091) - Metrics collection and storage
- **Node Exporter** (9100) - System metrics collection

#### 🌐 **Network Services**
- **Pi-hole** (5354/8054) - Network-wide ad blocking and DNS
- **Stremio** (11470/12470) - Media streaming server
- **Cloudflare Tunnel** - Secure external access

## 🔧 Configuration

### Environment Variables
All configuration is managed through the `.env` file:

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env
```

### Required Variables
- `DOMAIN` - Your domain name
- `TIMEZONE` - Your timezone
- `PUID/PGID` - User/group IDs
- `TAILSCALE_IP` - Your Tailscale IP
- `CF_API_TOKEN` - Cloudflare API token
- `CF_TUNNEL_ID` - Cloudflare tunnel ID
- `PIHOLE_WEB_PASSWORD` - Pi-hole password
- `GRAFANA_PASSWORD` - Grafana password
- `HOMEASSISTANT_KEY` - Home Assistant API key

### Additional Variables
- `LUKBOT_SENTRY_DSN` - Sentry DSN for error tracking
- `LUKBOT_SENTRY_ORG_SLUG` - Sentry organization slug
- `LUKBOT_SENTRY_PROJECT_SLUG` - Sentry project slug
- `LUKBOT_SENTRY_AUTH_TOKEN` - Sentry authentication token
- `WUD_DISCORD_WEBHOOK_URL` - Discord webhook for update notifications
- `WUD_SMTP_PASS` - SMTP password for email notifications

## 🐍 Python Automation System

### Features
- **Rich CLI Interface** - Beautiful, colored output
- **Health Monitoring** - Comprehensive service health checks
- **Update Management** - Automated update checking and deployment
- **Backup System** - Automated backups with retention
- **Configuration Validation** - Environment variable validation
- **Cron Integration** - Automated task scheduling

### Structure
```
scripts/homelab_manager/
├── cli.py              # Main CLI interface
├── automation.py       # Deploy/update/backup automation
├── health.py          # Health monitoring
├── updates.py         # Update management
├── config.py          # Configuration management
└── container_manager.py # Container management
```

## 🔄 Automated Tasks

The system can be configured to run automated tasks:

```bash
# Setup automated tasks
./homelab setup
```

This creates cron jobs for:
- **Daily backup at 2 AM**
- **Weekly update check on Sunday at 3 AM**
- **Daily cleanup at 4 AM**
- **Daily update check at 5 AM**

## 📊 Monitoring

### Health Checks
- Service availability (HTTP endpoints)
- System resources (CPU, memory, disk)
- Docker container status
- Network connectivity

### Monitoring Tools
- **Grafana** - Dashboards and visualization
- **Prometheus** - Metrics collection
- **Uptime Kuma** - Service uptime monitoring
- **What's Up Docker** - Container update monitoring

## 💾 Backup System

### Automated Backups
- **Docker volumes** - Application data
- **Configuration files** - Docker Compose and environment
- **Application data** - Home Assistant, Grafana configs
- **Retention policy** - Keeps last 7 days of backups

### Manual Backups
```bash
# Create backup
./homelab backup

# Restore from backup
./homelab restore /path/to/backup
```

## 🔒 Security

### Environment Variables
- All sensitive data stored in `.env` file
- `.env` file excluded from version control
- Environment variable validation with security checks
- Secure configuration templates with placeholders
- Password strength validation
- Token format validation

### Docker Security
- Non-root user execution
- Read-only containers where possible
- Network isolation
- Resource limits
- Secure subprocess execution (no `os.system()`)

### Security Features
- **Zero hardcoded secrets** - All sensitive data externalized
- **Environment validation** - Comprehensive validation with security checks
- **Secure subprocess handling** - Uses `subprocess.run()` instead of `os.system()`
- **Password strength checks** - Validates password complexity
- **Token format validation** - Ensures proper token formats

## 🚀 Benefits

### Why Python Over Shell?
- **Better Error Handling** - Comprehensive exception handling
- **Rich Output** - Beautiful, colored CLI interface
- **Type Safety** - Better code reliability
- **Maintainability** - Easier to modify and extend
- **Testing** - Unit testing capabilities
- **Documentation** - Self-documenting code

### Why This Over Terraform/Ansible?
- **Homelab-Focused** - Built specifically for homelab use
- **Simple** - No complex infrastructure concepts
- **Fast** - Quick deployment and updates
- **Maintainable** - Easy to understand and modify
- **Appropriate Scale** - Perfect for single-server homelab

## 📁 Project Structure

```
homelab/
├── docker-compose.yml          # Core infrastructure
├── .env                        # Environment variables
├── .env.example               # Template
├── .gitignore                 # Security
├── homelab                    # Main entry point
├── scripts/
│   ├── homelab_manager/       # Python automation system
│   ├── containers             # Simple wrapper
│   ├── container-status.py    # Container status
│   ├── update-containers.py   # Container updates
│   └── requirements.txt       # Python dependencies
├── appdata/                   # Application data
├── homepage/                  # Homepage config
├── grafana/                   # Grafana data
└── venv/                      # Python environment
```

## 🎯 Perfect for Homelab Because:

1. **Simple Commands** - One script for everything
2. **No Learning Curve** - Just Python and Docker
3. **Automated Tasks** - Set and forget
4. **Health Monitoring** - Know if something breaks
5. **Easy Backups** - Never lose your data
6. **Update Management** - Keep services current
7. **Troubleshooting** - Easy log viewing
8. **Maintainable** - Easy to modify and extend

## 🏠 This is Your Homelab, Simplified!

You now have **enterprise-grade automation** with **homelab simplicity**! 🎉

The system gives you all the benefits of automation (backups, updates, monitoring) without the complexity of enterprise tools. Perfect for a homelab! 🚀
