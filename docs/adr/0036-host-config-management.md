# ADR 0036: Host Config Management — Git-First Flow with Dirty-File Gate

- **Status:** Accepted
- **Date:** 2026-06-22
- **Deciders:** Lucas (solo operator)
- **Supersedes:** —
- **Superseded by:** —
- **Related:** [ADR-0023](./0023-deploy-drift-observability.md) (deploy drift observability), [ADR-0022](./0022-release-branch-model.md) (release-branch model), [ADR-0013](./0013-auto-deploy-pipeline.md) (auto-deploy pipeline, deferred)

---

## Context

On 2026-06-22, the homelab host was discovered running **v2.8.0 locally with 24 tracked-file local modifications** while `origin/release` had advanced to **v2.10.7** (62 commits ahead over 2+ weeks). Investigation revealed:

1. **Root cause:** The host was used as the primary dev environment. Config changes were edited directly on the host, then some were committed upstream via PRs on the MacBook, but `make deploy` was **never executed** after v2.8.0 to pull those changes back to the host.
2. **Silent drift:** ADR-0023 added drift alerting (`homelab_version_drift_days > 7` → Discord), which correctly surfaced the version gap. But the file-level divergence (24 local modifications) was neither visible nor prevented — the alert came late.
3. **Dry-run validation:** A `git stash && git checkout release && git pull && git stash pop` dry-run revealed **0 merge conflicts** — all 24 local modifications were already superseded by upstream PRs. The host's "local" changes were not novel; they were just stale.
4. **Port binding convention already normalized:** TAILSCALE_IP port bindings (security hardening applied directly on the host during earlier sessions) have since been formalized in tracked compose files (`compose/monitoring.yml`, `compose/core.yml`). No host-specific override layer is needed.

ADR-0023 addressed the feedback loop (drift visibility), but the root cause (host as dev environment + no pre-deploy gate) was not. This ADR closes that gap.

## Decision

**Adopt strict git-first config flow with a dirty-file gate on `make deploy`.**

The operator's workflow changes from:
- **Before:** edit config on host → maybe commit to repo → maybe `make deploy` (or skip it and drift)
- **After:** edit config on MacBook → PR → merge to release → guaranteed `make deploy` picks it up (or blocked + alerted)

### Policies (enforceable, not advisory)

1. **No direct tracked-file edits on the host.** Tracked files — any `*.yml`, `*.yaml`, `*.toml`, files under `homelab_manager/**`, or files under `config/**` — are never edited directly on the host. All config changes originate from the MacBook, go through a PR, merge to release, then `make deploy` pulls them.

2. **`make deploy` dirty-file gate:** The deploy target now checks `git status --porcelain` before executing `docker compose up -d`:
   ```bash
   # Pseudo-code for the gate
   if git diff --quiet HEAD -- '*.yml' '*.yaml' '*.toml' homelab_manager/ config/; then
       # Clean — proceed with deploy
       docker compose up -d --build
   else
       # Dirty — fail with guidance
       echo "❌ Host has local modifications to tracked files:"
       git diff --name-only HEAD -- '*.yml' '*.yaml' '*.toml' homelab_manager/ config/
       echo "Commit them or stash them, then re-run make deploy."
       echo "For emergency overrides: DEPLOY_FORCE=1 make deploy"
       exit 1
   fi
   ```

3. **Emergency override protocol (`DEPLOY_FORCE=1`):** If you MUST edit a tracked file directly on the host for operational urgency:
   - Do it (document the reason inline in the file if possible).
   - **Immediately** stash it: `git stash -m "host-emergency: <reason>"`
   - Set `DEPLOY_FORCE=1` when deploying: `DEPLOY_FORCE=1 make deploy`
   - The deploy will succeed, but **append to `/var/log/homelab-deploy-overrides.log`:**
     ```
     [2026-06-22T14:30:00Z] DEPLOY_FORCE=1 by luk-server
     Modified tracked files: config/caddy/Caddyfile, compose/monitoring.yml
     Reason: production outage — alert threshold misconfiguration required immediate dial-down
     ```
   - **Within 24 hours**, open a PR from MacBook to make the change permanent (move it from host-only into tracked config, or formalize it in `.env`).

4. **No `override.local.yml` needed (revised from proposal).** Initial proposal included a gitignored `compose/override.local.yml` for host-specific bindings. **Withdrawn:** all known host-specific config (TAILSCALE_IP port bindings, icons, log.py) is already tracked. If a genuine host-only config emerges in the future (truly cannot be tracked), add the pattern at that time.

## Alternatives considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **A — Git-first + dirty-file gate (adopted)** | **Accepted** | Prevents silent divergence at the file level; gate is a pre-flight check, not a gate after the fact; emergency escape hatch is audited for accountability. |
| B — Status quo (edit on host, commit later) | Rejected | Exactly what caused the 62-commit drift observed on 2026-06-22. No pre-flight check = no signal until drift is large. |
| C — `override.local.yml` for host-specific config | Deferred | Not needed: all known host overrides are already tracked. Revisit only if a true host-only config emerges. |
| D — Ansible / Jinja templating | Rejected | Single-host homelab; learning curve and maintenance overhead not justified. Branch-per-host and role-per-function are Ansible patterns, not docker-compose. |
| E — Branch-per-host (`main` = template, `server-luk` = host-specific) | Rejected | Conflicts with ADR-0022 (release-branch model). Rebase friction with batched releases. Over-engineered for single host. |
| F — GitOps pull operator (Flux / ArgoCD) | Rejected | Container orchestration overhead not justified for a single-host homelab. |

