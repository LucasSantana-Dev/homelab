# 🏠 Homelab Manager

Modern Python CLI for homelab management with Docker, Tailscale, and Cloudflare integration.

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

- **Homepage** - Dashboard (port 3000)
- **Stremio** - Media streaming (port 8080)
- **Home Assistant** - Home automation (port 8123)
- **Portainer** - Container management (port 9000)
- **Pi-hole** - DNS filtering (port 8054)
- **Grafana** - Monitoring (port 3002)
- **Uptime Kuma** - Uptime monitoring (port 3001)
- **What's Up Docker** - Container monitoring (port 3003)

## 🔧 Configuration

### Environment Variables

Create a `.env` file with your configuration:

```bash
# Network Configuration
TAILSCALE_IP=100.64.0.10
TIMEZONE=America/Sao_Paulo

# User Configuration
PUID=1000
PGID=1000

# Domain Configuration
DOMAIN=your-domain.com

# Cloudflare Configuration (Optional)
CF_API_TOKEN=your_cloudflare_api_token_here
CF_TUNNEL_ID=your_tunnel_id_here

# Service Passwords
PIHOLE_WEB_PASSWORD=your_pihole_password_here
GRAFANA_PASSWORD=your_grafana_password_here
```

### Access Methods

1. **Localhost**: `http://localhost:PORT`
2. **Tailscale**: `http://TAILSCALE_IP:PORT`
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
