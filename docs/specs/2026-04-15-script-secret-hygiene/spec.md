---
status: in-progress
created: 2026-04-15
updated: 2026-04-21
owner: lucassantana
pr:
tags: security,audit-p0
---

# script-secret-hygiene

## Goal

Eliminate plaintext credentials from tracked scripts, rotate any already-leaked values, and scrub historical commits where exposure is confirmed in a public repo.

## Context

Audit [`docs/audit/README.md`](../../audit/README.md) P0 #1 flagged three plaintext-secret locations:

- `scripts/maintenance/recover-lucky-db.sh:9` → `DB_PASSWORD="discordbot123"` (Lucky PostgreSQL).
- `scripts/maintenance/update-containers.sh:18,19,32` → `FORGE_MCP_{BASIC_AUTH,ADMIN}_PASSWORD` defaults embedded inline.

Live-code state on 2026-04-21:

- **recover-lucky-db.sh is fixed.** PR [#18](https://github.com/LucasSantana-Dev/homelab/pull/18) (commit `b32f8ba`) sources `LUCKY_DB_{NAME,USER,PASSWORD,CONTAINER}` from `.env` and aborts early if `LUCKY_DB_PASSWORD` is unset. `.env.example` documents the keys; `.env` is gitignored.
- **update-containers.sh is fixed.** `FORGE_MCP_*_PASSWORD` defaults are empty (`:-}`); values come from `.env`. The script keeps placeholder fallbacks so `docker compose config` does not fail interpolation when the `forge-space` profile is not activated.
- **forge-space.yml is gone.** PR [#43](https://github.com/LucasSantana-Dev/homelab/pull/43) removed `compose/forge-space.yml` entirely because the Forge-Space org was archived 2026-04-20. The `FORGE_MCP_*` interpolation-guard block in `update-containers.sh:15-59` is therefore dead code and can be deleted.

What remains open:

- **Git history still carries the leaked Lucky DB password.** Repo went public 2025-09-29; plaintext `discordbot123` was removed only at `b32f8ba` (2026-04-16). The credential lived in public history for ~6.5 months. Must be rotated regardless of scrub decision; history-scrub is a second step.
- **No automated gate prevents re-introduction.** `.gitleaks.toml` covers Kubernetes secret patterns and Discord webhook tokens but not the inline `VAR="value"` pattern that slipped through last time.

## Approach

1. **Close the live-code loop.** Delete the dead `FORGE_MCP_*` guard block from `scripts/maintenance/update-containers.sh` now that `compose/forge-space.yml` is gone.
2. **Rotate the Lucky DB credential.** Generate a new password, update `.env` on the homelab host, restart `lucky-postgres`, verify `recover-lucky-db.sh` still connects.
3. **Decide on history scrub.** Two options:
   - (A) Run `scripts/security/rewrite-history.sh` per [`docs/public-release-hardening.md`](../../public-release-hardening.md). Forces every clone to re-clone. Clean.
   - (B) Accept the exposure — it is a non-production dev-grade password (`discordbot123`) protected by Tailscale-only access to the Lucky container. Document the risk-accepted state.
   Recommended: (A) if the Lucky database is accessible outside Tailscale at any point (even historically), else (B) with a dated note in [`docs/secrets.md`](../../secrets.md).
4. **Add a gitleaks rule** for inline shell secrets of the pattern `(?i)(password|secret|token|key)=["'][A-Za-z0-9+/=_\-]{6,}["']` unless already allowlisted. Test against the known-historical commit to confirm detection; gate future PRs.

## Verification

- `rg -nP '(password|secret|token|key)=["'\''"][^$][^"'\''"]+["'\''"]' scripts/` returns no hits outside allowlists.
- `scripts/security/secret-gate.sh` passes with the new gitleaks rule enabled.
- `docker exec lucky-postgres psql -U <user> -c '\conninfo'` succeeds after rotation.
- `docker compose -f docker-compose.yml config --quiet` still passes without the `FORGE_MCP_*` placeholders.
- If history scrub lands: `scripts/security/pre-release-checkpoint.sh` backup + tag + mirror exist; `git log -S"discordbot123" --all` returns empty on the rewritten ref.

## Out of scope

- Rotating credentials unrelated to this audit finding (Discord webhooks, Cloudflare tokens, etc.) — those are covered by the generic flow in `docs/public-release-hardening.md` §2.
- Introducing SOPS age-encrypted secrets. `.sops.yaml` exists but its round-trip has not been verified — tracked separately (backlog item G2).
