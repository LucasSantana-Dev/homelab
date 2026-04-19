# Homelab Service Audit — 2026-04-19

**Goal:** identify stale/redundant services consuming resources. Ship prune PRs for anything confirmed unused.

**Status:** static analysis complete; live runtime data pending (homelab unreachable at audit time — run `scripts/audit-services.sh` when on the tailnet).

## How to complete this audit

```bash
ssh homelab 'bash -s' < scripts/audit-services.sh \
  > docs/audits/$(date +%F)-live.log
```

Then fill the **Live data** sections below and open per-service removal PRs for anything flagged "remove".

## Service inventory (declared in compose/)

Grouped by compose file. `→` indicates friend-exposed (see `docs/tailscale-friends-sharing.md`).

| File | Services |
|---|---|
| `apps.yml` | n8n, nextcloud (+ db/redis), paperless-ngx (+ db/redis) |
| `automation.yml` | homeassistant |
| `core.yml` | nginx, cloudflared, homepage, uptime-kuma, portainer, whats-up-docker, filebrowser |
| `forge-space.yml` | forge-mcp-gateway *(profile: forge-space)* |
| `lan-proxy.yml` | caddy-lan |
| `media.yml` | stremio→, jellyfin→ |
| `monitoring.yml` | grafana, alertmanager, blackbox-exporter, prometheus, node-exporter, cadvisor, netdata, loki, promtail |
| `security.yml` | pihole, vaultwarden, authentik (db/redis/server/worker) |
| `automation.yml` + homelab server | craftvaria (Minecraft)→ |
| `dev-dashboard.yml` | dev-dashboard *(python:3-alpine)* |

## Static-analysis suspects

Each candidate has **evidence** (why it looks stale) and a **verify step** (how to prove it before deleting).

### 1. `netdata` — likely remove

- **Evidence:** Prometheus + node-exporter + cAdvisor + Grafana (Wave 2D) already cover host/container metrics. Netdata duplicates both collection and UI. Netdata pulls ~200MB RAM + continuous CPU.
- **Verify:** `docker stats netdata` over 1h. Check if any Grafana dashboard or alert rule references netdata.
- **Action:** remove `netdata` block from `compose/monitoring.yml`. Keep node-exporter + cAdvisor.

### 2. `nginx` (in `core.yml`) — likely remove

- **Evidence:** Caddy (`lan-proxy.yml`) is the current LAN edge, with `*.home` hostnames live in `config/caddy/Caddyfile`. `config/nginx/conf.d/stremio.conf` was just deleted on the `fix/stremio-remote-access` branch, suggesting nginx is on its way out.
- **Verify:** confirm no service depends on nginx's network; check `docker ps | grep nginx`; grep compose files for `nginx:` references.
- **Action:** remove `nginx` service + its `appdata/nginx/` config once migration complete.

### 3. `whats-up-docker` — likely remove

- **Evidence:** Renovate is already running on this repo (`renovate.json`) for dependency updates. WUD duplicates that function for container images, less flexibly.
- **Verify:** check if Homepage or any notification channel currently subscribes to WUD events.
- **Action:** remove from `core.yml`. Let Renovate handle image bumps via `.env` variables (`IMG_*`).

### 4. `blackbox-exporter` vs `uptime-kuma` — consolidate

- **Evidence:** both probe HTTP/TCP endpoints. Blackbox feeds Prometheus; Uptime Kuma has its own UI + alerts.
- **Verify:** check which one has current probes configured (`config/blackbox/` vs Uptime Kuma UI).
- **Decision rule:** if Grafana dashboards already visualize blackbox probes → keep blackbox, drop uptime-kuma. Otherwise → keep uptime-kuma (simpler), drop blackbox.

### 5. `loki` + `promtail` — confirm or remove

- **Evidence:** log aggregation only pays off if Grafana dashboards query it or alerts fire on log patterns.
- **Verify:** Grafana → Dashboards → filter by Loki datasource. Count ≥ 1 → keep. Zero → remove both.

### 6. `filebrowser` — likely remove

- **Evidence:** Nextcloud + Jellyfin already cover the file browsing/sharing use cases. Filebrowser is the lowest-value service with a public-ish endpoint.
- **Verify:** `docker logs filebrowser --since 30d | wc -l` — any access at all?
- **Action:** remove from `core.yml`.

### 7. `paperless-ngx:custom` — rebuild or drop

- **Evidence:** custom image (non-upstream tag) implies a local Dockerfile. If no one is uploading documents, it's stale disk + an unmaintained image build.
- **Verify:** last write to paperless data volume.
- **Action:** if used → restore to upstream `ghcr.io/paperless-ngx/paperless-ngx`; if unused → remove service + volumes.

### 8. `dev-dashboard` — confirm still in use

- **Evidence:** `python:3-alpine` base suggests an experimental one-off. Lives in a single-service compose file (`dev-dashboard.yml`), detached from the main stack.
- **Verify:** who/what hits its Caddy route? Grep `caddy` logs for the hostname.
- **Action:** archive under `archive/` if experimental and no longer referenced.

## Live data

Fill in after running `scripts/audit-services.sh`:

### Resource hogs (top 5 by RAM / CPU)

```
<paste from DOCKER_STATS section>
```

### Stale containers (uptime > 30d without access)

```
<paste from CONTAINER_AGE_AND_RESTARTS + CADDY_ACCESS_7D>
```

### Stopped/exited containers

```
<paste from STOPPED_CONTAINERS>
```

### Dangling images / volumes

```
<paste from DANGLING>
```

## Follow-up PRs

One PR per confirmed removal, merge auto-queued:

- [ ] `chore(monitoring): remove netdata`
- [ ] `chore(core): remove nginx (migrated to caddy)`
- [ ] `chore(core): remove whats-up-docker (handled by renovate)`
- [ ] `chore(monitoring): consolidate blackbox-exporter ↔ uptime-kuma`
- [ ] `chore(monitoring): remove loki + promtail` *(if no dashboards depend)*
- [ ] `chore(core): remove filebrowser`
- [ ] `chore(apps): remove/restore paperless-ngx`
- [ ] `chore: archive dev-dashboard`

## Re-run cadence

Add this audit to `roadmap.md` as a quarterly task. Automated trigger:
see `~/.claude/skills/homelab-audit/SKILL.md`.