## Consequences

### Positive

- **Silent drift prevented:** `make deploy` now fails loudly if the host has local modifications to tracked config. The operator gets: "Fix this before deploying" instead of a silent successful deploy that leaves the host and repo out of sync.
- **Host stays 1:1 with release:** tracked config on the host always matches the release branch (within the window of time between `git pull` and the next change).
- **Emergency edits are audited:** `DEPLOY_FORCE=1` overrides are logged to `/var/log/homelab-deploy-overrides.log` with timestamps and file lists, so drift from emergencies is visible in hindsight and reviewable before the next release.
- **Reuses existing infrastructure:** the dirty-file check is a simple git command; no new observability or tooling needed beyond what ADR-0023 already added (drift alerts).

### Negative

- **Direct host edits are now a process violation** (but not impossible). If the operator forgets the `git stash` / `DEPLOY_FORCE=1` protocol, the next `make deploy` will block with an error. This is intentional friction, not a bug.
- **`make deploy` target gains ~1s latency** for the pre-flight git check. Negligible.
- **Emergency escape hatch adds a small operational burden:** the log at `/var/log/homelab-deploy-overrides.log` must be reviewed periodically (recommend: before each release, as part of the release handoff).

### Neutral

- **Workflow unchanged except for the gate.** PRs still go through the same release-branch merge flow; `make deploy` still runs the same compose up/health-check sequence. Only new thing is the pre-flight check.
- **Does not address pre-v2.8.0 divergence.** The 62-commit gap that existed on 2026-06-22 is resolved by a one-time `git pull` (done on 2026-06-22 at 14:38 UTC). This ADR prevents the *next* divergence.

## Revisit triggers

| # | Trigger | Action |
|---|---------|--------|
| R1 | A second homelab host is added | Re-evaluate git-branch-per-host and Ansible inventory-vars patterns; may become cost-effective at 2+ hosts. |
| R2 | A genuine host-only config emerges that cannot be tracked | Implement `compose/override.local.yml` pattern (gitignored) at that time. |
| R3 | Auto-deploy (ADR-0013 Option C) is implemented | The dirty-file gate must integrate with the auto-deploy pull-loop; a dangling local modification could auto-deploy an out-of-date state. |
| R4 | `/var/log/homelab-deploy-overrides.log` reaches >3 entries in a release cycle | Indicates repeated emergency edits; escalate to deeper investigation of why edits are needed on the host (e.g., is the MacBook-to-PR-to-deploy latency unacceptable for a class of changes?). |
| R5 | Calendar: 2026-12-22 (6 months from this ADR) | Soft checkpoint: is the dirty-file gate preventing drift as intended? Do any of R1–R4 conditions exist? |

## Implementation

1. **One-time cleanup (done 2026-06-22):** `git stash && git checkout release && git pull origin release` on the host; confirm 0 conflicts; discard stash. Host is now at v2.10.7, release branch, 0 local modifications.

2. **Update `make deploy` target (1 Makefile edit):**
   ```makefile
   deploy: validate-env ## Deploy all homelab services
       @echo "🚀 Checking for local config modifications..."
       @if ! git diff --quiet HEAD -- '*.yml' '*.yaml' '*.toml' homelab_manager/ config/; then \
           if [ -z "$$DEPLOY_FORCE" ]; then \
               echo "❌ Host has local modifications to tracked files:"; \
               git diff --name-only HEAD -- '*.yml' '*.yaml' '*.toml' homelab_manager/ config/; \
               echo "Commit them or stash them, then re-run make deploy."; \
               echo "For emergency overrides: DEPLOY_FORCE=1 make deploy"; \
               exit 1; \
           else \
               echo "⚠️  DEPLOY_FORCE=1 — overriding dirty-file check. Logging override."; \
               echo "[$$( date -u +%Y-%m-%dT%H:%M:%SZ)] DEPLOY_FORCE=1 by $$(whoami)" >> /var/log/homelab-deploy-overrides.log; \
               echo "Modified tracked files: $$(git diff --name-only HEAD -- '*.yml' '*.yaml' '*.toml' homelab_manager/ config/)" >> /var/log/homelab-deploy-overrides.log; \
           fi; \
       fi
       @echo "✅ Config check passed. Deploying..."
       docker compose up -d --build
       @bash scripts/deployment/record-deploy-health.sh
       @echo "✅ Deployment complete"
   ```

3. **Ensure `/var/log/homelab-deploy-overrides.log` exists and is rotated:**
   ```bash
   touch /var/log/homelab-deploy-overrides.log
   chmod 644 /var/log/homelab-deploy-overrides.log
   # Add to logrotate, e.g. /etc/logrotate.d/homelab:
   # /var/log/homelab-deploy-overrides.log {
   #     monthly
   #     rotate 6
   #     compress
   # }
   ```

4. **Document the protocol in `docs/deployment.md`** (or equiv.) with the emergency edit section from this ADR.

## Notes

This ADR was born from a dry-run that revealed 0 merge conflicts on a 62-commit gap — a strong signal that the real problem is not multi-sided config edits, but unidirectional drift (host as dev env, never pulled back). The dirty-file gate solves the latter without heavyweight tooling.

The decision-critic process (2026-06-22) verified the core claims:
- Stash pop dry-run revealed 0 conflicts (verified).
- Port-binding convention already normalized in release (verified).
- All blocking files were pre-existing in release (verified).
- `DEPLOY_FORCE=1` escape hatch is the right UX for emergencies in a single-host system (critic confirmed).
