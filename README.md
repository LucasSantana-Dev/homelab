# 🏠 Homelab Manager

Modern Python CLI for homelab management with Docker, Tailscale, and Cloudflare integration.

## 🔒 Security Notice

**This repository contains NO secrets or credentials.** All sensitive information must be configured locally using a `.env` file (which is gitignored).

### Before Deploying:
1. Copy `.env.example` to `.env`
2. Fill in all required credentials and tokens
3. **Never commit `.env` to version control**

All services are accessible **only via Tailscale network** (100.0.0.0/8) - no public internet exposure by default.

See `.env.example` for all required variables and refer to our [Security Policy](.github/SECURITY.md) for reporting vulnerabilities.

## ✨ Features

- **Modern CLI**: Clean, intuitive command-line interface with rich output
- **Service Management**: Deploy, update, restart, and monitor homelab services
- **Health Monitoring**: Real-time health checks and status monitoring
- **Backup & Restore**: Automated backup and restore functionality
- **Configuration Management**: Environment variable validation and management
- **Multi-Access**: Localhost, Tailscale, and Cloudflare tunnel support

## 🚀 Quick Start

### Auto-Start Configuration

To enable automatic startup of all services on boot:

1. **Install systemd services:**
   ```bash
   cd /home/luk-server/homelab
   sudo ./scripts/deployment/install-systemd-services.sh
   ```

2. **Configure BIOS for power-on after AC loss:**
   - See `docs/bios-power-on-setup.md` for detailed instructions
   - Enable "Power On After AC Loss" in BIOS/UEFI settings
   - This ensures the server automatically boots when power is restored

3. **Verify services are enabled:**
   ```bash
   ./scripts/monitoring/status-services.sh
   ```

### Installation

```bash
# Install in production mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Show homelab status
python -m homelab_manager status

# Deploy homelab services
python -m homelab_manager deploy

# Check service health
python -m homelab_manager health

# Show service URLs
python -m homelab_manager urls

# Get help
python -m homelab_manager --help
```

### Using the Wrapper Script

```bash
# Use the wrapper script for backward compatibility
./scripts/homelab status
./scripts/homelab deploy
./scripts/homelab health
```

## 📋 Commands

### Core Commands

- `status` - Show homelab status and service information
- `deploy` - Deploy homelab services
- `update` - Update homelab services (fast mode)
- `update-safe` - Safe rolling update with health checks
- `health` - Check homelab health
- `backup` - Create homelab backup
- `restore <backup-path>` - Restore from backup
- `logs [service]` - Show service logs
- `config` - Show configuration information
- `urls` - Show service URLs and access methods
- `restart [service]` - Restart services

### Update Commands (Makefile)

- `make update` - Fast update (pull all images, restart all containers)
- `make update-safe` - Safe rolling update with health checks between restarts
- `make update-dry-run` - Preview what would be updated without making changes
- `make update-timer-install` - Install and enable the automatic update timer
- `make update-timer-status` - Show status of the update timer
- `make update-timer-enable` - Enable the automatic update timer
- `make update-timer-disable` - Disable the automatic update timer
- `make update-timer-run-now` - Manually trigger an update immediately
- `make update-logs` - Show recent container update logs

### Examples

```bash
# Deploy all services
python -m homelab_manager deploy

# Update all services
python -m homelab_manager update

# Check health of all services
python -m homelab_manager health

# Create backup
python -m homelab_manager backup

# Restore from backup
python -m homelab_manager restore backups/homelab_backup_20241201_120000.tar.gz

# Get logs for specific service
python -m homelab_manager logs stremio

# Restart specific service
python -m homelab_manager restart stremio

# Show all service URLs
python -m homelab_manager urls
```

## 🏗️ Architecture

### Project Structure

```
homelab/
├── compose/                      # Modular Docker Compose files
│   ├── base.yml                 # Networks and volumes
│   ├── core.yml                 # Nginx, Homepage, Portainer, etc.
│   ├── monitoring.yml           # Prometheus, Grafana, Loki, etc.
│   ├── media.yml                # Jellyfin, Stremio
│   ├── apps.yml                 # n8n, Paperless, Nextcloud
│   ├── security.yml             # Authentik, Vaultwarden, Pi-hole
│   └── automation.yml           # Home Assistant
├── homelab_manager/              # Python CLI package
│   ├── cli/                     # CLI commands
│   ├── core/                    # Configuration management
│   ├── services/                # Container and health services
│   ├── models/                  # Data models
│   │   └── service.py          # Service dataclass
│   ├── data/                    # Static data files
│   │   └── services.yaml       # Service registry
│   └── utils/                   # Utility functions
├── scripts/                      # Utility scripts (organized)
│   ├── homelab                  # Main CLI wrapper
│   ├── containers               # Container management wrapper
│   ├── deployment/              # Service lifecycle scripts
│   ├── maintenance/             # Backup and update scripts
│   ├── monitoring/              # Status and health scripts
│   ├── security/                # Security scanning
│   └── systemd/                 # Systemd service files
├── config/                       # Service configurations
├── appdata/                      # Service data (volumes)
├── docker-compose.yml            # Main orchestrator (includes modules)
├── pyproject.toml                # Python project config (single source)
└── .env                          # Environment variables
```

