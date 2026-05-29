# 0012 — Polish existing Grafana stack; defer ML anomaly detection

- **Status:** Accepted
- **Date:** 2026-05-16
- **Deciders:** Lucas Santana
- **Related:** ADR-0011 (retire netdata), ADR-0010 (retire fragile patterns over patch them)

## Context

ADR-0011 retired netdata and committed to the existing
Prometheus + Grafana + node-exporter + cadvisor stack. That ADR explicitly
deferred the "what to actually configure on Grafana" question — it accepted
that new dashboards would be added "on demand."

Working state of the stack post-0011:

- `observability/grafana/provisioning/dashboards/` contains two thin
  custom dashboards (`containers.json`, `docker-host.json`).
- `observability/prometheus/prometheus.yml` has zero alert rules
  (`rule_files: []`).
- No fallback observability runbook exists; if Prometheus or Grafana go
  down, the operator has no documented way to query the underlying
  exporters directly.

Three distinct gaps netdata previously filled, now uncovered:

1. **1-second resolution UI.** Prometheus scrapes every 15s. Unrecoverable
   without scrape-interval changes that materially increase TSDB cost.
2. **Unsupervised ML anomaly detection.** Netdata trained 18 models per
   metric at the edge. Grafana ecosystem alternatives
   (`grafana/promql-anomaly-detection` z-score recording rules, Grafana ML
   plugin DBSCAN/MAD) require manual band tuning per metric.
3. **Auto-discovered per-container deep-dive.** Netdata had a built-in
   per-container drill-down. Grafana requires hand-curated dashboards.

## Decision

**Polish the existing stack only — no ML layer, no new agents.** Specifically:

1. Import community Grafana dashboards:
   - **1860** (Node Exporter Full)
   - **13112** or **21154** (combined cAdvisor + node-exporter)
   - **19792** (cAdvisor deep-dive)
2. Replace or archive the skeletal `containers.json` and `docker-host.json`.
3. Author `observability/prometheus/alert_rules.yml` with 5 rules:
   high CPU sustained, memory pressure, container restart loop, disk fill,
   scrape target down. Wire into `prometheus.yml`.
4. Verify the alertmanager → healthchecks → email pipeline end-to-end with
   a synthetic alert.
5. Write `docs/runbooks/observability-fallback.md`: exact `curl` recipes
   against `node-exporter:9100/metrics` and `cadvisor:8080/metrics` for
   when Prometheus/Grafana are unavailable.
6. Execute the runbook fallback once during the pilot; capture known-good
   output as the baseline.

**Accept gaps 1, 2, and 3.** Document them in the runbook so future-Lucas
knows they're known.

## Alternatives considered

| Option | Rejection reason |
|---|---|
| Add `grafana/promql-anomaly-detection` z-score recording rules + alertmanager rules on band-cross | Z-score bands require quarterly retuning as traffic envelope shifts (Lucky band-nights, Craftvaria modding sessions cause non-stationary baselines). On a single-operator homelab, ongoing tuning will degrade to alarm fatigue within 3 months, and the rules will be silenced — net negative. Revisit when traffic stabilises or a second operator joins. |
| Add Grafana ML plugin (no-code DBSCAN/MAD) | Same baseline-drift problem as above. Adds a Grafana plugin to maintain. |
| Add Grafana Alloy as unified collector (replace node-exporter, eventually promtail) | Alloy's value (one config, OTel-native, agent consolidation) is real, but at 5–10 monitored containers on a single host there is no agent sprawl to consolidate. Defer until 20+ containers or multi-host. |
| Add Beszel as secondary lightweight UI | Adds a UI-only tool ADR-0011 just retired. Violates the retire-and-simplify ethos. The "I want a single pane of glass" need is met by Grafana once the dashboards above are imported. |
| Build custom dashboards tailored to homelab services | Gold-plating. Community dashboards (1860, 13112/21154, 19792) cover 80–90% of what custom builds would. Add custom dashboards on demand if a specific view is missed. |
| Keep `containers.json` + `docker-host.json` and just add rules + runbook | The current custom dashboards are skeletal and predate the full stack. Replacing them with community-maintained dashboards is lower-effort than maintaining the bespoke ones. |

## Consequences

**Positive:**

- Closes the largest visible gap (skeletal dashboards) with zero new
  containers and zero new config languages.
- Operationally durable: dashboards 1860 / 13112 / 19792 are maintained
  by the community and survive Prometheus version bumps without operator
  effort.
- Alert rules give first-line "something is wrong" signal that didn't
  exist before. Healthchecks deadman-switch already runs, so wiring is
  thin.
- Runbook fallback creates a documented degraded-mode operating procedure
  the homelab has never had. Future Prometheus outage no longer means
  flying blind.
- No new query language, plugin, or agent surface to maintain.
- Migration friction to VictoriaMetrics or Mimir later remains near zero
  (scrape configs and rules are Prometheus-standard).

**Negative:**

- Anomalies not covered by the 5 alert rules will not surface. The
  operator must explicitly add a rule when a new failure mode is
  identified. (Same posture as before netdata — netdata's ML rarely
  drove actions in practice.)
- 1-second resolution remains lost.
- Per-container drill-down requires clicking through dashboards rather
  than netdata's auto-routed UI. Acceptable for a 5–10 container scale.

**Neutral:**

- The Lucky-observability work in PR #135 (separate track) will need to
  fit its custom dashboard alongside the community-imported set. No
  conflict expected — different file names.

## Implementation

Single PR `feat/observability-polish` against `release`, after #146
(retire-netdata) merges. Effort ~2h. Rollback is `git revert`.

Phases inside the PR:

1. Import + commit the three community dashboards.
2. Archive (or delete) the two skeletal custom dashboards.
3. Author and commit `alert_rules.yml`; reference from `prometheus.yml`.
4. Author the fallback runbook.
5. End-to-end synthetic-alert test + runbook fallback test; capture
   output, paste into the runbook as "known good baseline."

## Revisit triggers

Re-open ADR-0012 if any of the following becomes true:

1. **Traffic stabilises into a predictable envelope.** Lucky moves to a
   server with constant load patterns; Craftvaria daily-active is steady.
   Z-score bands become tractable; revisit Option E (add ML rules).
2. **Container count crosses ~20 or a second host is added.** Agent
   consolidation (Grafana Alloy) starts paying for itself; revisit
   Option B.
3. **Prometheus outage causes an actual incident.** The fallback runbook
   either saves the day (reinforces this decision) or proves
   insufficient (need a secondary always-on observability layer; revisit
   the Beszel option or a netdata-fixed hybrid).
4. **Two consecutive months of alertmanager rules failing to catch a
   real anomaly with user impact.** The rule-based approach has missed
   the threshold; ML anomaly detection's value becomes demonstrated;
   revisit Option E.
5. **Operator team grows.** A second person owning alert tuning makes
   the ongoing-maintenance cost of ML rules viable; revisit Option E.
