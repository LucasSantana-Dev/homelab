# CoJam deploy runbook

CoJam's Go server + its own Postgres, added as `compose/cojam.yml`. The server
persists room state (queue, now-playing, radio). Three services: `cojam-db`
(Postgres), `cojam-server` (Go API + WebSocket at `cojam-api.${DOMAIN}` /
`cojam-api.home`), and `cojam-web` (the Next.js frontend at `cojam.${DOMAIN}` /
`cojam.home`). The web image is environment-agnostic; it reads the WebSocket URL
at runtime from `COJAM_WS_URL` (set in compose to `wss://cojam-api.${DOMAIN}/...`).

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

   Optional overrides (defaults shown):

   ```bash
   # COJAM_CORS_ORIGINS=https://cojam.<your-domain>   # the web frontend origin
   # IMG_COJAM_SERVER=ghcr.io/lucassantana-dev/cojam-server:latest
   ```

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
curl -s http://127.0.0.1:8092/env.js       # window.__COJAM_ENV__ = {"wsUrl":"wss://cojam-api...."}
curl -sI http://cojam.home/ | head -1      # 200 via Caddy

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
