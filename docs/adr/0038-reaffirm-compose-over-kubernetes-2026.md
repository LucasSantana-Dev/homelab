# ADR 0038: Reaffirm Docker Compose over Kubernetes (2026 re-evaluation) + growth trigger

- **Status:** Accepted
- **Date:** 2026-07-08
- **Deciders:** Lucas (solo operator)
- **Supersedes:** —
- **Superseded by:** —
- **Related:** [ADR-0001](./0001-compose-vs-k3s-boundary.md) (Compose vs K3s boundary, 90-day experiment), [ADR-0004](./0004-drop-k3s.md) (Drop K3s), [ADR-0002](./0002-storage-boundary.md) (storage boundary), [ADR-0003](./0003-ingress-boundary-compose-edge.md) (ingress boundary)

---

## Context

On 2026-07-08 the operator proposed migrating the homelab's containers to Kubernetes, motivated by growth of **Lucky** (a Discord bot). This ADR records the re-evaluation, because the proposal directly touches a still-standing decision (ADR-0004) and a Kubernetes migration is a big-bang subsystem replacement.

The question was researched (4 sourced web-research angles) and stress-tested via a 5-lens structured debate (architecture-fidelity, pragmatism/YAGNI, growth-fit, risk/blast-radius, operator-intent). Full plan: `.claude/plans/k8s-growth-readiness-2026-07-08.md`.

**Measured state (2026-07-08):**
- One server: Intel N100, 4 cores, **14 GB RAM**, bare metal, Ubuntu 25.04. Single node — no HA is possible regardless of orchestrator.
- **45 running containers** across 3 compose projects (homelab 31, lucky 7, lucky-staging 5) + a Roblox rig. RAM 6.1 GB used, **461 MB free** (8.8 GB available incl. reclaimable cache).
- Orchestration: docker-compose + the bespoke `homelab_manager` (deploy/restart/update/status/health/backup). Compose already declares **31 `restart: unless-stopped`, 31 resource-limit blocks, 30 healthchecks**.

**What changed since ADR-0004 dropped k3s — in the wrong direction for k8s:** RAM 24 GB → 14 GB (smaller box), containers 19 → 45 (2.4× load), usage 1.7 GB → 6.1 GB (tighter headroom). ADR-0004's revisit condition ("50+ host cluster planned / multi-node needed") is **not** met.

**Key evidence:**
- Single-node k3s control-plane overhead is ~750 MB–1.4 GB RAM; on a box with <2 GB free, etcd is starved by workload contention → the cluster (and all 45 services) goes unresponsive. Single node yields no HA. k8s' real adds (RBAC, network policies, namespaces, declarative) are not current needs; crash-recovery/limits/health are already covered by compose + `homelab_manager`.
- A growing Discord bot does not need k8s on one node: gateway sharding is mandated only at 2,500+ guilds; k8s StatefulSets matter only past ~100k guilds ("2027+ if ever"). Vertical scaling + managed Postgres covers 99%.
- Migration blast radius is severe (Lucky prod + Postgres/Redis state + Cloudflare tunnels + Tailscale + observability), effort 2–8 weeks, with a documented industry cautionary tale ($340K migration deleted after 6 months for unnecessary complexity).

## Decision

**Reaffirm ADR-0004: stay on Docker Compose. Do not migrate the homelab (or Lucky) to Kubernetes/k3s now.** Answer Lucky's growth with **trajectory instrumentation** (the `lucky_growth_gate` Prometheus rules + Grafana panels shipped here), not orchestration.

> **Correction (2026-07-08, same day):** the first draft named "managed Postgres offload" as the root-cause growth fix, assuming it would free 0.5–1 GB of host headroom. Direct measurement refuted this — Lucky's Postgres is **14 MB on disk / ~28 MiB RAM** (PostgreSQL 18.3, 66 tables, plpgsql only), and is not among the host's top-12 memory consumers (those are kopia/n8n/paperless/prometheus). Offloading it would free ~28 MB, not 0.5–1 GB. **The Postgres offload is therefore DEFERRED** — it does not address headroom, and at 26 guilds there is nothing to decouple. If headroom ever becomes the constraint, the levers are the actual top consumers, not Lucky's DB. The runbook `docs/lucky-postgres-offload-runbook.md` is retained for if/when the offload-revisit trigger below fires.

**Documented trigger to revisit Kubernetes — both must hold:**
1. A **second homelab node** is operationalized, **AND**
2. Lucky's **sustained host memory utilization > 70% for ≥ 30 consecutive days** (measured by the `lucky_growth_gate` gate).

**Separate trigger to revisit the Postgres offload:** Lucky DB > 1 GB, OR sustained PG connection/CPU pressure, OR Lucky > 500 guilds.

Single-node k3s remains explicitly unjustified (etcd-starvation cascades to all services). If someday triggered, migration uses the **strangler pattern** on a ≥2-node cluster, prod last, Lucky last — never big-bang on the prod N100.

## Alternatives considered

1. **Migrate to k3s now (single node):** Rejected. Overhead unsafe at 461 MB free; no HA; blast radius covers prod. Contradicts ADR-0004's still-valid revisit bar.
2. **Podman Quadlet / Docker Swarm / Nomad:** Deferred/rejected. Quadlet is the strongest *modern* single-node option but offers no benefit worth a 45-service rewrite today; Swarm is stagnant/compat-broken on Docker v29; Nomad is multi-node overkill.
3. **Managed Postgres offload + measure (chosen path):** Directly targets the growth bottleneck (state), frees headroom, and produces the data any future architecture decision needs.
4. **k3s learning sandbox on separate hardware (Pi/spare box):** Legitimate and prod-safe; gated on an explicit upskilling goal or a climbing trajectory. Never on the prod N100.

## Consequences

- **Positive:** No prod risk; complexity budget preserved; the real growth lever (managed DB) is pulled; a measurable, non-ideological trigger replaces "it feels like time."
- **Negative:** No k8s learning on prod (mitigated by the sandbox option); if a genuine multi-node need arrives, migration is a new-architecture effort, not intra-cluster growth.
- **Neutral:** Lucky's app metrics (guild count, latency, heap) are already instrumented; this ADR adds a resource-utilization growth gate (Prometheus rules + Grafana panels).

## References

- Plan: `.claude/plans/k8s-growth-readiness-2026-07-08.md`
- Runbook: `docs/lucky-postgres-offload-runbook.md`
- Growth-gate monitoring: `config/prometheus/alerts.yml` (group `lucky_growth_gate`), `config/grafana/provisioning/dashboards/lukbot/`
