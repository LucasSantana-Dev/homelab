# M2 docker-socket-proxy — on-host validation runbook

On-host checklist for PR #384 (route read-only `docker.sock` consumers through
`tecnativa/docker-socket-proxy`). This change **cannot** be validated in CI or on a
dev box (no docker daemon / no host), so it ships as a draft PR gated on this
runbook. See issue #378 for the design and rationale.

## What changes

A filtering `docker-socket-proxy` (read-only endpoint allowlist) is added on an
internal `socketproxy` network. Three consumers move off the direct socket mount:

| Service | Before | After |
|---------|--------|-------|
| agent-box | `/var/run/docker.sock:ro` | `DOCKER_HOST=tcp://docker-socket-proxy:2375` |
| whats-up-docker | `/var/run/docker.sock:ro` | `WUD_WATCHER_LOCAL_HOST/PORT` → proxy |
| homepage | `/var/run/docker.sock:ro` | `config/homepage/docker.yaml` host/port → proxy |
| homelab-manager | direct socket | **unchanged** (needs write) |
| portainer | direct socket | **unchanged** (needs write, ADR-0017) |

Why: `:ro` on `docker.sock` only makes the socket **file** read-only. The Docker
API over it stays fully capable, so a compromised consumer can still
`POST /containers/create`, exec, and mount the host root. Only a filtering proxy
actually restricts the API.

## Validation (run on the homelab host)

```bash
# ── On the homelab host, from the repo checkout ──
cd "$HOMELAB_DIR"    # the homelab repo on the host

# 0. Deploy the branch (git-first per ADR-0036; commit/stash dirty files first)
git fetch origin && git checkout hardening/docker-socket-proxy
make deploy

# CHECK 1 — proxy up and READ-ONLY (allow GET, deny POST)
docker ps --filter name=docker-socket-proxy --format '{{.Names}} {{.Status}}'
docker exec agent-box wget -qO- http://docker-socket-proxy:2375/version | head -c 200; echo
docker exec agent-box wget -qO- --post-data='' http://docker-socket-proxy:2375/containers/create 2>&1 \
  | grep -i "403\|forbidden" && echo "WRITE DENIED ok" || echo "WARN WRITE NOT DENIED - STOP"

# CHECK 2 — agent-box docker-mcp honors DOCKER_HOST (riskiest unknown)
docker exec agent-box sh -c 'echo DOCKER_HOST=$DOCKER_HOST'   # expect tcp://docker-socket-proxy:2375
docker exec agent-box docker ps --format '{{.Names}}' | head  # expect a container list via the proxy
# Then exercise the docker-mcp MCP server the way an agent would and confirm it lists containers.
# If it cannot, docker-mcp hardcodes the socket path -> revert agent-box (see rollback + fallback).

# CHECK 3 — whats-up-docker connected via tcp watcher
docker logs whats-up-docker 2>&1 | grep -iE "watcher|docker-socket-proxy|error" | tail -20

# CHECK 4 — homepage docker widgets render over TCP
curl -s http://127.0.0.1:${HOMEPAGE_PORT:-3000}/ -o /dev/null -w "homepage HTTP %{http_code}\n"
docker logs homepage 2>&1 | grep -iE "docker|socket|error" | tail -20

# CHECK 5 — direct-socket services unaffected
docker ps --filter name=portainer --filter name=homelab-manager --format '{{.Names}} {{.Status}}'
curl -s http://127.0.0.1:${PORTAINER_PORT:-9000}/ -o /dev/null -w "portainer HTTP %{http_code}\n"

# ROLLBACK (if any check fails)
git checkout release && make deploy    # restores direct-socket config; comment the failure on PR #384
```

## Pass criteria

- Check 1: write denied (403).
- Check 2: agent-box lists containers through the proxy.
- Checks 3–4: no connection errors in WUD / homepage logs.
- Check 5: portainer + homelab-manager healthy.

All green → mark #384 ready and merge to `release`.

## Most likely failure + fallback

Check 2. If `docker-mcp` hardcodes `/var/run/docker.sock` it will ignore
`DOCKER_HOST`. Fallback: leave **agent-box on the direct socket** and still move
**whats-up-docker + homepage** behind the proxy (a net win). Record the outcome on
issue #378.
