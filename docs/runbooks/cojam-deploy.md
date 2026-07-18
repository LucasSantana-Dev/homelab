# CoJam deploy runbook

CoJam's Go server + its own Postgres, added as `compose/cojam.yml`. The server
persists room state (queue, now-playing, radio). Three services: `cojam-db`
(Postgres), `cojam-server` (Go API + WebSocket on `:8091`), and `cojam-web`
(the Next.js frontend on `:8092`).

**Public domain: a single subdomain `cojam.${COJAM_DOMAIN}`** (e.g.
`cojam.lucassantana.tech`). Caddy path-routes on that one host: `/connection/*`
(the centrifuge WebSocket) and `/api/*` (connection-token + apple dev-token) go
to the Go server; everything else (the Next app, `/env.js`, `/callback`,
`/room`) goes to the web frontend. The web app defines no `/api/*` routes, so the
split is collision-free. `COJAM_DOMAIN` lets CoJam use its own domain without
moving other homelab services off the shared `${DOMAIN}`; it falls back to
`${DOMAIN}` when unset. The web image is environment-agnostic and reads the
WebSocket URL at runtime from `COJAM_WS_URL`
(`wss://cojam.${COJAM_DOMAIN}/connection/websocket`). LAN access keeps the
two-subdomain split (`cojam.home` / `cojam-api.home`) for local testing.

## Prerequisites

- The server image must be published to GHCR first. The CoJam repo's
  `publish-server-image` workflow pushes `ghcr.io/lucassantana-dev/cojam-server`
  on pushes to `main`. Confirm the package exists (and is public, or `docker
  login ghcr.io` on the host) before deploying.

## One-time setup

1. Add the database password to the host `.env` (never committed in plaintext):

   ```bash
   # on the homelab host, in the repo root
   echo "COJAM_DB_PASSWORD=$(openssl rand -base64 24)" >> .env
   ```

   Domain + origin (set for the lucassantana.tech cutover):

   ```bash
   # cojam's own public domain (falls back to ${DOMAIN} if unset)
   echo "COJAM_DOMAIN=lucassantana.tech" >> .env
   # the browser origin allowed to open the WebSocket (same host now)
   echo "COJAM_CORS_ORIGINS=https://cojam.lucassantana.tech" >> .env
   # IMG_COJAM_SERVER=ghcr.io/lucassantana-dev/cojam-server:latest   # (default)
   ```

## Cloudflare (operator, one-time): expose cojam.lucassantana.tech

The homelab is reached through the Cloudflare Tunnel, so cojam needs one public
hostname on the tunnel (Cloudflare auto-creates the DNS record):

1. Cloudflare Zero Trust -> Networks -> Tunnels -> the homelab tunnel -> Public
   Hostnames -> Add a public hostname:
   - Subdomain `cojam`, domain `lucassantana.tech`
   - Service: the internal Caddy that serves this Caddyfile (the same
     `http://<caddy-lan>` target the other public hostnames use).
2. That entry auto-creates a proxied `CNAME cojam -> <tunnel-id>.cfargotunnel.com`
   in the `lucassantana.tech` DNS. No manual A record (per the tunnel doc, do not
   also publish a direct A record for tunnelled hostnames).
3. Because it is a single subdomain, no `cojam-api` hostname is needed - the WS
   and API travel under `/connection` and `/api` on `cojam.lucassantana.tech`.

If Spotify is later enabled (`FEATURE_SPOTIFY`), register the redirect URI
`https://cojam.lucassantana.tech/callback/spotify` in the Spotify app.

2. Encrypt and verify the secret, then commit the encrypted file:

   ```bash
   make sops-encrypt
   make sops-verify
   git add .env.enc && git commit -m "chore: add COJAM_DB_PASSWORD"
   ```

## Deploy

```bash
make deploy
```

`make deploy` enforces the git-first dirty-file gate (ADR-0036): pull this
change on the host first so the tracked files are clean. It then runs
`docker compose up -d --build` and the health gate.

## Verify

```bash
# containers up and healthy
docker compose ps cojam-db cojam-server cojam-web

# web serves and points at the API (runtime config, not baked)
curl -s http://127.0.0.1:8092/env.js       # {"wsUrl":"wss://cojam.lucassantana.tech/connection/websocket"}
curl -sI http://cojam.home/ | head -1      # 200 via Caddy (LAN)

# public: single subdomain path-routes correctly through the tunnel + Caddy
curl -sI https://cojam.lucassantana.tech/ | head -1                      # 200 (web)
curl -s  https://cojam.lucassantana.tech/api/connection-token | head -c 60 # 501 when FEATURE_ROOM_AUTH off, else a token (server, proves /api -> :8091)

# server reports persistence enabled + migration applied
docker compose logs cojam-server | grep -E "persistence_enabled|Starting server"

# readiness (200 when the DB is reachable)
curl -s http://127.0.0.1:8091/readyz            # {"status":"ready"}
curl -s http://cojam-api.home/readyz            # via Caddy on the LAN

# the rooms table exists
docker exec cojam-db psql -U cojam -d cojam -c "\dt"
```

## Notes

- **Migrations run on boot.** The server applies pending migrations before
  serving; a migration failure is fatal (the container exits), so a bad schema
  fails the deploy rather than serving on it.
- **Fail-fast:** if the DB is unreachable at startup the server exits within 30s
  instead of hanging or silently running in-memory.
- **Data lives at** `appdata/cojam/db` (bind mount). Back it up with the same
  mechanism as other stateful stacks.
- **Rollback:** `docker compose down cojam-server cojam-db` removes the stack;
  the data volume persists unless you delete `appdata/cojam/db`.
