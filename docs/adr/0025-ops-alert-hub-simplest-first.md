# ADR-0025: Ops alert hub — Alertmanager-direct + n8n aggregation; defer the LLM layer

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** Lucas (solo operator)
**Relates:** [[ADR-0023]] (deploy-drift observability), [[ADR-0024]] (k3s decommission). Supersedes the initial "n8n + hermes does everything" design reached in a grill-with-options session.

## Context

The question was "what's worth automating with n8n + a 'hermes' agent across my projects?" A `grill-with-options` session converged on an ambitious **ops alert hub**: hermes (running on the existing `agent-box` container) would dedupe + severity-triage + enrich + propose-remediate alerts from Prometheus/Alertmanager + Sentry + healthchecks + WUD, with n8n as the router.

A `research-and-decide` pass then challenged that design and **two facts flipped it**:

1. **Alertmanager already solves dedupe/triage/routing.** `config/alertmanager/alertmanager.yml` has `group_by: [alertname, severity]`, per-severity routes with `group_wait/group_interval/repeat_interval`, and `inhibit_rules:` (cascading-storm suppression). An LLM "deduper" in n8n would reinvent — worse, slower, costlier — what Alertmanager is purpose-built for.
2. **Measured demand is low and self-diagnosing.** Prometheus alert history (identical over 7d and 30d) shows **10 distinct firing alert types**, *all* resource/service: `Critical/High {CPU,Memory}`, `HighLoadAverage`, `Critical/Low DiskSpace`, `ServiceDown`, `LuckyBackendDown`, `LuckyBotHeapHigh`. These are self-diagnosing ("disk 90% → prune", "container down → restart"), and several were the *noise we just fixed this session*. LLM "enrichment" to explain "disk is full" adds ~nothing.

The `decision-critic` (artifact-only) returned **NEEDS_REVISION**, flagging the new n8n hop as a single-point-of-failure in the alert path (today Alertmanager → Discord is direct) and the LLM layer as over-built for unmeasured, self-diagnosing alerts. The orchestrator verified its load-bearing claims (the Alertmanager config, the alert-frequency query).

## Decision

Ship the **simplest design that delivers the core value, keeping alert reliability intact; defer the LLM/agent layer until measured demand justifies it.**

1. **Alertmanager → Discord stays DIRECT for Prometheus alerts.** No n8n in the fire path (eliminates the SPOF). Invest the effort in **richer Alertmanager Discord templates** instead: affected service, severity, a runbook link, and a Loki query link — this *is* the "enrichment" for all 10 known alert types, with zero LLM.
2. **n8n is a NON-critical cross-source aggregator** for the genuine gap: Sentry + healthchecks + WUD (which are not Prometheus alerts) → one normalized `#digest` feed. If n8n is down, Prometheus alerts are unaffected.
3. **DEFER hermes / LLM enrichment.** Revisit only when an alert class appears that templates demonstrably cannot explain.
4. **DEFER auto/propose-remediation.** Revisit later as an explicit operator-triggered n8n `/remedy` listener (with a pre-execution state-check), once the simple feed has proven out.

## Alternatives considered

1. **n8n + hermes full hub (the grilled design)** — rejected: reinvents Alertmanager's dedupe/triage; routes critical alerts through a new SPOF; LLM cost/latency for self-diagnosing alerts; two-system (n8n↔agent-box) drift. Over-built for a solo operator with ~10 stable, obvious alert types.
2. **Do nothing (status quo: 4 separate Discord webhooks)** — rejected: the cross-source fragmentation (Prometheus vs Sentry vs healthchecks vs WUD in separate places) is a real, cheap-to-fix annoyance.
3. **Alerta / Karma aggregation dashboard** — rejected: another always-on service to run for a UI the operator would rarely open; Discord is already the surface.
4. **Robusta-style auto-remediation** — rejected: built for Kubernetes, which was just decommissioned ([[ADR-0024]]).

## Consequences

**Positive:** keeps battle-tested Alertmanager→Discord reliability; delivers the two real wins (richer templates + one cross-source feed) in ~2 hours; zero LLM cost/latency; no new critical-path dependency; nothing to roll back if n8n misbehaves.

**Negative:** no automated remediation yet (fixes stay manual); no LLM "diagnosis" (fine — the alerts self-diagnose); a small amount of Alertmanager-template work.

**Neutral:** `agent-box` and n8n keep running as-is; this adds n8n workflows + Alertmanager templates, not infrastructure.

## Revisit when

- A **new class of alerts** appears that Alertmanager templates + a Loki link genuinely cannot make actionable (then: pilot hermes enrichment on *that class only*).
- **Distinct incident diversity grows** past ~20 types or incidents become non-self-diagnosing (e.g. app-logic errors needing correlation across Loki/Sentry/deploys).
- **Repetitive manual remediation** (prune/restart) becomes frequent enough to be worth an operator-triggered `/remedy` listener — and only with a pre-execution state-check and a propose→approve gate ([[ADR-0024]]-style caution).
- If hermes is ever added to the alert path, it MUST have a fallback (enrichment-unavailable → post the raw alert) and never sit in front of the critical Alertmanager→Discord route.

## Adoption plan (phased)

- **Phase 1 (now, ~1h):** enrich Alertmanager Discord templates — service, severity, runbook URL, Loki query link — for the 10 known alert types. Verify Prometheus alerts still reach Discord directly.
- **Phase 2 (~1h):** n8n webhook receiver aggregating Sentry + healthchecks + WUD → `#digest` (with a daily WUD rollup). Confirm n8n being down does not affect Prometheus alerts.
- **Phase 3 (deferred):** hermes enrichment — only for an alert class templates can't cover; with the fallback above.
- **Phase 4 (deferred):** operator-triggered `/remedy` listener for repetitive fixes, propose→approve + state-check.
