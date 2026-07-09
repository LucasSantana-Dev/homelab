# ADR 0040: Compose `profiles: [optional]` for deliberately-stopped apps

- **Status:** Accepted
- **Date:** 2026-07-09
- **Deciders:** Lucas (solo operator)
- **Supersedes:** —
- **Superseded by:** —
- **Related:** [ADR-0038](./0038-reaffirm-compose-over-kubernetes-2026.md) (Compose, single N100), [ADR-0036](./0036-host-config-management.md) (git-first deploy)

---

## Context

On 2026-07-09 the operator stopped `paperless-{db,redis,ngx}` and `homeassistant`
to relieve RAM pressure on the 14 GB N100 (stremio is the prioritized app; these
four are unused). They stay in Compose with `restart: unless-stopped`.

The friction: `make deploy` runs `docker compose up -d --build`, and the boot
`homelab-docker.service` unit runs `docker compose up -d`. `up` **restarts a
manually-stopped container**, so every deploy (and every reboot) silently revived
all four — reintroducing the RAM pressure and forcing a manual `docker stop` of
the four afterward. This recurred during the v2.12.0 deploy.

We need "stopped stays stopped across `up -d`" without losing the service config
or data volumes.

## Decision

**Give the four services `profiles: ["optional"]`.** Compose excludes profiled
services from `docker compose up -d` unless the profile is explicitly activated,
so `make deploy` and the boot unit no longer start or restart them. Run on demand
with `docker compose --profile optional up -d <svc>`. Data volumes and full config
are retained; reverting is deleting one line per service.

Also **remove the `http://homeassistant:8123/` target from the Prometheus
blackbox probe list** — probing a now-intentionally-off service yields a permanent
`probe_success == 0` (the `alerts.yml:162` ServiceDown alert). Paperless was not
probed, so needs no change. (This mirrors the earlier cleanup in `prometheus.yml`
that removed retired/placeholder targets to kill 8 false ServiceDown alerts.)

## Alternatives considered

1. **Status quo — manual `docker stop` after every deploy/reboot.** Rejected:
   reintroduces the exact friction this ADR removes (manual stop after each
   deploy); easy to forget → silent RAM regression.
2. **Delete the four service blocks from Compose.** Rejected: loses the config,
   detaches named volumes from the Compose graph, and re-adding = restoring YAML.
   Profiles keep the definition inert-but-present.
3. **Move the four to a separate non-`include:`d compose file.** Rejected: more
   restructuring than a one-line-per-service profile, and a second deploy path.
4. **`deploy.replicas: 0` / scale 0.** Rejected: hacky, non-obvious, tooling-specific.

## Consequences

**Positive:**
- `make deploy` and reboot no longer revive the four → RAM state is stable without
  manual intervention.
- Config + data volumes retained; on-demand start is one flagged command.
- No permanent false ServiceDown alert for the off HA.

**Negative / neutral:**
- **WUD won't auto-update a stopped/profiled container** (it watches running
  containers) → images for the four go stale until re-enabled; pull manually when
  promoting them back. Acceptable for unused apps.
- An operator must remember `--profile optional` to run them; the inline compose
  comment + this ADR are the reminder. Data is never lost (volumes persist).
- `homelab-docker.service` still has an `ExecStartPre=docker compose build
  paperless-ngx` — harmless (explicit-name build ignores profile gating; it builds
  but does not start the image).

**Verification (done before merge):** no non-profiled service `depends_on` the
four (only the internal `paperless-ngx → paperless-db/redis`, all in the same
profile); kopia has no dependency on them (volumes persist while stopped);
paperless is not probed. **Acceptance test at deploy:** `make deploy` must leave
the four `stopped`/absent (not `Started`).

## Revisit when

- A profiled app becomes regular-use again → drop its `profiles:` line (and re-add
  the HA blackbox target) to make it default-on.
- RAM ceiling is raised (more host memory / second node per ADR-0038) such that
  keeping them always-on costs nothing → profiles no longer needed.
- Compose `include:` + profiles interaction changes in a future Compose release
  such that profiled services leak into the default `up`.
