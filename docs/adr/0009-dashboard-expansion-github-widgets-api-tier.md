# ADR 0009 — Dashboard Expansion: Tiered GitHub Integration + API Layer

**Status:** Accepted
**Date:** 2026-05-15
**Deciders:** Lucas Santana

---

## Context

The homelab dashboard (Homepage) currently shows 4 sections (Media, Storage, Apps, Infrastructure) with 13 services. It has zero visibility into GitHub repositories or project status.

Three gaps were identified:
1. No GitHub project integration — open PRs, issues, CI status are invisible from the dashboard.
2. No custom data from the homelab manager — health summaries, backup state, service counts require SSH.
3. No dedicated "Projects" view — the single-page layout mixes infra and dev concerns.

The user explicitly requested: new features, fixes on the home dashboard, more GitHub project integration, and a custom dashboard page.

**Constraints at decision time:**
- Authentik SSO is not yet live (blocks a standalone authenticated microservice).
- n8n basic auth is silently ignored in v1.0+ (blocks n8n as an aggregator until fixed).
- Homepage `customapi` widget renders key-value pairs only — not a rich component.
- Homepage supports multiple pages via `pages:` in `settings.yaml`.
- `homelab_manager` is a CLI-only tool; no HTTP server exists yet.

---

## Decision

Use a **three-tier approach**:

### Tier 1 — Immediate (effort: xs, this sprint)
Add a second Homepage tab ("Projects") using Homepage's built-in GitHub widgets:
- `github-release-tracker` per repo (Forgejo, homelab, ai-dev-toolkit, etc.)
- `github-commit-activity` for recent push activity
- No new infra. Pure YAML config in `config/homepage/`.

### Tier 2 — This month (effort: m)
Add an HTTP server mode to `homelab_manager` exposing `/health`, `/status`, and `/summary` JSON endpoints. Wire these into Homepage `customapi` widgets for live infra state without SSH.

### Tier 3 — Deferred (effort: l)
A custom web microservice (React + shadcn/ui, served behind Caddy + Authentik SSO) replacing or supplementing Homepage for the "Projects" hub. Trigger conditions:
- Authentik SSO is live (ADR pre-condition for public-facing authenticated pages).
- The `customapi` key-value display is confirmed insufficient for the desired richness.
- At least 10+ GitHub repos are active (justifies the maintenance overhead).

---

## Alternatives Considered

| Option | Verdict | Rejection reason |
|---|---|---|
| Grafana + GitHub datasource | Rejected | Grafana is a metrics dashboard, not a project hub; wrong UX; Authentik not yet wired |
| n8n aggregation polling → customapi | Deferred | n8n auth is broken in v1+; not a safe dependency until fixed |
| Homepage customapi only (no extra tab) | Partial | customapi renders key-value pairs; insufficient for rich project status; kept for Tier 2 infra metrics only |
| Custom microservice immediately | Deferred to Tier 3 | Authentik not live; maintenance overhead not yet justified; Tier 1+2 cover 80% of the need |
| Homepage single page with GitHub widgets | Rejected (layout) | Mixing infra + dev concerns in one 4-column layout produces visual noise; tab separation cleaner |

---

## Consequences

**Positive:**
- Tier 1 is zero-infra and ships in < 1 hour.
- Tier 2 adds direct homelab state without external dependencies.
- Tier 3 remains open for when the pre-conditions are met, with a clear trigger.

**Negative / trade-offs:**
- Homepage GitHub widgets require a `HOMEPAGE_GITHUB_TOKEN` env var for rate-limit headroom (15 req/hr unauthenticated vs 5000/hr authenticated). Low risk; public repos only.
- Tier 2 opens an HTTP port on the homelab manager; must be loopback-bound (`127.0.0.1`) and proxied through Caddy with Authentik forward-auth when available.
- Tier 3 is intentionally under-specified until triggers fire.

---

## Revisit When

- Authentik SSO goes live → re-evaluate Tier 3 scope.
- n8n auth is fixed → n8n aggregation becomes viable for Tier 2 alternative.
- GitHub repos grow past 10 active → custom microservice ROI improves.
- Homepage `customapi` gains richer widget types → Tier 2 scope may expand.
- ADR 0005 (media stack) pre-conditions met by 2026-05-27 → Jellyfin dashboard card.

---

## Related

- ADR 0003 — ingress boundary (Caddy + Cloudflare owns all ingress; any new HTTP service must be proxied)
- ADR 0006 — WoL shell endpoint (precedent for homelab_manager HTTP surface)
- ADR 0005 — media stack (Jellyfin card deferred to Tier 1 once conditions met)
- Backlog run: 2026-05-15 (features T8–T11 derived from this ADR)
