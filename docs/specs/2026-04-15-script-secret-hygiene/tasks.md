# Tasks — script-secret-hygiene

## Live code

- [x] Rotate `DB_PASSWORD` (lucky-postgres) — superseded by full refactor to `.env`-sourced creds in PR #18.
- [x] Refactor `recover-lucky-db.sh` to source `.env` (PR #18, commit `b32f8ba`).
- [x] Refactor `update-containers.sh` to source `.env` — `FORGE_MCP_*` and other creds now use `${VAR:-}` with `.env` fallback.
- [ ] Delete dead `FORGE_MCP_*` interpolation-guard block from `update-containers.sh:15-59` now that `compose/forge-space.yml` is gone (PR #43).

## Rotation

- [ ] Generate new Lucky DB password (`openssl rand -base64 32`).
- [ ] Update `LUCKY_DB_PASSWORD` in `~/homelab/.env` on homelab host.
- [ ] Restart `lucky-postgres` container.
- [ ] Run `scripts/maintenance/recover-lucky-db.sh --dry-run` (or minimal invocation) to confirm new credential works.

## History

- [ ] Decide scrub vs. risk-accept (see spec §3).
- [ ] If scrub: run `scripts/security/pre-release-checkpoint.sh`, then `scripts/security/rewrite-history.sh`, then force-push per `docs/public-release-hardening.md` §4.
- [ ] If risk-accept: add dated entry to `docs/secrets.md` explaining exposure window (2025-09-29 → 2026-04-16) and why rotation alone is sufficient (dev-grade password, Tailscale-only network path, no evidence of abuse).

## Prevention

- [ ] Add gitleaks rule for inline shell `VAR="secret"` pattern to `.gitleaks.toml`.
- [ ] Test rule against pre-#18 revision (must fire on `recover-lucky-db.sh` at `b32f8ba~1`).
- [ ] Add allowlist entries for known non-secret defaults (`test_password_123` fixtures in CI workflows, `.env.example` placeholder keys).

## Close-out

- [ ] Update this spec's frontmatter: `status: shipped`, `shipped: YYYY-MM-DD`, `pr: <merged-PR-URL>`.
- [ ] Move spec entry in `docs/roadmap.md` from "Next (proposed)" to "Recently shipped".
- [ ] Add `CHANGELOG.md` entry under `[Unreleased] ### Security`.
