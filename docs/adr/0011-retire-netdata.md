# 0011 — Retire netdata; rely on Prometheus + Grafana stack

- **Status:** Accepted
- **Date:** 2026-05-16
- **Deciders:** Lucas Santana
- **Related:** ADR-0004 (drop k3s — bias toward simpler operational surface), ADR-0010 (retire fragile patterns over patch them)

## Context

`netdata` has been in a docker restart loop for weeks. The originally-recorded
root cause ("SQLite readonly DB") was wrong; re-diagnosis on 2026-05-16 showed
the actual failure mode:

```
cp: preserving times for '/etc/netdata/charts.d': Operation not permitted
cp: preserving times for '/etc/netdata/custom-plugins.d': Operation not permitted
...
```

The entrypoint's `cp -p` (preserve attributes) fails on every file in the
`netdataconfig` volume because the v2 hardening pass dropped `CAP_FOWNER` via
`cap_drop: ALL`. The volume contents are owned by UID 201 (the in-container
`netdata` user), populated in October 2025; preserving their timestamps
requires `CAP_FOWNER`, which is not in the `cap_add` list.

Meanwhile, the rest of the monitoring stack — added across the v2.x line — has
been running healthily without netdata:

- **node-exporter** (host metrics, `:9100/metrics`)
- **cadvisor** (per-container metrics, `:8080/metrics`)
- **prometheus** (scrapes both above + alertmanager + loki + blackbox)
- **grafana** (dashboards)
- **alertmanager** (rule-based alerts → healthchecks → email)
- **loki + promtail** (log aggregation)
- **gatus** (uptime + endpoint health)
- **blackbox-exporter** (external probing)
- **healthchecks** (deadman-switch / cron alerting)

Netdata's distinct value over this set is (a) 1-second resolution UI and (b)
unsupervised ML anomaly detection.

## Decision

**Remove netdata from the stack.** Rely on the existing
Prometheus + Grafana + node-exporter + cadvisor stack for monitoring; add new
Grafana dashboards on demand if a specific netdata view is missed.

Migration is small (one service block, three volumes, one homepage widget,
one gatus entry); risk-mitigation is documentation, not phased rollout.

## Alternatives considered

| Option | Rejection reason |
|---|---|
| Fix: add `CAP_FOWNER` to cap_add | 5-minute patch, but keeps a service that overlaps 90 % with node-exporter + cadvisor and brings `SYS_PTRACE` + `apparmor:unconfined`. Carrying a service that hasn't earned its keep is operational debt. |
| Empty `/etc/netdata` volume + restart (no cap change) | Avoids changing capabilities — `cp -p` to an empty dir succeeds — but still keeps the overlap and the attack surface. Same rejection as the cap fix, with worse hygiene. |
| Replace with Glances (Python alternative) | Adds a new tool just to keep a "single pane of glass." Grafana already is that pane. Net negative: more code, less integration. |
| Move netdata to a host install (apt) | Matches upstream's recommended pattern and sidesteps container perms, but breaks the "compose is the source of truth for the host" model. Provisioning a new host would require an out-of-band install step. |
| Build Grafana dashboards replicating netdata views *first*, then remove | Gold-plating. We can add dashboards on demand if a concrete view is missed. ADR-0010's lesson applies: retire first, iterate if asked. |

## Consequences

**Positive:**

- One fewer restart-looping container in `docker ps`; log noise gone.
- Drops `SYS_PTRACE`, `DAC_READ_SEARCH`, `apparmor:unconfined` from the attack
  surface (netdata was the only service requiring these).
- Three unused volumes (`netdataconfig`, `netdatalib`, `netdatacache`) freed.
- Removes the homepage widget that has shown an error state since the regression.
- One less image to track for security updates.

**Negative:**

- Lose live ML anomaly detection. Today's alerting is rule-based via
  Alertmanager → Healthchecks → email; anomalies we didn't think to alert on
  are not surfaced. In 12 months of weekly-cadence dashboard checking, no
  netdata-fired anomaly has driven an action, so the practical loss is
  hypothetical.
- Lose 1-second resolution UI. Prometheus scrapes every 15 s by default;
  Grafana visualises at the scrape resolution. Sufficient for the homelab's
  use cases (capacity planning, post-mortem triage).
- Lose a free fallback observability layer if Prometheus or Grafana break.
  Mitigation: a runbook entry documenting how to query `node-exporter:9100/metrics`
  and `cadvisor:8080/metrics` directly during outages.

**Neutral:**

- `.env.example` will retain `IMG_NETDATA` and `NETDATA_CLAIM_TOKEN` until the
  user cleans them (the file is protected by the `protect-files.sh` hook and
  must be edited by the operator). Stale but harmless.

## Implementation

Single PR against `release`:

1. Remove the `netdata:` service block from `compose/monitoring.yml`.
2. Remove `netdataconfig`, `netdatalib`, `netdatacache` from `compose/base.yml`.
3. Remove the `Netdata:` block (lines 98-105) from `config/homepage/services.yaml`.
4. Remove the `Netdata` entry from `config/gatus/config.yaml`.
5. Add a runbook section under `docs/runbooks/` (or expand the existing README)
   documenting fallback observability queries.
6. Operator removes `IMG_NETDATA=` and `NETDATA_CLAIM_TOKEN=` from server
   `.env` (and from `.env.example` in a separate, hook-approved commit).
7. On deploy: `docker compose up -d --remove-orphans` removes the container;
   `docker volume rm homelab_netdataconfig homelab_netdatalib homelab_netdatacache`
   reclaims the volumes (post-deploy).

## Revisit triggers

Re-open ADR-0011 if any of the following becomes true:

1. **Multi-host expansion.** A second physical host means per-host live UIs
   become valuable again. Netdata's parent/child topology was designed for this.
2. **Anomaly miss with consequences.** Alertmanager rules fail to catch a
   real anomaly two months running, with measurable user impact. ML-based
   detection's value would then be demonstrated.
3. **Prometheus/Grafana outage with consequences.** A documented incident
   where the absence of a fallback UI extended the outage. Mitigation runbook
   should have caught this; if not, fallback observability needs revisiting.
4. **Capacity headroom + curiosity.** CPU/RAM pressure eases, the operator
   wants richer per-second diagnostics, and the security cost of
   `apparmor:unconfined` is judged acceptable for a re-add.
5. **Upstream change.** Netdata ships a default container that no longer
   needs the capability soup (e.g., a true rootless image). The capability
   surface that drove this decision dissolves.
