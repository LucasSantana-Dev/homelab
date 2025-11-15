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

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
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
- `update` - Update homelab services
- `health` - Check homelab health
- `backup` - Create homelab backup
- `restore <backup-path>` - Restore from backup
- `logs [service]` - Show service logs
- `config` - Show configuration information
- `urls` - Show service URLs and access methods
- `restart [service]` - Restart services

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
├── homelab_manager/          # Python CLI package
│   ├── __init__.py
│   ├── cli.py               # Main CLI interface
│   ├── config.py            # Configuration management
│   ├── container_manager.py # Container operations
│   ├── health.py            # Health monitoring
│   └── updates.py           # Update management
├── scripts/                 # Utility scripts
│   └── homelab             # CLI wrapper
├── config/                  # Service configurations
├── appdata/                 # Service data
├── docker-compose.yml       # Main compose file
├── .env                     # Environment variables
└── requirements.txt         # Python dependencies
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
pip install -r requirements.txt

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

1. Add service to `docker-compose.yml`
2. Update service configuration in `container_manager.py`
3. Add health check URL in `health.py`
4. Update service list in CLI commands

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

## 🔒 Security

- **Network Isolation**: Services bound to localhost and Tailscale
- **Authentication**: Service-specific authentication
- **TLS/SSL**: HTTPS with self-signed certificates
- **Access Control**: Tailscale-only access by default

## 📚 Documentation

- **CLI Help**: `python -m homelab_manager --help`
- **Command Help**: `python -m homelab_manager <command> --help`
- **Configuration**: Check `.env.example` for all options

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
