# ADR 0008 — Wave 4: Compose Hygiene (Dead Anchors + Image Tag Pinning)

**Status:** Accepted  
**Date:** 2026-05-14  
**Branch:** `refactor/wave4-audit-r2`  
**Closes:** Audit-deep v2 findings I1 (dead anchors) and H4 partial (image tags)

---

## Context

Audit-deep v2 (2026-05-13, score 72/100 YELLOW) surfaced two structural issues in
the `compose/` directory:

**I1 — Dead YAML anchors:** 41 anchor definitions (`&logging-defaults`,
`&healthcheck-*`, `&resources-*` and others) existed across 5 compose files but
zero `<<:` merge keys consumed them. The anchors were from an earlier design
(Wave 0) where reuse was planned but never wired. They created maintenance debt:
readers had to track whether a change to an anchor would ever take effect.

**H4 — Floating image tags (partial):** Several images used major-only or
non-existent tags as compose fallback defaults:
- `nextcloud:29-alpine` — this tag variant does not exist on Docker Hub
- `postgres:15-alpine` — resolves to latest 15.x patch, not a specific version
- `tinyauth:v5` — resolves to latest v5.x patch
- `forgejo:12` — resolves to latest v12.x (Codeberg requires auth to enumerate tags)

The remaining 5 floating tags from H4 (H5/CodeQL, H6 unvalidated input) are
separate findings with separate remediations.

---

## Decision

### I1: Remove all dead anchors

Remove the 41 anchor definitions from `compose/base.yml`, `compose/core.yml`,
`compose/apps.yml`, `compose/security.yml`, and `compose/monitoring.yml`.
Do not add merge keys to "activate" them — the logging/healthcheck/resource
blocks are already inline in every service and were never being deduplicated in
practice. Adding merge keys now would be dead complexity; removing the anchors
reduces noise.

### H4: Pin compose fallback defaults to patch-level versions

Use the `image: ${IMG_NAME:-registry/image:x.y.z}` pattern already established
in the repo. The compose fallback is the canonical pin for dev/staging; production
can override via `.env`. Specific decisions:

| Image | Before | After | Rationale |
|---|---|---|---|
| nextcloud | `nextcloud:29-alpine` | `nextcloud:29-fpm-alpine` | `:29-alpine` does not exist; `fpm-alpine` is the correct Alpine variant |
| postgres (×2) | `postgres:15-alpine` | `postgres:15.17-alpine` | Pin to latest known patch |
| tinyauth | `tinyauth:v5` | `tinyauth:v5.0.7` | Pin to latest confirmed patch via GHCR |
| forgejo | `forgejo:12` | unchanged | Codeberg requires auth to list tags; plan stop condition applied — do not block PR |

---

## Alternatives Considered

**Re-activate anchors with merge keys:** Would reduce inline repetition for logging
and resource blocks. Rejected because: (1) merge keys interact poorly with Docker
Compose's own merging semantics in multi-file `-f` setups; (2) the services already
have consistent inline blocks that work; (3) adding merge keys would be a net
complexity increase, not a reduction.

**Use SHA digests for all image pins:** More reproducible but requires a weekly
rotation workflow and breaks local pull workflows without a registry mirror.
Deferred — the `.env` / `.env.example` production override mechanism is the right
place for SHA pinning; compose fallbacks are for `dev` and `make up` convenience.

**Pin forgejo at patch level:** Required Codeberg API auth to enumerate tags. Hit
the 48h stop condition defined in the plan. forgejo releases are infrequent (monthly)
and the major-only tag already rejects arbitrary patches; risk is low.

---

## Consequences

**Positive:**
- Compose files are shorter and easier to read
- No silent "anchor defined but never used" footguns
- 3 of 4 floating H4 tags now resolve to a known version at `docker-compose pull`
- nextcloud tag corrected — `docker pull nextcloud:29-alpine` was silently failing

**Neutral:**
- The inline logging/resource blocks remain repeated; a future ADR can address this
  with a different dedup strategy (e.g., YAML processor pre-step, or full migration
  to Docker Compose `include:`)
- `.env.example` still contains `IMG_NEXTCLOUD=nextcloud:latest@sha256:...` which
  uses `latest`, not `29-fpm-alpine`. That file is protected by `protect-files.sh`
  and intentionally uses a prod SHA override pattern; the compose fallback pin is
  authoritative for dev.

**Negative:**
- forgejo remains at `12` (major-only). Track for pinning in next audit cycle.

---

## Revisit When

- forgejo publishes a v12.x.y tag that's discoverable without auth (or when Codeberg
  API credentials are available to the CI pipeline)
- Any `nextcloud:29-fpm-alpine` patch (29.x.y) is released and should be tracked
- Audit-deep v3 re-scores — expect I1 and partial H4 to be CLOSED, raising score
  above current 72/100

---

## Related

- ADR 0007 — homelab-manager clients package (Wave 3)
- Audit-deep v2 report: `memory/audit_deep_homelab_2026-05-13_v2.md`
- Plan: `.claude/plans/wave4-audit-remediation-2026-05-14.md`
- Commits: `707be99` (I1), `4fca85b` (H4)
