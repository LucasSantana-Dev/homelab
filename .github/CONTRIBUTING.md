# Contributing

This is a personal homelab repository. Contributions are welcome but narrow in scope: the stack is tuned for a single deployment, so changes that only make sense in a different setup are less likely to land.

## Before you open a PR

1. **Skim the boundaries.** Read [`docs/adr/`](../docs/adr/) and [`docs/project-structure.md`](../docs/project-structure.md). The big decisions that shape the repo:
   - Docker Compose is the only orchestrator ([`ADR 0001`](../docs/adr/0001-compose-vs-k3s-boundary.md), [`ADR 0004`](../docs/adr/0004-drop-k3s.md)).
   - Local-path storage only ([`ADR 0002`](../docs/adr/0002-storage-boundary-local-path.md)).
   - Ingress is Compose-edge via Caddy ([`ADR 0003`](../docs/adr/0003-ingress-boundary-compose-edge.md)).
2. **Pick the right change size.** Small, scoped PRs ship. Mixing features, refactors, and config edits in one branch does not.
3. **Run the local gates** from [`DEVELOPMENT.md`](../DEVELOPMENT.md):

   ```bash
   make lint
   make test
   ./scripts/security/secret-gate.sh
   ./scripts/security/public-safety-gate.sh
   ```

4. **No secrets.** Anything credential-shaped belongs in a local `.env` (gitignored) or SOPS-encrypted under `.env.enc.yaml`. See [`docs/secrets.md`](../docs/secrets.md).

## Commit style

Conventional Commits, lowercase type, short imperative subject:

```
<type>(<scope>): <subject>

<optional body>
```

Types in active use: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`. Scopes match the top-level directory or subsystem (`caddy`, `compose`, `ci`, `scripts`, `k3s`, `tailscale`, `monitoring`, `security`, …).

Examples from recent history:

- `chore(ci): drop dead Craftvaria repo ref, gate pytest, retire py3.9`
- `feat(caddy): unify reverse proxy — cloudflared → caddy-lan → k3s`
- `fix(stremio): restore remote access via LAN DNS + Tailscale Funnel`

## Pull requests

- Base branch is `main`. Linear history is required — no merge commits, all PRs are squash-merged.
- Required CI checks: `pre-commit`, `test (3.12)`, `repo-hygiene`, `terraform-check`, `CodeQL`. The `docker`, `security`, and `container-security` jobs also run but are advisory.
- Renovate owns dependency bumps — do not open manual dep-update PRs unless Renovate is misconfigured.
- If your change is non-trivial, draft a spec under [`docs/specs/`](../docs/specs/) first following the existing format (`spec.md` + `tasks.md`, frontmatter with `status`/`created`/`tags`).

## Reporting security issues

Do **not** open public issues for security problems. Follow [`SECURITY.md`](./SECURITY.md).

## Code of conduct

By participating you agree to the [Code of Conduct](./CODE_OF_CONDUCT.md).