### Services

#### Core Infrastructure
- **Homepage** - Dashboard (port 3000)
- **Portainer** - Container management (port 9000)
- **Uptime Kuma** - Uptime monitoring (port 3001)
- **What's Up Docker** - Container monitoring (port 3003)

#### Media & Entertainment
- **Stremio** - Media streaming (port 8080)
- **Jellyfin** - Media server (port 8096) - https://jellyfin.homelab.example.com

#### Home Automation
- **Home Assistant** - Home automation (port 8123)

#### Networking & Security
- **Pi-hole** - DNS filtering (port 8054)
- **Vaultwarden** - Password manager (port 8200) - https://vault.homelab.example.com

#### Security & Identity
- **Authentik** - SSO & Identity Provider (ports 9100, 9443) - https://auth.homelab.example.com

#### Monitoring & Observability
- **Grafana** - Metrics visualization (port 3002)
- **Prometheus** - Metrics collection (port 9091)
- **Netdata** - Real-time monitoring (port 19999)
- **Alertmanager** - Alert routing (port 9093) - https://alertmanager.homelab.example.com
- **Loki** - Log aggregation (port 3100)

#### Automation
- **n8n** - Workflow automation (port 5678) - https://n8n.homelab.example.com

#### Document Management
- **Paperless-ngx** - Document Management & OCR (port 8400) - https://docs.homelab.example.com

#### Cloud Storage
- **Nextcloud** - Cloud Storage & File Sharing (port 8300) - https://cloud.homelab.example.com

## 🔧 Configuration

### Auto-Start Services

The homelab is configured to automatically start all services on boot using systemd:

- **homelab-docker.service** - Main homelab stack (nginx, grafana, prometheus, etc.)
- **satisfactory-server.service** - Satisfactory game server with Cloudflared tunnel
- **lukbot.service** - LukBot Discord bot

**Service Management:**
```bash
# Check service status
./scripts/monitoring/status-services.sh

# Manually start all services
./scripts/deployment/startup-services.sh

# Gracefully shutdown all services
./scripts/deployment/shutdown-services.sh

# View service logs
sudo journalctl -u homelab-docker -n 50
sudo journalctl -u satisfactory-server -n 50
sudo journalctl -u lukbot -n 50
```

**Boot Sequence:**
1. BIOS auto power-on (if configured)
2. Ubuntu system boot
3. Docker service starts
4. Tailscale daemon starts
5. Network becomes available
6. Homelab services start (10s delay)
7. Satisfactory server starts (5s delay after homelab)
8. LukBot starts (5s delay after homelab)

### Environment Variables

Create a `.env` file with your configuration:

```bash
# Network Configuration
TAILSCALE_IP=YOUR_TAILSCALE_IP_HERE
TIMEZONE=America/Sao_Paulo

# User Configuration
PUID=1000
PGID=1000

# Domain Configuration
DOMAIN=your-domain.com

# Cloudflare Configuration (Optional)
CF_API_TOKEN=your_cloudflare_api_token_here
CF_TUNNEL_ID=your_tunnel_id_here

# Service Passwords & Tokens
PIHOLE_WEB_PASSWORD=your_pihole_password_here
GRAFANA_PASSWORD=your_grafana_password_here
HOMEASSISTANT_KEY=your_homeassistant_key_here
VAULTWARDEN_ADMIN_TOKEN=your_vaultwarden_admin_token_here
N8N_USER=admin
N8N_PASSWORD=your_n8n_password_here

# Authentik SSO Configuration
AUTHENTIK_SECRET_KEY=<openssl rand -base64 50>
AUTHENTIK_DB_PASSWORD=<secure password>

# Paperless-ngx Document Management
PAPERLESS_SECRET_KEY=<openssl rand -base64 50>
PAPERLESS_DB_PASSWORD=<secure password>
PAPERLESS_ADMIN_PASSWORD=<secure password>

# Nextcloud Cloud Storage
NEXTCLOUD_DB_ROOT_PASSWORD=<secure password>
NEXTCLOUD_DB_PASSWORD=<secure password>
```

