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

---

## Static-analysis update (2026-04-21)

Pass done without SSH. Narrows what the next live-host audit still has to verify, and flags one hidden migration cost the original audit missed.

### Dependency graph (from compose files)

`grep -rn 'depends_on:' compose/` followed by a service-name filter returns **zero** matches for `nginx`, `whats-up-docker`, and `netdata`. All three are leaf nodes — removing them cannot break an explicit compose dependency. (Implicit runtime deps — e.g. cloudflared dialing a route nginx serves — are not captured by `depends_on`; see nginx caveat below.)

### Candidate-by-candidate

| # | Candidate | Static verdict | What live audit still has to confirm |
|---|---|---|---|
| 1 | `netdata` | **Safe to remove** — no `depends_on`; no service references the netdata container. Grafana provisioning dir grepped: no netdata datasource. Prometheus/node-exporter/cAdvisor already scrape host+container metrics. | Grafana dashboards (Grafana's own DB) for any netdata data source. `docker stats netdata` baseline so the reclaimed RAM/CPU is logged. |
| 2 | `nginx` | **Not safe to remove in one PR.** Caddy `config/caddy/Caddyfile` *does* cover every route in `config/nginx/conf.d/tailscale-domains.conf`, BUT `config/nginx/conf.d/dev-dashboard.conf` serves `https://dev.luk-homeserver.com.br` with an Authentik SSO integration (`include conf.d/includes/authentik-server-sso.conf` + `authentik-location-auth.conf`) that has no Caddy equivalent in the current Caddyfile. Migration cost hidden by the original audit. | Whether `dev-dashboard` is still used (also its own audit item #8). If yes, translate the `auth_request` / `authentik-location-auth.conf` pattern to Caddy's [`forward_auth`](https://caddyserver.com/docs/caddyfile/directives/forward_auth). If no, drop `dev-dashboard` and nginx becomes removable in one pass. |
| 3 | `whats-up-docker` | **Safe to remove** — no `depends_on`. Renovate (`renovate.json`) has been active since PR #12 with `automerge: true` on `patch`/`digest` for `docker-compose`/`dockerfile` managers. WUD env vars in `.env.example` are WUD-only (`WUD_UPDATER_DOCKER_HUB_TOKEN`, `WUD_UPDATER_GITHUB_TOKEN`, `WUD_SMTP_*`, `WUD_DISCORD_WEBHOOK_URL`), except `WUD_DISCORD_WEBHOOK_URL` is also used as a fallback in `scripts/maintenance/update-containers.sh:62` behind `UPDATE_DISCORD_WEBHOOK_URL`. | Whether the Homepage widget or any Discord channel still subscribes to WUD notifications. If yes, the `UPDATE_DISCORD_WEBHOOK_URL` path already fully replaces that wiring. |
| 4 | `blackbox-exporter` ↔ `uptime-kuma` | **Deferred** — decision rule depends on which one has active probes. That is Grafana-/Uptime-Kuma-UI state, not static. | Follow audit's decision rule as-is. |
| 5 | `loki` + `promtail` | **Deferred** — Grafana-panel data, not static. | Follow audit's decision rule as-is. |
| 6 | `filebrowser` | **Static suggestive only** — service declares `volumes: /home/luk-server:/srv/home` so whoever is using it is using it directly against the homeserver filesystem, which is not a use-case `nextcloud` fully replaces. | `docker logs filebrowser --since 30d \| wc -l` per audit. |
| 7 | `paperless-ngx:custom` | **Static suggestive only.** | As audit. |
| 8 | `dev-dashboard` | **Gates nginx removal** (see #2). If dropped, unblocks nginx cleanup. | As audit. |

### What to do on next SSH (condensed order)

```bash
# From laptop
ssh homelab 'bash -s' < scripts/audit-services.sh > docs/audits/$(date +%F)-live.log

# On homelab (quick deterministic checks)
docker logs filebrowser --since 30d | wc -l
docker exec grafana find /var/lib/grafana/dashboards -name '*.json' \
  -exec grep -l -E 'netdata|loki' {} +
docker logs whats-up-docker --since 30d | grep -c 'notif'
```

Once the log is filled in, each of the three "Safe to remove" items above is a single-file compose PR (plus docs/env cleanup). The nginx migration is a separate, larger spec and should be tracked under `docs/specs/2026-04-??-caddy-dev-dashboard-migration/` before attempting.
