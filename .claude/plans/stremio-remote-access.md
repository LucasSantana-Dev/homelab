---
status: planned
created: 2026-04-19
owner: lucassantana
pr: null
tags: [homelab, stremio, networking, caddy, pihole, tailscale]
---

# Stremio Remote Access Fix

## Goal
Make the homelab Stremio server reachable from other devices — on-LAN via `http://stremio.home` and off-LAN via a Tailscale Funnel HTTPS URL that Stremio Web accepts.

## Current state (verified live on homelab 2026-04-19)
- Container `stremio-server` **is not running** (no `docker ps -a` entry). `compose/media.yml` defines it but `docker compose up` was never executed.
- Only running containers: `caddy-lan`, `pihole`, `lucky-nginx`.
- Caddyfile (`~/homelab/config/caddy/Caddyfile`): `*.home` routes for ai/craftvaria/lucky/registry/pihole/cockpit — **no `stremio.home`**.
- Pi-hole dnsmasq (`etc-dnsmasq.d/02-local-home.conf`): **no stremio record**.
- Real env: `DOMAIN=luk-homeserver.com.br`, `TAILSCALE_IP=100.95.204.103`, LAN IP `192.168.0.6` (⚠️ memory index says `.11` — drift, separate issue).
- Stale scripts still point at fake `stremio.homelab.example.com`: `scripts/{test-stremio-connection,diagnose-stremio,test-device-connectivity,setup-device-dns}.sh`.
- `config/nginx/conf.d/stremio.conf` is a disabled stub (nginx replaced by Caddy).

## Root cause
Three independent gaps: (1) container never started; (2) no LAN DNS/proxy route; (3) no HTTPS endpoint, so Stremio Web (HTTPS origin) refuses the HTTP server URL (mixed-content block).

## Out of scope
- Jellyfin (same compose file — touch only if trivially colocated).
- Full LAN IP drift reconciliation (memory 192.168.0.11 vs live 192.168.0.6) — note only.
- Migrating to k3s — stays on Compose per ADR 0004.

## Phases

### Phase 1 — Start the container (15 min)
Files: none (runtime only).
- `ssh homelab 'cd ~/homelab && docker compose -f compose/base.yml -f compose/media.yml up -d stremio'`
- Wait for status `Up (healthy)` or `Up` (no healthcheck defined — add one in Phase 2 if time allows).
- **Verify**: `curl -sI http://127.0.0.1:11470/` on homelab returns 200; `curl -sI http://192.168.0.6:11470/` from laptop returns 200; `curl -sI http://100.95.204.103:11470/` over Tailscale returns 200.

### Phase 2 — LAN HTTP route `stremio.home` (20 min)
Files: `config/caddy/Caddyfile`, `config/pihole/etc-dnsmasq.d/02-local-home.conf`.
- Append to Caddyfile:
  ```
  http://stremio.home {
      reverse_proxy 127.0.0.1:11470
  }
  ```
- Append to dnsmasq custom conf: `address=/stremio.home/192.168.0.6`
- `docker exec caddy-lan caddy reload --config /etc/caddy/Caddyfile`
- `docker exec pihole pihole restartdns`
- **Verify**: from a LAN device: `curl -sI http://stremio.home/` → 200; `dig stremio.home @192.168.0.6 +short` → `192.168.0.6`.

### Phase 3 — HTTPS for Stremio Web via Tailscale Funnel (30 min)
Stremio Web enforces HTTPS for the streaming server URL (mixed-content). Funnel is the lowest-friction trusted-cert path (no DNS-01 / Cloudflare plumbing).
- `ssh homelab 'sudo tailscale funnel --bg --https=443 http://127.0.0.1:11470'`
- Record the emitted URL (e.g. `https://homelab.<tailnet>.ts.net`) into `.env` as `STREMIO_PUBLIC_URL` and into `config/stremio/README.md`.
- Update `compose/media.yml` env `STREMIO_SERVER_URL=${STREMIO_PUBLIC_URL}` so server self-reports the correct URL; `docker compose up -d stremio` to re-apply.
- **Verify**: `curl -sI https://<funnel-host>/` → 200 with valid Let's Encrypt chain; in Stremio Web → Settings → Server → paste funnel URL → streaming server status = connected.
- **Fallback**: if Funnel is disabled in the tailnet ACL, pivot to Caddy + Cloudflare DNS-01 on `stremio.luk-homeserver.com.br` (documented as Phase 3b in PR description, not executed by default).

### Phase 4 — Scripts cleanup (15 min)
Files: `scripts/{test-stremio-connection,diagnose-stremio,test-device-connectivity,setup-device-dns}.sh`, `config/nginx/conf.d/stremio.conf`.
- Replace all `stremio.homelab.example.com` → `stremio.home` (LAN path) and parameterize the Funnel URL from `.env`.
- Delete `config/nginx/conf.d/stremio.conf` (dead stub).
- Have `diagnose-stremio.sh` print the three canonical URLs: LAN (`http://stremio.home`), Tailscale (`http://100.95.204.103:11470`), Funnel (from `.env`).
- **Verify**: `bash scripts/diagnose-stremio.sh` returns all green.

### Phase 5 — Ship (15 min)
- Branch `fix/stremio-remote-access`.
- Commit split: (a) caddy+pihole route, (b) compose/env updates, (c) scripts cleanup.
- Push, open PR with CI, `gh pr merge --auto --squash` → `safe-merge` once green.
- On merge: update `~/.claude/projects/-Users-lucassantana/memory/homelab-network.md` with the new `stremio.home` entry and Funnel URL; note LAN IP drift (`.6` vs `.11`) as a follow-up TODO.
- **Verify**: PR merged, `docker compose up -d` idempotent on clean checkout reproduces working state.

## Dependencies
Phase 1 → 2 → 3 sequentially (need container up before proxy can reach it, need LAN DNS before scripts reference it). Phase 4 can run parallel to Phase 3. Phase 5 depends on all prior phases.

## Related context
(RAG pack excerpts above — `scripts/diagnose-stremio.sh`, `compose/media.yml`, `setup-device-dns.sh`, homelab-lan plan.)