### DNS Configuration

All services use custom domains (e.g., `auth.homelab.example.com`, `grafana.homelab.example.com`) that need DNS resolution. You have three options:

**Option 1: Tailscale MagicDNS (Recommended)**
- Configure wildcard DNS in Tailscale admin console
- Works across all devices on your Tailscale network automatically
- Most reliable for multi-device access
- See `docs/dns-setup.md` for detailed instructions

**Option 2: Local /etc/hosts File (Testing)**
- Quick setup for testing from a single machine
- Add entries mapping domains to your Tailscale IP
- Must be configured on each device
- See `docs/dns-setup.md` for all domain entries

**Option 3: DuckDNS (Not Recommended)**
- External DNS service (token already in `.env`)
- NOT recommended for Tailscale-only setup
- Would expose services to public internet

**Quick Start with /etc/hosts:**
```bash
# Add this line to /etc/hosts (Linux/Mac) or C:\Windows\System32\drivers\etc\hosts (Windows)
<YOUR_TAILSCALE_IP> auth.homelab.example.com

# Replace <YOUR_TAILSCALE_IP> with the value from your .env file
```

For complete DNS setup including all services, see `docs/dns-setup.md`.

### Access Methods

1. **Localhost**: `http://localhost:PORT`
2. **Tailscale**: `http://TAILSCALE_IP:PORT` or `https://service.DOMAIN` (with DNS configured)
3. **Public**: `https://service.DOMAIN` (with Cloudflare tunnel)

## 🛠️ Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black homelab_manager/

# Lint code
flake8 homelab_manager/

# Type checking
mypy homelab_manager/
```

### Adding New Services

1. Add service to the appropriate `compose/*.yml` module
2. Add service definition to `homelab_manager/data/services.yaml`
3. Update nginx configuration if needed
4. Restart services: `docker compose up -d`

## 📊 Monitoring

### Health Checks

The CLI provides comprehensive health monitoring:

- **Service Status**: Running/stopped status
- **Response Time**: HTTP response times
- **Health Status**: Container health status
- **Last Check**: Timestamp of last health check

### Backup & Restore

- **Automated Backups**: Create timestamped backups
- **Data Protection**: Backup all service data
- **Easy Restore**: Restore from any backup point

### Automated Container Updates

The homelab includes an automated container update system that runs every 5 days:

**Features:**
- **Safe Rolling Updates**: Updates containers in priority groups with health checks
- **Update Order**: Databases → Core Services → Applications → Monitoring → Utilities
- **Health Checks**: Waits for container health between updates
- **Pre-Update Backup**: Creates backup of critical configs before updating
- **Discord Notifications**: Sends update status to Discord webhook
- **Lock File**: Prevents concurrent update runs

**Container Update Groups:**
| Group | Wait Time | Containers |
|-------|-----------|------------|
| Databases | 30s | nextcloud-db, authentik-db, paperless-db, *-redis |
| Core | 20s | nginx, homepage, homeassistant, vaultwarden |
| Applications | 20s | jellyfin, stremio, n8n, nextcloud, paperless-ngx |
| Monitoring | 15s | prometheus, grafana, loki, alertmanager, netdata |
| Utilities | 10s | portainer, uptime-kuma, whats-up-docker, pihole |

**Setup Automated Updates:**
```bash
# Install the systemd timer (runs every 5 days at 3 AM)
make update-timer-install

# Check timer status
make update-timer-status

# Run a manual safe update
make update-safe

# Preview what would be updated
make update-dry-run

# View update logs
make update-logs
```

**Configuration:**
Set `WUD_DISCORD_WEBHOOK_URL` in `.env` to receive Discord notifications about updates.

## 🔒 Security

- **Network Isolation**: Services bound to localhost and Tailscale
- **Authentication**: Service-specific authentication
- **TLS/SSL**: HTTPS with self-signed certificates
- **Access Control**: Tailscale-only access by default

## 📚 Documentation

- **CLI Help**: `python -m homelab_manager --help`
- **Command Help**: `python -m homelab_manager <command> --help`
- **Configuration**: Check `.env.example` for all options
- **Auto-Start Setup**: See `docs/bios-power-on-setup.md` for BIOS configuration
- **Service Management**: Scripts in `scripts/deployment/`, `scripts/monitoring/`
- **Scripts README**: See `scripts/README.md` for script documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: Create an issue on GitHub
- **Documentation**: Check the docs/ directory
- **CLI Help**: Use `--help` for command documentation

---

**Happy Homelabbing! 🏠✨**
