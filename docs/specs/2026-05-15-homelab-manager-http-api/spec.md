# Spec: homelab_manager HTTP API Mode (/health /status /summary)

**Created:** 2026-05-15  
**ADR:** docs/adr/0009-dashboard-expansion-github-widgets-api-tier.md (Tier 2)  
**Effort:** m (1–2d)  
**Severity:** medium  

---

## Goal

Add an HTTP server mode to `homelab_manager` exposing JSON endpoints (`/health`, `/status`, `/summary`) so Homepage `customapi` widgets can display live infra state without SSH access.

## Context

- `homelab_manager` is currently CLI-only (`homelab_manager/cli/` — 4 files).
- `homelab_manager/services/health.py` has `HealthMonitor.check_all_services()` (parallelized, PR #101) — this is the data source.
- ADR 0009 Tier 2 specifies HTTP server mode, loopback-bound (`127.0.0.1`) until Caddy forward-auth is wired.
- ADR 0006 established the precedent for homelab_manager HTTP surface (WoL shell endpoint).
- ADR 0003: any new HTTP service must be proxied through Caddy (ingress boundary rule). Port must not be publicly exposed until then.
- Homepage `customapi` widget renders key-value pairs from a JSON endpoint — sufficient for health/status metrics.

## Approach

### Server module

1. Create `homelab_manager/server/` package:
   - `__init__.py`
   - `app.py` — lightweight HTTP server (use `http.server` stdlib or `fastapi` if already a dependency; check `pyproject.toml` first)
   - `routes.py` — endpoint handlers

2. Implement endpoints:
   - `GET /health` → `{"status": "ok", "timestamp": "<ISO>", "version": "<version>"}`
   - `GET /status` → output from `HealthMonitor.check_all_services()` serialized to JSON (service name → status dict)
   - `GET /summary` → aggregated counts: `{"total": N, "healthy": N, "unhealthy": N, "unknown": N, "services": [...]}`

3. Bind exclusively to `127.0.0.1:<port>` (default: 8765). Port configurable via env var `HOMELAB_MANAGER_HTTP_PORT`.

### CLI integration

4. Add `homelab serve` subcommand to `homelab_manager/cli/commands.py`:
   ```
   homelab serve [--port PORT] [--host HOST]
   ```
   Starts the HTTP server. Default host: `127.0.0.1`.

### Deployment

5. Add `homelab_manager` as a service in a compose file (e.g. `compose/core.yml` or new `compose/manager.yml`):
   - Bind port: `127.0.0.1:8765:8765`
   - Volume mount for compose files (read-only)
   - Restart policy: `unless-stopped`

6. Wire Homepage `customapi` widget in `config/homepage/services.yaml` (or the Projects tab YAML) pointing to `http://homelab-manager:8765/summary`.

### Security

7. Until Caddy forward-auth (Authentik) is wired:
   - Port must be loopback-bound on the host
   - No public ingress route in Cloudflare tunnel config
   - Add to `docs/adr/0009` revisit-when: "when Caddy forward-auth is ready, expose via subdomain"

## Verification

- [ ] `homelab serve` starts without error and logs `Listening on 127.0.0.1:8765`
- [ ] `GET /health` returns `{"status": "ok", ...}` with HTTP 200
- [ ] `GET /status` returns a JSON object with at least one service entry
- [ ] `GET /summary` returns `total`, `healthy`, `unhealthy` counts that match `homelab status` CLI output
- [ ] Port is NOT accessible from outside loopback (verify with `curl http://<server-LAN-IP>:8765/health` — should fail)
- [ ] Homepage `customapi` widget renders the summary data without error
- [ ] All existing `homelab_manager` tests pass (`pytest tests/`)
- [ ] New unit tests cover: route handlers return correct shape, HealthMonitor serialization

## Out of scope

- Authentication middleware (deferred to Authentik integration)
- WebSocket live updates
- Metrics/Prometheus endpoint (separate feature if needed)
- Public Caddy route (blocked on Authentik)
