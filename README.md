# 🏠 Homelab Manager

Production-grade homelab infrastructure — zero-trust networking, full observability, one-command deploys.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Available-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/Code%20Style-Black-000000.svg)](https://github.com/psf/black)

---

## 🔒 Security First

**This repository contains NO secrets or credentials.** All sensitive data is configured locally via `.env` (gitignored).

### Setup
1. Copy `.env.example` to `.env` and populate all required values
2. **Never commit `.env` to version control**

### Trust Model
- Services are **Tailscale-first by default** — bound to localhost and private network
- Public exposure is **opt-in via Cloudflare Tunnel**, restricted to selected hostnames
- All public traffic gates through **Authentik SSO** with GitHub OAuth + break-glass fallback
- DNS filtering via **Pi-hole** (LAN) and Tailscale MagicDNS (remote)

📖 Full details: [Security Policy](.github/SECURITY.md) | [Hardening Guide](docs/public-release-hardening.md) | [Network Architecture](docs/network-architecture.md)

---

## 🚀 Quick Start

```bash
# Install CLI + dependencies
pip install -e .

# Core commands
python -m homelab_manager status    # Service status & health
python -m homelab_manager deploy    # Deploy all services
python -m homelab_manager health    # Health check summary
python -m homelab_manager urls      # Print access URLs (Tailscale + public)
python -m homelab_manager --help    # Full command reference
```

### First-Time Setup
```bash
# Verify prerequisites
python -m homelab_manager system-check

# Configure secrets
cp .env.example .env
nano .env  # Fill in all REQUIRED env vars

# Deploy stack
make deploy

# Verify health
python -m homelab_manager health --verbose
```

For **auto-start on boot** after AC loss, see [BIOS Power-On Setup](docs/bios-power-on-setup.md).

---

## 🏗️ Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                             │
│                  (Cloudflare Tunnel)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────▼──────────────┐
         │  Cloudflared Container   │  (Phase-1 Public Edge)
         │  Edge Rules + Auth Gate  │  Authentik SSO → GitHub OAuth
         └───────────┬──────────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
      │        Localhost            │       Tailscale VPN
      │        (127.0.0.1)          │       (Private Mesh)
      │              │              │
  ┌───▼────────────────────────────▼──┐
  │   Docker Compose Services Stack    │
  │                                    │
  │  ┌─ Core ─────────────────────┐  │
  │  │ • Nginx Proxy (reverse)    │  │
  │  │ • Homepage Dashboard       │  │
  │  │ • Portainer (Docker UI)    │  │
  │  │ • FileBrowser (Web FS)     │  │
  │  │ • What's Up Docker (CLI)   │  │
  │  │ • MCP Gateway (Forge)      │  │
  │  └────────────────────────────┘  │
  │                                    │
  │  ┌─ Monitoring & Observability──┐ │
  │  │ • Prometheus (metrics)       │ │
  │  │ • Grafana (visualization)    │ │
  │  │ • Loki (log aggregation)     │ │
  │  │ • Promtail (log collection)  │ │
  │  │ • Alertmanager (routing)     │ │
  │  │ • Node Exporter (metrics)    │ │
  │  │ • cAdvisor (container stats) │ │
  │  │ • Blackbox Exporter (probes) │ │
  │  │ • Netdata (real-time)        │ │
  │  └────────────────────────────────┘ │
  │                                    │
  │  ┌─ Security ──────────────────┐  │
  │  │ • Pi-hole (DNS filtering)    │  │
  │  │ • Authentik (SSO/Identity)   │  │
  │  └────────────────────────────────┘ │
  │                                    │
  │  ┌─ Applications ──────────────┐  │
  │  │ • Nextcloud (cloud storage) │  │
  │  │ • Paperless-ngx (OCR docs)  │  │
  │  │ • n8n (workflows)           │  │
  │  │ • Jellyfin (media)          │  │
  │  │ • Stremio (streaming)       │  │
  │  │ • Home Assistant (automation)   │  │
  │  └────────────────────────────────┘ │
  │                                    │
  │  ┌─ Databases & Caches ────────┐  │
  │  │ • MariaDB (Nextcloud)        │  │
  │  │ • PostgreSQL (Paperless)     │  │
  │  │ • PostgreSQL (Authentik)     │  │
  │  │ • Redis (cache/broker x3)    │  │
  │  └────────────────────────────────┘ │
  │                                    │
  └────────────────────────────────────┘
         │
    ┌────▼─────┐
    │  Discord  │  (Alerts via Lucky bot)
    │Notifications  Container health, log anomalies, security events
    └──────────┘
```

---

## 📊 Service Stack

### Core Infrastructure
| Service | Port | Purpose | Access |
|---------|------|---------|--------|
| **Nginx Proxy** | 80 | Reverse proxy & routing | Localhost |
| **Homepage** | 3000 | Dashboard & service hub | Public via Tunnel + SSO |
| **Portainer** | 9000 | Docker management UI | Tailscale only |
| **FileBrowser** | 8080 | Web-based file manager | Tailscale only |
| **What's Up Docker** | 3003 | Container update monitoring | Tailscale only |
| **Forge MCP Gateway** | 4444 | MCP server (IBM Forge runtime) | Localhost only |
| **Cloudflared** | 2000 | Cloudflare Tunnel agent | Internal |

### Monitoring & Observability (Full Stack)
| Service | Port | Purpose | Access |
|---------|------|---------|--------|
| **Prometheus** | 9091 | Metrics scraper & storage | Localhost only |
| **Grafana** | 3002 | Metrics dashboard | Tailscale only |
| **Loki** | 3100 | Log aggregation | Localhost only |
| **Promtail** | — | Log collector agent | Internal |
| **Alertmanager** | 9093 | Alert routing & grouping | Localhost only |
| **Node Exporter** | 9100 | System metrics | Localhost only |
| **cAdvisor** | 8082 | Container metrics | Localhost only |
| **Blackbox Exporter** | 9115 | HTTP/endpoint probes | Localhost only |
| **Netdata** | 19999 | Real-time monitoring | Public/Tailscale |

### Security & Authentication
| Service | Port | Purpose | Access |
|---------|------|---------|--------|
| **Pi-hole** | 8054 | DNS filtering & ad-blocking | Localhost + LAN |
| **Authentik** | 9100 | SSO & identity provider | Public via Tunnel |

### Applications
| Service | Port | Purpose | Access |
|---------|------|---------|--------|
| **Nextcloud** | 8300 | Cloud storage & NAS | Public via Tunnel + SSO |
| **Paperless-ngx** | 8400 | Document mgmt & OCR | Tailscale only |
| **n8n** | 5678 | Workflow automation | Tailscale only |
| **Jellyfin** | 8096 | Media streaming | Public/Tailscale |
| **Stremio** | 11470 | Add-on streaming | Public/Tailscale |
| **Home Assistant** | 8123 | Home automation | Tailscale only |

### Support Services (Databases & Caches)
- **MariaDB** (Nextcloud) — internal
- **PostgreSQL** (Paperless-ngx) — internal
- **PostgreSQL** (Authentik) — internal
- **Redis** (Nextcloud, Paperless-ngx, Authentik caches) — internal

---

## 🔐 Security Model

### Network Layers
1. **Layer 1 — Localhost Binding** (Default)
   - Services listen on `127.0.0.1` only
   - Accessible only within the host
   - Zero external attack surface

2. **Layer 2 — Tailscale VPN** (Private)
   - Services bridged over Tailscale mesh
   - Access from remote devices via VPN
   - Encrypted point-to-point tunnels
   - MagicDNS for service discovery

3. **Layer 3 — Cloudflare Tunnel** (Selected Services)
   - Public domains routed through Cloudflare's edge
   - Not a traditional reverse proxy — eliminates port forwarding
   - DDoS protection, WAF, and rate limiting at Cloudflare
   - **Homepage, Authentik, Nextcloud, Jellyfin** (configurable)

### Authentication & Authorization
- **Public services** gate through **Authentik SSO**
- Primary auth: **GitHub OAuth** (company/team gating)
- Fallback: Local username/password (break-glass)
- Session timeout & MFA configurable per service

### DNS & IP Management
- **Pi-hole** blocks malware/tracking domains (internal DNS)
- **Tailscale MagicDNS** provides `https://service.your-domain` naming
- Static IPs assigned via Docker networks
- No dynamic DNS, no leaked IPs to WHOIS

### Secrets Management
- `.env` file (git-ignored) — local only
- No hardcoded credentials in images
- Database passwords rotated via `Makefile` targets
- Audit trail via [SOPS](https://github.com/mozilla/sops) (encrypted secrets file support)

📖 Details: [Authentik SSO Setup](docs/tinyauth-sso-setup.md) | [Cloudflare Tunnel](docs/cloudflare-tunnel-phase1.md) | [Network Architecture](docs/network-architecture.md)

---

## 🔔 Discord Notifications

Container and service events trigger alerts to Discord via the **Lucky bot**:

### Monitored Events
| Event | Trigger | Route |
|-------|---------|-------|
| **Container Health** | Container fails or restarts | Alertmanager → Lucky → #homelab |
| **Update Available** | Docker image update detected | What's Up Docker → Lucky → #homelab |
| **Deploy Status** | Service deploy succeeds/fails | CLI → Lucky → #homelab |
| **Log Anomalies** | Errors in container logs | Loki rules → Alertmanager → Lucky |
| **Security Events** | Failed auth, SSH attempts (if enabled) | Pi-hole/Authentik → Lucky → #homelab |

### Configuration
Set in `.env`:
```bash
LUCKY_NOTIFY_URL=http://localhost:8090/api/internal/notify
LUCKY_NOTIFY_KEY=<shared-secret-from-lucky-.env>
LUCKY_NOTIFY_CHANNEL_ID=<discord-channel-id>
```

Test the connection:
```bash
curl -X POST "$LUCKY_NOTIFY_URL" \
  -H "X-Notify-Key: $LUCKY_NOTIFY_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"channelId\":\"$LUCKY_NOTIFY_CHANNEL_ID\",\"content\":\"test from homelab\"}"
```

Expect HTTP `204`.

---

## 🏗️ Project Structure

```
homelab/
├── compose/               # Modular Docker Compose manifests
│   ├── core.yml          # Nginx, Homepage, Portainer, Cloudflared
│   ├── monitoring.yml    # Prometheus, Grafana, Loki, Alertmanager
│   ├── apps.yml          # Nextcloud, Paperless, n8n
│   ├── media.yml         # Jellyfin, Stremio
│   ├── security.yml      # Pi-hole, Authentik
│   └── automation.yml    # Home Assistant
│
├── homelab_manager/       # Python CLI (main entry point)
│   ├── cli/              # Commands (status, deploy, health, urls)
│   ├── core/             # Business logic (deploy, health checks)
│   ├── services/         # Service definitions & adapters
│   ├── models/           # Data models (Config, Service, Status)
│   ├── data/
│   │   └── services.yaml # Service registry (single source of truth)
│   └── utils/            # Helpers (retry, logging, parsing)
│
├── config/                # Service configurations
│   ├── nginx/            # Nginx reverse proxy rules
│   ├── prometheus/       # Prometheus scrape configs
│   ├── alertmanager/     # Alert rules & routing
│   ├── loki/             # Loki ingestion rules
│   └── [service]/        # Per-service configs
│
├── scripts/               # Utility scripts
│   ├── deployment/       # Rolling updates, backups
│   ├── maintenance/      # Cleanup, optimization
│   ├── monitoring/       # Health checks, metrics
│   └── security/         # Certificate renewal, audit
│
├── infra/terraform/       # IaC for DNS, Tunnel, network
│   ├── cloudflare/       # Cloudflare Tunnel config
│   └── tailscale/        # Tailscale ACLs (if managed)
│
├── docs/                  # Documentation
│   ├── adr/              # Architecture Decision Records
│   ├── specs/            # Feature specs
│   ├── network-architecture.md
│   ├── cloudflare-tunnel-phase1.md
│   ├── authentik-sso-setup.md
│   ├── bios-power-on-setup.md
│   └── [more...]
│
├── .env.example           # Template (commit this)
├── .env                   # Secrets (git-ignored)
├── docker-compose.yml     # Top-level compose (includes all)
├── Makefile              # High-level tasks (deploy, update, health)
├── pyproject.toml        # Python package config
└── LICENSE               # MIT
```

---

## 🛠️ Development & Operations

### Install (Dev)
```bash
pip install -e ".[dev]"  # Editable install + dev deps
```

### Quality Checks
```bash
pytest                    # Run tests
black homelab_manager/    # Format code
flake8 homelab_manager/   # Lint
mypy homelab_manager/     # Type checking
```

### Common Operations
```bash
make deploy              # Full stack deploy
make update-safe         # Rolling update with health checks
make update-dry-run      # Preview updates (no apply)
make health              # Service health summary
make logs                # Tail container logs
make power-restore-check # Validate post-power-loss recovery
make sso-status          # Check Authentik edge runtime
make ssl-renew           # Renew wildcard TLS cert
```

### Add a New Service
1. Create compose file or add to existing: `compose/category.yml`
2. Register in service registry: `homelab_manager/data/services.yaml`
3. Add Nginx rules if exposed: `config/nginx/homelab.conf`
4. Add Prometheus scrape config (if metrics): `config/prometheus/prometheus.yml`
5. Run: `python -m homelab_manager deploy`

---

## 📚 Documentation & References

| Document | Purpose |
|----------|---------|
| [Network Architecture](docs/network-architecture.md) | Trust model, network layers, IP scheme |
| [Cloudflare Tunnel Phase 1](docs/cloudflare-tunnel-phase1.md) | Public edge routing & domain setup |
| [Authentik SSO Setup](docs/authentik-sso-setup.md) | OAuth, GitHub integration, break-glass |
| [BIOS Power-On Setup](docs/bios-power-on-setup.md) | AC-loss recovery, auto-start config |
| [DNS Setup](docs/dns-setup.md) | Tailscale MagicDNS, Pi-hole, DoH |
| [Architecture Decision Records](docs/adr/) | Design choices & rationale |
| [Feature Specs](docs/specs/) | Upcoming features & phases |
| [Runbooks](docs/runbooks/) | Operational procedures |
| [Security Policy](.github/SECURITY.md) | Vulnerability disclosure |
| [Public Release Hardening](docs/public-release-hardening.md) | Secrets hygiene checklist |

---

## 🔄 Status & Health

Check service health:
```bash
python -m homelab_manager health          # Summary
python -m homelab_manager health --verbose # Per-service details
```

Check system state:
```bash
python -m homelab_manager status          # Container status
python -m homelab_manager urls            # Access URLs
```

View logs:
```bash
docker compose logs -f [service]          # Container logs
docker compose exec [service] sh           # Container shell
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file for details.

---

## 🎯 What's Next

- **Monitor & Iterate**: Use Grafana dashboards to understand resource usage
- **Set Alerts**: Configure Alertmanager rules for your use case
- **Backup Strategy**: Configure automated backups (docs/backup.md)
- **Scale Up**: Add services as needed; modular compose files support growth
- **Secure Further**: Review [Security Policy](.github/SECURITY.md) and audit logs quarterly

Questions? Check the [docs](docs/), [ADRs](docs/adr/), or open an issue.
