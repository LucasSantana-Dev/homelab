# ADR-0018: Healthcheck probes must use a binary the image actually ships

- **Status:** Accepted
- **Date:** 2026-05-30

## Context

Nine containers have sat `running/unhealthy` — chronically, firing daily on the
`autonomous-agent` Discord channel:

- **kopia** (fixed in #164: the image ships no `wget`, so the `CMD-SHELL wget`
  probe could never pass)
- **prometheus, node-exporter, whats-up-docker, homepage** — `curl --fail …`
  against images that ship `wget` (busybox) but **not** `curl`
- **homepage** additionally probed `localhost` (resolves to `::1`/IPv6) while the
  app binds IPv4 only
- **stremio-server** — `curl …/manifest.json` returns 404 (wrong path; `/`
  returns 307)
- **promtail** (ships no curl/wget/nc/python) and **portainer** (scratch image,
  no shell at all) — *no* in-container probe is possible
- **healthchecks** — a genuine HTTP 500 (SQLite DB path bug) on top of a broken
  `wget` probe

Every one was a **false positive**: the services were up; the probe binary
simply wasn't in the image, so the check could never execute (`exec: "curl":
executable file not found in $PATH`).

This is the same root cause **recurring** (kopia on 2026-05-28, then eight more
on 2026-05-30 — ≥2× within 14 days), which triggers the operator rule "force an
ADR + prevention rule on recurrence regardless of severity."

A permanently-failing healthcheck is **worse than no healthcheck**: it produces
daily alert fatigue *and* blinds monitoring — a container that goes genuinely
unhealthy looks identical to the chronic noise.

## Decision

A container `healthcheck.test` must use one of:

1. **A binary verified present in that image.** Confirm with
   `docker exec <container> command -v <tool>` before committing. Images differ:
   `prom/*` and node/alpine images ship **busybox `wget`**, not `curl`;
   `grafana/grafana` ships `curl`; many ship neither.
2. **The application runtime already in the image** — e.g. `python3 -c "import
   urllib.request; urllib.request.urlopen(...)"` (healthchecks), `node -e
   "http.get(...)"` (lucky-bot).
3. **`healthcheck: disable: true`** for distroless/scratch images that ship no
   usable probe tool (gatus, loki, promtail, portainer). These are then monitored
   **externally** via `blackbox-exporter` (config/blackbox), which probes the
   published port over the network without needing a tool inside the container.

Additional rules:

- Probe **`127.0.0.1`**, not `localhost`, to avoid `::1`/IPv6 when the app binds
  IPv4 only.
- The probe should fail on application errors, not just connection refusal (the
  python3 urllib check correctly fails on the healthchecks HTTP 500).

**Prevention (follow-up):** add a CI lint that parses `compose/*.yml`
healthchecks and flags `curl`/`wget` probes targeting images known not to ship
them. Until that lands, this ADR is the convention.

## Alternatives considered

- **Bake `curl`/`wget` into every image** — rejected: bloats images, fights
  upstream minimal/distroless choices, breaks on rebuilds.
- **Accept the chronic "unhealthy" noise** — rejected: blinds monitoring and
  trains the operator to ignore the alert that matters.
- **Universal TCP/`nc` probes** — rejected: many minimal images lack `nc` too,
  and a TCP-connect can't catch app-level failures like the healthchecks 500.

## Consequences

- (+) Monitoring signal restored; `unhealthy` once again means *something is
  actually wrong*.
- (+) Recurrence rule satisfied; the convention is written down where future
  agents and CI will find it.
- (−) Per-image probe choice stays manual until the CI lint is implemented.
- (~) Distroless services (gatus, loki, promtail, portainer) have **no
  in-container** liveness check; they depend on external blackbox probes, which
  must be added as targets (tracked as a follow-up; promtail/portainer targets
  are TODO).

## Revisit when

- The CI healthcheck-lint is implemented → this becomes enforced, not advisory.
- The blackbox-exporter targets for the disabled-probe services are added →
  remove the "no liveness check" caveat above.
- A new image class needs a probe strategy not covered here.
