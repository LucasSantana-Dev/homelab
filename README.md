# 🏠 Homelab Manager

Modern Python CLI for homelab management with Docker, Tailscale, and Cloudflare integration.

## 🔒 Security Notice

**This repository contains NO secrets or credentials.** All sensitive information is configured locally via a `.env` file (gitignored).

1. Copy `.env.example` to `.env` and fill in all required values
2. **Never commit `.env` to version control**

Services are **Tailscale-first by default**. Public exposure is opt-in via Cloudflare Tunnel, restricted to selected hostnames behind SSO. See [Security Policy](.github/SECURITY.md) and [public-release-hardening.md](docs/public-release-hardening.md).

## 🚀 Quick Start

```bash
# Install
pip install -e .

# Core commands
python -m homelab_manager status    # Show status
python -m homelab_manager deploy    # Deploy services
python -m homelab_manager health    # Check health
python -m homelab_manager urls      # Show access URLs
python -m homelab_manager --help    # All commands
```

For auto-start on boot, see `docs/bios-power-on-setup.md`.

## 🏗️ Architecture

```
homelab/
├── compose/          # Modular Docker Compose files (base, core, monitoring, media, apps, security, automation)
├── homelab_manager/  # Python CLI package (cli/, core/, services/, models/, data/, utils/)
├── scripts/          # Utility scripts (deployment/, maintenance/, monitoring/, security/)
├── config/           # Service configurations
├── infra/terraform/  # DNS/tunnel/network IaC
├── docs/             # ADRs, specs, runbooks
└── docker-compose.yml
```

## 🌐 Services

| Category | Service | Port |
|----------|---------|------|
| Core | Homepage | 3000 |
| Core | Caddy (LAN) | — |
| Core | Cloudflared | — |
| Core | Portainer | 9000 |
| Core | Forge MCP Gateway | 4444 |
| Monitoring | Grafana | 3002 |
| Monitoring | Prometheus | 9091 |
| Monitoring | Netdata | 19999 |
| Monitoring | Alertmanager | 9093 |
| Monitoring | Loki | 3100 |
| Monitoring | Gatus | 8095 |
| Monitoring | Healthchecks | 8092 |
| Security | Pi-hole (DNS) | 8054 |
| Security | Tinyauth (SSO) | — |
| Security | CrowdSec | — |
| Automation | Home Assistant | 8123 |
| Automation | n8n | 5678 |
| Apps | Nextcloud | 8300 |
| Apps | Paperless-ngx | 8400 |
| Apps | Miniflux | — |
| Apps | Linkding | — |
| Apps | Forgejo | — |
| Media | Stremio | 11470 |

See [ADR 0005](docs/adr/0005-media-stack-stremio-realdebrid.md) for media stack decisions.

## 🔑 Access Methods

1. **Localhost**: `http://localhost:PORT`
2. **Tailscale**: `http://TAILSCALE_IP:PORT` or `https://service.DOMAIN` (with DNS)
3. **Public (selected only)**: `https://service.DOMAIN` via Cloudflare Tunnel + Tinyauth SSO

DNS setup: see `docs/dns-setup.md`. Tailscale MagicDNS is recommended.

## 🛠️ Development

```bash
pip install -e ".[dev]"   # Install with dev deps
pytest                     # Run tests
black homelab_manager/     # Format
flake8 homelab_manager/    # Lint
mypy homelab_manager/      # Type check
```

To add a service: add it to `compose/*.yml`, register in `homelab_manager/data/services.yaml`, update `config/caddy/` if exposed, then `docker compose up -d`.

## 📋 Key Makefile Targets

| Target | Purpose |
|--------|---------|
| `make update-safe` | Rolling update with health checks |
| `make update-dry-run` | Preview updates without applying |
| `make power-restore-check` | Validate post-boot AC-loss readiness |
| `make sso-status` | Validate SSO edge runtime |
| `make ssl-renew` | Renew wildcard TLS cert (Cloudflare DNS-01) |
| `make host-stabilize-prep` | Recovery point before host maintenance |

## 🔒 Security Model

- Services bound to localhost and Tailscale by default
- Selected domains exposed via Cloudflare Tunnel only
- Tinyauth forward-auth gates admin/public services
- GitHub OAuth allowlist + local break-glass fallback
- See [docs/tinyauth-sso-setup.md](docs/tinyauth-sso-setup.md) and [docs/cloudflare-tunnel-phase1.md](docs/cloudflare-tunnel-phase1.md)

## 📚 Documentation

- `docs/adr/` — Architecture Decision Records
- `docs/specs/` — Feature specs
- `docs/dns-setup.md` — DNS configuration
- `docs/bios-power-on-setup.md` — Auto-start / AC-loss setup
- `docs/tinyauth-sso-setup.md` — SSO setup
- `docs/cloudflare-tunnel-phase1.md` — Public exposure model
- `docs/public-release-hardening.md` — Secrets hygiene
- `scripts/README.md` — Script documentation
- `.env.example` — All environment variables

## 📄 License

MIT License — see LICENSE file for details.
