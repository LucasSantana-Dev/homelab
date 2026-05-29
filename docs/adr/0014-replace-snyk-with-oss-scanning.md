# ADR-0014: Replace Snyk (SaaS) with the existing OSS scanning stack

- **Status:** Accepted
- **Date:** 2026-05-28
- **Supersedes:** the `.snyk` policy added in #140 (v2.4.2)

## Context

The repo carried two Snyk surfaces:

1. A `.snyk` policy file + a `snyk/` entry in `dockerfiles/homelab-manager/.dockerignore`.
2. The **Snyk GitHub App** integration, which posts two PR checks: `security/snyk`
   (dependency scan) and `code/snyk` (Snyk Code / SAST).

`code/snyk` had been **failing on every PR** with "Code test limit reached" — a
monthly-quota exhaustion, not a real finding. It is non-required, so it never
blocked merges, but it produced a red check on every PR (alert fatigue). An
`audit-deep` pass (2026-05-28) flagged it, and confirmed Snyk's coverage is
**fully redundant** with free/OSS tooling already running in `ci.yml`:

| Snyk capability | Already covered by (free/OSS) |
|---|---|
| SAST (`code/snyk`) | **CodeQL** (GitHub default-setup) |
| Dependency CVEs (`security/snyk`) | **Trivy** `fs` scan + **Socket Security** |
| Container/image CVEs | **Trivy** image scan + compose-config scan |
| Secrets | **gitleaks** (OSS) + GitGuardian |

Snyk was not referenced by any workflow YAML — it ran purely as an external App.
It added a paid-SaaS dependency and per-PR noise without unique coverage.

## Decision

Remove Snyk entirely and rely on the existing OSS/free stack.

- Delete `.snyk` and the `snyk/` `.dockerignore` entry.
- Migrate the intent of the `.snyk` path exclusions (`archive/**`,
  `dockerfiles/paperless-ngx/**`) into the Trivy `fs` step via
  `skip-dirs: 'archive,dockerfiles/paperless-ngx'`, so removal does not surface
  reverted-k3s history (ADR-0004) or upstream-owned paperless-ngx base-image CVEs
  as noise.
- **Operator action (outside this repo):** uninstall the Snyk GitHub App from the
  repository so the `security/snyk` and `code/snyk` check-runs stop appearing.

## Alternatives considered

1. **Disable only Snyk Code, keep `security/snyk`** (the lighter audit suggestion)
   — rejected: `security/snyk` is also redundant with Trivy + Socket, and keeping
   the App keeps the SaaS dependency and the quota-prone account.
2. **Keep Snyk, raise the plan tier** — rejected: pays for coverage already
   provided free; violates the OSS-over-SaaS preference.
3. **Add Semgrep OSS to replace CodeQL too** — deferred: CodeQL default-setup is
   free and already active; Semgrep would be additive, not required. Revisit only
   if CodeQL coverage proves insufficient.

## Consequences

- One fewer SaaS integration; no more per-PR `code/snyk` quota-fail noise.
- SAST/dep/container/secret coverage unchanged in substance (CodeQL + Trivy +
  Socket + gitleaks).
- Path-exclusion intent now lives in `ci.yml` (Trivy `skip-dirs`) — version-
  controlled and visible in the workflow, rather than in a Snyk-specific file.
- **Note:** Socket Security and GitGuardian are also free-tier SaaS (not OSS).
  They are retained for now; replacing them (e.g. gitleaks-only for secrets) is a
  separate decision, not in scope here.

## Revisit when

- CodeQL default-setup is disabled or stops covering a language in use.
- A dependency/container CVE class is found that Trivy + Socket both miss.
- The team wants a fully OSS-only posture (then reconsider Socket + GitGuardian).
