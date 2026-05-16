# Spec: Homepage "Projects" Tab — GitHub Release + Commit Widgets

**Created:** 2026-05-15
**ADR:** docs/adr/0009-dashboard-expansion-github-widgets-api-tier.md (Tier 1)
**Effort:** s (1–4h)
**Severity:** medium

---

## Goal

Add a second Homepage tab ("Projects") using built-in GitHub widgets to surface release and commit activity for the homelab's active repositories — zero new infra, pure YAML config change.

## Context

- `config/homepage/settings.yaml` has no `pages:` key — Homepage is single-tab today.
- `config/homepage/services.yaml` has 4 sections (Media, Storage, Apps, Infrastructure); no GitHub integration.
- Homepage v1.0.3 supports `github-releases` and `github-commit-activity` widgets natively.
- Without `HOMEPAGE_GITHUB_TOKEN`, GitHub API rate limit is 15 req/hr (unauthenticated); 5000/hr with token.
- ADR 0009 identified Tier 1 as the highest-ROI path: no new services, ships in < 1 hour.

## Approach

1. Add `pages:` to `config/homepage/settings.yaml` to enable multi-tab layout. Existing sections stay on "Home" tab; new "Projects" tab added.
2. Create `config/homepage/services-projects.yaml` (or add a new page group in `services.yaml`) with GitHub widget entries for:
   - `LucasSantana-Dev/homelab` — release tracker + commit activity
   - `LucasSantana-Dev/ai-dev-toolkit` — release tracker + commit activity
   - `LucasSantana-Dev/forgejo` (or Forgejo instance) — release tracker
   - Additional repos as needed (homelab_manager, etc.)
3. Add `HOMEPAGE_GITHUB_TOKEN` env var to `compose/core.yml` homepage service and `.env.example`.
4. Configure `config/homepage/widgets.yaml` or page-level widgets if Homepage v1.0.3 supports per-page widgets.
5. Test: navigate to dashboard, confirm "Projects" tab visible, GitHub widget data loads without rate-limit errors.

## Verification

- [ ] Homepage loads with two tabs: "Home" (existing 4 sections intact) and "Projects"
- [ ] "Projects" tab shows `github-releases` widget for ≥ 2 repos with correct latest release tag
- [ ] "Projects" tab shows `github-commit-activity` widget for ≥ 2 repos
- [ ] No 429 rate-limit errors in homepage container logs when `HOMEPAGE_GITHUB_TOKEN` is set
- [ ] `.env.example` documents `HOMEPAGE_GITHUB_TOKEN` with a comment explaining the rate-limit reason
- [ ] Existing "Home" tab sections are unaffected (smoke-test all 13 service cards)

## Out of scope

- Custom React dashboard (Tier 3 — deferred until Authentik live)
- homelab_manager API integration (Tier 2 — separate spec)
- PR/issue status widgets (requires richer widget type than Homepage currently provides)
