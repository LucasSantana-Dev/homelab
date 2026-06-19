# Compose / Dockerfile Audit

> **Historical snapshot (2026-04-14)** — This is part of the homelab audit series. Some services listed here have since been retired (e.g., authentik, vaultwarden, nginx, netdata, uptime-kuma). Refer to the audit README for current status and follow-up PRs.

## Services using :latest or no pin
compose/apps.yml:7:    image: ${IMG_N8N:-n8nio/n8n:latest}
compose/apps.yml:46:    image: ${IMG_MARIADB:-mariadb:latest}
compose/apps.yml:110:    image: ${IMG_NEXTCLOUD:-nextcloud:latest}
compose/core.yml:50:    image: ${IMG_CLOUDFLARED:-cloudflare/cloudflared:latest}
compose/core.yml:79:    image: ghcr.io/gethomepage/homepage:latest
compose/core.yml:144:    image: ${IMG_PORTAINER:-portainer/portainer-ce:latest}
compose/core.yml:172:    image: fmartinou/whats-up-docker:latest
compose/core.yml:208:    image: filebrowser/filebrowser:latest
compose/media.yml:7:    image: stremio/server:latest
compose/media.yml:41:    image: jellyfin/jellyfin:latest
compose/monitoring.yml:7:    image: ${IMG_GRAFANA:-grafana/grafana-oss:latest}
compose/monitoring.yml:54:    image: ${IMG_ALERTMANAGER:-prom/alertmanager:latest}
compose/monitoring.yml:92:    image: prom/blackbox-exporter:latest
compose/monitoring.yml:125:    image: ${IMG_PROMETHEUS:-prom/prometheus:latest}
compose/monitoring.yml:164:    image: prom/node-exporter:latest
compose/monitoring.yml:198:    image: ${IMG_CADVISOR:-gcr.io/cadvisor/cadvisor:latest}
compose/monitoring.yml:239:    image: netdata/netdata:latest
compose/monitoring.yml:274:    image: grafana/loki:latest
compose/monitoring.yml:304:    image: grafana/promtail:latest
compose/security.yml:7:    image: ${IMG_PIHOLE:-pihole/pihole:latest}
compose/security.yml:44:    image: ${IMG_VAULTWARDEN:-vaultwarden/server:latest}
compose/security.yml:145:    image: ${IMG_AUTHENTIK_SERVER:-ghcr.io/goauthentik/server:latest}
compose/security.yml:194:    image: ${IMG_AUTHENTIK_SERVER:-ghcr.io/goauthentik/server:latest}

## Services WITHOUT healthcheck
compose/automation.yml homeassistant
compose/core.yml cloudflared
compose/core.yml homepage
compose/core.yml uptime-kuma
compose/core.yml portainer
compose/core.yml whats-up-docker
compose/core.yml filebrowser
compose/dev-dashboard.yml dev-dashboard
compose/media.yml stremio
compose/monitoring.yml grafana
compose/monitoring.yml prometheus
compose/monitoring.yml node-exporter
compose/monitoring.yml netdata
compose/monitoring.yml promtail
compose/security.yml pihole
compose/security.yml authentik-worker

## Services WITHOUT resource limits
compose/core.yml cloudflared
compose/lan-proxy.yml caddy-lan

## Leftover TAILSCALE_IP in port bindings (PR #9 follow-ups)
compose/forge-space.yml:32:      - "${TAILSCALE_IP}:${FORGE_MCP_GATEWAY_PORT:-4444}:4444"

## Env drift (.env vs .env.example)
12d11
< BIND_IP=
18a18,26
> FORGE_MCP_ADMIN_API_ENABLED=
> FORGE_MCP_ADMIN_EMAIL=
> FORGE_MCP_ADMIN_FULL_NAME=
> FORGE_MCP_ADMIN_PASSWORD=
> FORGE_MCP_AUTH_REQUIRED=
> FORGE_MCP_BASIC_AUTH_PASSWORD=
> FORGE_MCP_BASIC_AUTH_USER=
> FORGE_MCP_GATEWAY_PORT=
> FORGE_MCP_JWT=
19a28,30
> FORGE_MCP_SECURE_COOKIES=
> FORGE_MCP_SERVER_URL=
> FORGE_MCP_UI_ENABLED=

## Dockerfiles summary
=== dockerfiles/serena-mcp.Dockerfile ===
FROM ghcr.io/oraios/serena:v0.1.4

USER root

ARG TERRAFORM_VERSION=1.14.6
USER/HEALTHCHECK directives: 2
