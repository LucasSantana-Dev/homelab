# Homelab Docker Compose Operations

Manage, restart, and troubleshoot Docker Compose services in the homelab.

## When to Use
- Restarting or recreating individual services
- Checking container health and status
- Diagnosing OOM kills, restart loops, or unhealthy containers
- Running scheduled or manual container image updates

## Compose File Structure

The root `docker-compose.yml` is a modular orchestrator that includes all service modules:

```
docker-compose.yml          # Orchestrator (include directives only)
compose/base.yml            # Networks and named volumes
compose/core.yml            # nginx-proxy, homepage, portainer, uptime-kuma, filebrowser, wud
compose/monitoring.yml      # prometheus, grafana, loki, alertmanager, netdata, promtail, etc.
compose/media.yml           # jellyfin, stremio-server
compose/apps.yml            # n8n, paperless-ngx, nextcloud
compose/security.yml        # authentik-server, authentik-worker, vaultwarden, pihole
compose/automation.yml      # homeassistant
compose/forge-space.yml     # Forge Space MCP gateway (profile: forge-space)
```

## Network Topology

```
frontend   172.20.0.0/24   External-facing services (nginx-proxy, homepage, etc.)
backend    172.21.0.0/24   Internal-only (no internet access)
monitoring 172.22.0.0/24   Metrics and log services
database   172.23.0.0/24   DB containers (internal-only, no internet access)
default                    Compose default bridge; most services share this
```

Services that need internet exposure attach to `frontend`. Internal services use `backend` or `database`.

## Restarting Services

### IMPORTANT: Forge env var caveat

`docker compose` commands validate variable interpolation for **all included files**, including `compose/forge-space.yml`. If `FORGE_MCP_JWT_SECRET_KEY`, `FORGE_MCP_BASIC_AUTH_PASSWORD`, or `FORGE_MCP_ADMIN_PASSWORD` are not set in the environment, `docker compose up/restart` will fail with an interpolation error.

**Safe pattern — use `docker restart` for single-container restarts:**
```bash
docker restart <container-name>
```

**Only use `docker compose` when the Forge vars are present or you export placeholders first:**
```bash
export FORGE_MCP_JWT_SECRET_KEY="${FORGE_MCP_JWT_SECRET_KEY:-placeholder}"
export FORGE_MCP_BASIC_AUTH_PASSWORD="${FORGE_MCP_BASIC_AUTH_PASSWORD:-placeholder}"
export FORGE_MCP_ADMIN_PASSWORD="${FORGE_MCP_ADMIN_PASSWORD:-placeholder}"
docker compose up -d --no-deps --force-recreate <service-name>
```

Or source from `.env` first:
```bash
set -a && source /home/luk-server/homelab/.env && set +a
docker compose -f /home/luk-server/homelab/docker-compose.yml up -d --no-deps <service-name>
```

## Checking Container Health

```bash
# All containers with status
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

# Detailed health for a specific container
docker inspect --format '{{.State.Status}} | health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' <name>

# Live logs (last 50 lines)
docker logs --tail 50 -f <container-name>

# Recent OOM kills
dmesg -T | grep -i "oom\|killed" | tail -20

# Container resource usage
docker stats --no-stream
```

## Common Troubleshooting

### OOM Kill
- **Symptom**: container exits with code 137, `dmesg` shows `oom-kill-action`
- **Common offenders**: `cadvisor` (limit 768M), `loki` (limit 512M), `prometheus` (limit 1G)
- **Fix**: `docker restart <name>` to bring it back; investigate memory growth in Grafana
- **cadvisor** has `healthcheck: disable: true` by default — it OOMs most frequently

### Unhealthy container
- **Symptom**: `docker ps` shows `(unhealthy)` in the status column
- **Check**: `docker inspect --format '{{json .State.Health}}' <name> | jq .`
- **Loki**: healthcheck is disabled (`healthcheck: disable: true`) — ignore Loki health in `docker ps`
- **Fix**: check logs, then `docker restart <name>`

### Restart loop (restarting every few seconds)
- **Check logs**: `docker logs --tail 100 <name>`
- **Common causes**: missing env var, config parse error, port conflict
- **Stop the loop**: `docker stop <name>` then fix the config before restarting

### Port conflict
```bash
ss -tlnp | grep <port>
docker ps --format '{{.Names}}\t{{.Ports}}' | grep <port>
```

### Container missing after host reboot
- All containers have `restart: unless-stopped` — they should auto-start
- If a container is missing: `docker ps -a` to check stopped state, then `docker start <name>`

## Update Workflow

The managed update script handles rolling updates with health checks between groups:

```bash
# Full update run (pulls new images, recreates changed containers)
bash scripts/maintenance/update-containers.sh

# Dry run (shows what would change)
bash scripts/maintenance/update-containers.sh --dry-run
```

Update order: `databases → security → core → apps → monitoring → utilities`

After Authentik updates the script automatically reloads `nginx-proxy` to refresh upstream resolution.

Update notifications are sent to Discord via `UPDATE_DISCORD_WEBHOOK_URL` (falls back to `WUD_DISCORD_WEBHOOK_URL`).

## Key Container Names (service → container)

| Service module | Container name |
|---|---|
| nginx-proxy | `nginx-proxy` |
| homepage | `homepage` |
| prometheus | `prometheus` |
| grafana | `grafana` |
| loki | `loki` |
| alertmanager | `alertmanager` |
| authentik-server | `authentik-server` |
| authentik-worker | `authentik-worker` |
| homeassistant | `homeassistant` |
| cadvisor | `cadvisor` |
| node-exporter | `node-exporter` |

## Scripts Reference
- `scripts/maintenance/update-containers.sh` — managed rolling update
- `scripts/maintenance/update-containers-cron.sh` — cron/systemd wrapper
- `scripts/maintenance/post-reboot-validate.sh` — validates all containers after reboot
- `scripts/maintenance/power-restore-check.sh` — post-power-loss health check
