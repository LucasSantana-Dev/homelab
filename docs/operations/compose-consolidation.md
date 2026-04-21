# Docker Compose Project Consolidation

## Background

The homelab runs two Docker Compose projects:

1. **`compose`** (manual project) — started via `docker compose -f compose/base.yml -f compose/media.yml -f compose/lan-proxy.yml -f compose/security.yml up -d`
2. **`homelab`** (systemd project) — started via `systemctl restart homelab-docker.service`, loads the main `docker-compose.yml`

This causes name collisions: services in the manual `compose` project block the systemd `homelab` project from starting, resulting in only 2 of 9 service modules coming up.

## Consolidation Steps

### 1. Stop the manual compose project

```bash
cd ~/homelab
docker compose -p compose down
```

Verify it's down:
```bash
docker compose -p compose ps
# Should show "no running services"
```

### 2. Restart systemd homelab service

```bash
sudo systemctl restart homelab-docker.service
```

Check logs:
```bash
sudo systemctl status homelab-docker.service
sudo journalctl -u homelab-docker.service -f
```

### 3. Verify all services are running

```bash
docker compose -p homelab ps
# Should show all 9 modules (base, core, lan-proxy, monitoring, media, apps, security, automation, dev-dashboard)
```

### 4. Test connectivity

- **Caddy LAN proxy**: `curl -sI http://127.0.0.1:80/`
- **Homepage**: `http://localhost:8080`
- **Grafana**: `http://localhost:3000` (verify no port conflict with Open WebUI)
- **Pi-hole**: `http://localhost:5380`

## Port Conflict Warning

**IMPORTANT**: If you see "port 3000 is already allocated", check if Open WebUI is still running on that port:

```bash
docker compose -p homelab ps | grep 3000
```

If Open WebUI (running separately) is on 3000, you must either:
- Stop Open WebUI and update its compose to use a different port
- Change Grafana config to use port 3001 (see `docker-compose.yml` environment variables)

## Rollback (if needed)

If something goes wrong:
```bash
sudo systemctl stop homelab-docker.service
docker compose -p homelab down
# Then restart the manual compose:
docker compose -p compose -f compose/base.yml -f compose/media.yml -f compose/lan-proxy.yml -f compose/security.yml up -d
```

## Verification Checklist

- [ ] Manual `compose` project is down
- [ ] Systemd service restarted successfully
- [ ] All 9 services show "Up" in `docker compose ps`
- [ ] Caddy is routing `*.home` domains
- [ ] Grafana is accessible on port 3000 (or configured port)
- [ ] No port conflicts reported

## Future: Remove the manual startup

Once this is verified, the manual `docker compose -p compose ...` command can be removed from init scripts and cron jobs. The systemd unit now handles everything.
