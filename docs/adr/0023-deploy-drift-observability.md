# ADR-0023: Deploy Drift Observability + Deploy-Health Signal (not auto-deploy yet)

**Status:** Accepted
**Date:** 2026-06-18
**Deciders:** Lucas (solo operator)
**Relates:** [[ADR-0013]] (tag-push auto-deploy — Accepted but unbuilt), [[ADR-0010]] (homelab-manager local Dockerfile build, "always `--build`"), [[ADR-0022]] (release-branch / batched-tag model)

## Context

Production `homelab-manager` was found running **v2.5.1** while the repo had shipped through **v2.7.0** — weeks of undetected drift. Investigation found **three** independent gaps, not one:

1. **No observability of the running version vs the latest release.** Nothing compared the deployed version to the newest tag, so the drift was silent.
2. **`make deploy` silently fails on host `.env` drift.** `make deploy` runs `validate-env` first, which hard-fails when the host `.env` is missing compose-referenced vars (found: `HEALTHCHECKS_SUPERUSER_EMAIL/PASSWORD`). These *are* in `.env.example` (empty), but the host `.env` was never synced — and **CI cannot catch this** because the host `.env` is not in the repo. Every manual deploy bounced off this wall unnoticed.
3. **`make deploy` does not rebuild the manager.** The target is `docker compose up -d` with **no `--build`**, violating [[ADR-0010]] ("always `--build` on source changes"). So even a *passing* `make deploy` would not have updated `homelab-manager:local` to 2.7.0; the image was 2 weeks stale.

ADR-0013 ("tag push auto-deploys") was Accepted but **never implemented** — there is no tag-deploy timer/script on the host. The deploy story is "manual + silently broken in three places."

## Decision

**Adopt Option B+ : make deploy drift and deploy-health observable, and fix the broken deploy mechanics — but keep deploys a deliberate human action (do NOT add auto-deploy yet).**

The failure was a broken *feedback loop*, not (primarily) a missing *automation*. Auto-deploy alone (Option A) would have silently hit the same `validate-env` wall and the same no-`--build` bug. So observability + mechanics are the load-bearing fixes; auto-deploy is a later, optional layer.

Concretely:

1. **Fix deploy mechanics (root cause):**
   - `make deploy` → add `--build` (ADR-0010 compliance) so the manager image rebuilds; add a post-up `/health` gate that fails the target if the service didn't come up.
   - Add a host-side `.env`-vs-`.env.example` preflight that reports **missing keys by name** (the gap CI can't see).
2. **Deploy-health signal:** the deploy wrapper writes a Prometheus textfile `homelab_last_deploy_status` (+ version, + timestamp) so a *failed or never-run* deploy is visible — not just drift.
3. **Drift exporter** (systemd timer, mirroring the existing `kopia-snapshot-freshness` textfile pattern): `homelab_running_version` (from `/health` on `127.0.0.1:8765`), `homelab_latest_tag` (`git tag -l 'v[0-9]*.[0-9]*.[0-9]*'` — **must** exclude non-semver tags like `backup-pre-public-*`), and `homelab_version_drift_days`.
4. **Exporter meta-healthcheck:** a Prometheus rule fires if the drift/deploy textfiles are stale (mtime > 6h), so the *exporter dying* cannot reproduce the original blind spot one level up.
5. **Drift alert:** `homelab_version_drift_days > 7` → Alertmanager → Discord (threshold tied to the ADR-0022 release cadence; tune later).

## Why this (decision-critic reconciliation)

`decision-critic` returned **NEEDS_REVISION** on plain Option B and the revisions are folded in above:
- B alone surfaced drift but **not** deploy-health (the validate-env block) — added the `last_deploy_status` metric + the `.env` preflight.
- The exporter is itself a silent-failure point — added the meta-healthcheck (#4).
- Tag pollution is real (`backup-pre-public-*` tags exist) — pinned the semver filter (#3).
- Verified `make deploy` lacks `--build` — added the ADR-0010 fix (#1), which the critic's contract surfaced indirectly via "deploy-health gap."

## Alternatives considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **B+** (drift + deploy-health + mechanics fix, manual deploy) | **Adopted** | Fixes all three gaps; reuses existing Prom/Grafana/Alertmanager + textfile pattern; keeps human-in-loop for prod config restarts. |
| A — auto-deploy only (implement ADR-0013) | Rejected | Would have silently hit the same validate-env + no-`--build` walls; no visibility. |
| B (plain) — drift metric only | Revised → B+ | Surfaces drift but not deploy-health; exporter is an unguarded silent-failure point; tag filter unspecified. |
| C — B+ **and** auto-deploy poller | Deferred | Correct only *after* the mechanics are fixed and proven; auto-applying unreviewed config to a single prod host is the bigger risk. The revisit trigger below escalates to C. |
| D — validate-env in CI only | Rejected (insufficient) | CI can't see the host `.env`; a partial CI check already exists in `ci.yml` and did not prevent this. |
| E — GitOps auto-pull+compose on `main` | Rejected | Deploys every commit — conflicts with the ADR-0022 batched-tag release model. |
| F — status quo + runbook | Rejected | Silent drift recurs (just proven). |

## Consequences

**Positive:** drift and deploy failures both become loud; the manager actually rebuilds; the host `.env` gap is named, not silent; observability reuses existing infra at low cost.
**Negative:** more host-side moving parts (exporter + timer + alert rules) — mitigated by the meta-healthcheck. Alert threshold needs tuning to avoid fatigue.
**Neutral:** deploys stay manual; ADR-0013's auto-deploy remains unbuilt and is explicitly deferred (not silently assumed live).

## Revisit when (escalate to Option C — auto-deploy)

- Drift alerts fire **repeatedly** but deploys still lag → the manual step itself is the failure (not the feedback loop); implement the ADR-0013 poller on top of this observability.
- The operator is regularly unavailable to deploy within the drift SLA.
- `make deploy` mechanics + `.env` preflight prove reliable for 2+ release cycles (precondition for trusting auto-deploy).

Also revisit ADR-0013 directly: either implement it (becomes Option C) or mark it Superseded by this ADR so "tag = deploy" stops being fiction.
