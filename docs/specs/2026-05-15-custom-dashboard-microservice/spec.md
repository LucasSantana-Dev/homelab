# Spec: Custom Web Dashboard Microservice (Tier 3 — Deferred)

**Created:** 2026-05-15
**ADR:** docs/adr/0009-dashboard-expansion-github-widgets-api-tier.md (Tier 3)
**Effort:** l (>2d)
**Severity:** low
**Status:** DEFERRED — do not implement until trigger conditions are met

---

## Goal

A custom React + shadcn/ui web microservice serving as a rich "Projects" hub — replacing or supplementing Homepage for developer-facing views, served behind Caddy + Authentik SSO.

## Trigger conditions (ALL must be true before starting)

1. **Authentik SSO is live** — required for authenticated public-facing pages.
2. **Homepage `customapi` key-value display confirmed insufficient** — rich components (PR status tables, CI badge grids, commit timelines) exceed what `customapi` can render.
3. **≥ 10 active GitHub repos** — justifies the maintenance overhead of a custom frontend.

Current state (2026-05-15): none of these conditions are met.

## Context

- Homepage `customapi` renders key-value pairs only — insufficient for rich project hub UX.
- Authentik SSO is not yet deployed — any public-facing authenticated page is blocked.
- Tier 1 (GitHub widgets) and Tier 2 (homelab_manager HTTP API) cover ~80% of the need at far lower cost.
- ADR 0009 explicitly defers Tier 3 and documents the trigger conditions.

## Intended scope (when triggers fire)

- React + Vite + shadcn/ui frontend
- Served as a Docker container behind Caddy reverse proxy
- Authentik SSO via forward-auth (consistent with ADR 0003 ingress boundary)
- Data sources:
  - GitHub API (PRs, issues, CI status) via `HOMEPAGE_GITHUB_TOKEN` or a dedicated fine-grained PAT
  - homelab_manager HTTP API (Tier 2 endpoint) for infra state
  - Gatus API for uptime data
- Views (initial):
  - Repository list with release + CI status per repo
  - Open PRs and issues across repos
  - Homelab service health summary

## Verification (when implemented)

- [ ] App builds without errors (`npm run build`)
- [ ] Caddy route configured with Authentik forward-auth middleware
- [ ] Unauthenticated requests redirect to Authentik login
- [ ] Authenticated users see the Projects hub with data from ≥ 2 repos
- [ ] homelab_manager `/summary` data rendered in service health view
- [ ] Mobile-responsive layout

## Notes

This spec is intentionally under-specified. Full requirements should be drafted when trigger conditions fire and the Tier 1 + Tier 2 experience reveals remaining gaps.
