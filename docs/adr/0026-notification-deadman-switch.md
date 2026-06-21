# ADR-0026: Catch silent notification failure with a dead-man-switch, not just a metric

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** Lucas (solo operator)
**Relates:** [[ADR-0025]] (ops alert hub — whose entire value depends on delivery), [[ADR-0023]] (deploy-drift observability). Prompted by #296 (dead Alertmanager webhook) + #298 (mis-wired WUD).

## Context

Two Discord notification paths were found **silently dead** this session: the Alertmanager webhook returns `404 Unknown Webhook` (#296), and WUD was wired to an env var WUD ignores (#298). In both cases delivery failed with **zero detection** — the alert/observability stack was blind.

The damning evidence: Prometheus already scrapes Alertmanager, and `alertmanager_notifications_total{integration="discord"}` = **608** with `..._failed_total` = **608** — i.e. **100% of Alertmanager's Discord deliveries have failed**, and **nothing alerted on it**. The data to catch this existed the whole time; no rule consumed it.

A `decision-critic` review (NEEDS_REVISION) flipped the obvious fix. Alerting on `notifications_failed`:
- only sees **Alertmanager's** deliveries — not WUD, n8n, or healthchecks' own paths (a false-safety illusion if treated as "delivery is monitored");
- has a **circular dependency** — if Alertmanager dies, the metric goes stale and the meta-alert can't route (the watcher depends on the watched);
- only increments **when a real alert fires** — verified: `increase[15m]=0` with 0 alerts firing. So a dead webhook is invisible until the first real fire alarm fails — too late.

## Decision

Adopt the canonical **Watchdog + Dead-Man-Switch** pattern as the **primary** defense; keep the metric rule as a **secondary** signal. Deliberately route every meta-alert through a **non-Discord** channel (Discord is the thing that dies).

1. **Watchdog (always-firing) alert** — `expr: vector(1)`, label `severity: none`, that is *always* firing.
2. **Alertmanager routes the Watchdog to a healthchecks.io ping URL** (a `webhook_configs` receiver hitting the check's ping endpoint) at a steady interval — constant test traffic through the pipeline.
3. **healthchecks.io dead-man-switch** — a check expecting that ping every N minutes. If pings **stop** (Prometheus down, Alertmanager down, or routing broken), healthchecks alarms **via its own channel (email — now working, #264)**. No circular dependency: delivery is healthchecks' job, not Alertmanager's.
4. **Secondary:** a Prometheus rule `increase(alertmanager_notifications_failed_total[10m]) > 0` (critical) routed to the **non-Discord** receiver — catches a Discord-webhook-specific failure while the pipeline is up. Routing the Watchdog through Discord too makes this proactive (constant traffic to fail on).
5. **WUD / n8n digest are explicitly OUT of scope** — they deliver via paths Alertmanager can't see. They are *non-critical* (missing a container-update ping ≠ missing a fire alarm). Documented as a known gap (no false safety); add per-source heartbeats only if they become critical.

Do **not** adopt a Discord bot, ntfy, Apprise, or Gotify — they add a service and still need self-monitoring; the existing webhooks plus a dead-man-switch cover the critical path.

## Alternatives considered

1. **Metric-rule self-monitoring as primary** — rejected (the critic's flip): Alertmanager-only visibility, circular dependency, fires only on real-alert traffic. Demoted to secondary.
2. **Discord bot (token) instead of webhooks** — rejected: tokens are more durable than webhooks but the path can still break and still needs monitoring; bigger change for a partial fix.
3. **Notification abstraction (ntfy/Apprise/Gotify)** — rejected: a new always-on service; still needs a dead-man-switch; over-built for a solo operator.
4. **Synthetic webhook probe (periodic test POST to Discord)** — rejected: spams the channel with test messages; the Watchdog-through-Discord variant achieves the same proactivity without extra spam (the Watchdog is silenced/low-noise).
5. **Status quo (webhooks, no monitoring)** — rejected: it is exactly the silent failure we hit.

## Consequences

**Positive:** catches whole-pipeline death proactively and the Discord-specific case; **works right now despite the dead webhook (#296)** because it routes via email/healthchecks; ~one healthchecks check + one Alertmanager receiver + two small rules; no new infrastructure.

**Negative:** WUD/n8n remain unmonitored (accepted, documented); email is the meta-channel and is itself a delivery path that can degrade (mitigated: healthchecks.io can fan out to multiple channels; revisit if it proves unreliable).

**Neutral:** depends on the healthchecks.io dead-man-switch + email (#264) both staying healthy — but that chain is independent of the Discord failure mode, which is the point.

## Revisit when

- **WUD or n8n notifications become critical** → add a per-source heartbeat (containerized → ping healthchecks on completion).
- **The email meta-channel proves unreliable** (spam, cred rotation, relay down) → add a second non-Discord channel to the healthchecks alarm (e.g. ntfy push), or a second dead-man-switch provider.
- **Alert volume grows** such that the always-firing Watchdog's noise matters → tune its route to a silent/low-interval receiver.

## Adoption plan (phased)

- **Phase 1 (now):** the healthchecks dead-man-switch — create the check, add the Alertmanager `webhook_configs` receiver pinging it, add the always-firing Watchdog rule, route Watchdog → healthchecks receiver. Verify: stop Alertmanager → the check goes down → email arrives.
- **Phase 2:** the `alertmanager_notifications_failed_total` rule → non-Discord receiver; route the Watchdog through Discord too for proactive webhook-death detection. Verify against the live 608-failure signal.
- **Deferred:** per-source WUD/n8n heartbeats (only if they become critical).
