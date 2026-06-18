# ADR-0022: Keep the Tag-Driven Release-Branch Model; Reconcile by Back-Merge, Not Trunk-Based Rewrite

**Status:** Accepted
**Date:** 2026-06-18
**Deciders:** Lucas (solo operator)
**Supersedes/relates:** [[ADR-0013]] (tag-push auto-deploy), [[ADR-0019]] (branch reconciliation: fetch+rebase over reset)

## Context

`main` and the long-lived `release` branch forked at tag `v2.6.1` (`98c2709`) and were never cross-merged, accumulating **genuinely disjoint work** on both sides:

- **main-only (8 commits):** v2.6.2 + v2.6.4 releases, CLI exception scrub (#180), server HTTP integration tests (#181), loki `/loki` bind-mount fix (#191), promtail label fix (#192), homepage EACCES hotfix, Grafana Loki panels (#222).
- **release-only (17 commits):** dependabot CI bumps (#187–#190), black pin (#186), public-safety-gate scope fix, kopia snapshot-freshness metric+alert (ADR-0016), per-service health-check timeout bound, validate-env parser tests (#177), backup-docs rewrite + kopia restore runbook (#176), watchdog checkout alignment (#178), healthcheck 127.0.0.1 fix (ADR-0018), v2.6.1 release.

~1207 insertions / 147 deletions across 17 files; only the EACCES hotfix is duplicated (different SHAs). The divergence **hard-failed a `/release-cut`** (its precondition requires `release ⊇ main`) on 2026-06-18, forcing a `/hotfix` path to ship v2.6.4. This forced the question: fix the branch model, or abandon it.

## Decision

**Keep the tag-driven release-branch model. Reconcile the fork by back-merging `main` → `release` (restoring the `release ⊇ main` invariant), and fix the root cause — work-routing discipline — rather than deleting `release` for a trunk-based model.**

The reconciliation merge lands on `release` (which has no linear-history constraint), so a real merge commit is fine; `main`'s squash-only/linear protection is not in the way. After reconciliation, the next `/release-cut` ships the unified batch (kopia feature ⇒ likely a minor, v2.7.0).

### Why not trunk-based (the option originally favored)

The Phase-1 leading option was **A: go trunk-based on `main`, delete `release`.** A `decision-critic` review returned **NEEDS_REVISION**, and verifying its Claims-To-Verify refuted A's premises:

- **Deploy is tag-driven, not main-HEAD** ([[ADR-0013]], Accepted): the host polls and deploys the **highest semver tag** (`tag-deploy-guard.sh`). Versioning is load-bearing, so the buffer that produces coherent, batched tags has real value. A's premise "trunk-based matches actual behavior" is false.
- **The model is in heavy, working use:** 13 tags; `v2.4.2/3/4` shipped within 24h; steady cadence. Not a rarely-succeeding ceremony.
- **Cadence is already codified** (`~/.claude/standards/release-cadence.md` + repo `CONTRIBUTING.md`).
- **A is mechanically broken on its own constraint:** `main` is squash-only + merge-commits disallowed, so "bring release's 17 commits onto main" would squash them to one commit (losing per-PR granularity/bisect on kopia/healthcheck code), or require disabling protection, or actually be cherry-pick-replay (Option C) — the artifact described A but proposed C's mechanics.
- **Root cause is discipline, not the model:** dependabot/CI PRs targeted `release` while feature PRs (#180–#222) targeted `main` directly. Deleting the branch does not fix routing; it makes the cost of poor routing (chaotic tagging, unclear versioning) more visible.

## Alternatives considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **A. Trunk-based on `main`; delete `release`** | Rejected | Premise refuted (deploy is tag-driven; model in active use); mechanically broken under squash-only; doesn't fix the discipline root cause; irreversible one-way door. |
| **B. Keep model + drift-gate automation** | Adopted (partial) | The routing-discipline fix is the durable half of B; full auto-sync automation deferred as over-engineering for one operator until drift recurs. |
| **C. Cherry-pick-replay 17 release commits onto main** | Rejected (kept as rollback) | Clean linear history but 17 cherry-picks risk conflicts/tedium and still abandons the model. Retained as the fallback if the back-merge proves intractable. |
| **D. Make `release` the canonical trunk** | Rejected | Backwards — `main` holds the latest releases (v2.6.2/v2.6.4) + EACCES. |
| **E. Back-merge to reunify + keep model** | **Adopted** | Restores `release ⊇ main` cheaply (merge commit on release); pairs with the discipline fix. |
| **F. Status quo / defer** | Rejected | Proven friction (blocked a release-cut); divergence grows. |

## Consequences

**Positive**
- Preserves the tag-driven deploy pipeline ([[ADR-0013]]) and batched, coherent release notes.
- Reconciliation is mechanically simple (one merge on the unconstrained `release` branch), no protection changes.
- Fixes the actual root cause (routing), not just the symptom.

**Negative**
- The back-merge has a ~9-file conflict surface (CHANGELOG.md, pyproject.toml, compose/core.yml, public-safety-gate.sh, two watchdog workflows, backup.md, kopia-restore.md, validate-env test) needing manual resolution.
- Routing discipline must be enforced by a gate, not trusted to habit — the lapse that caused this will recur otherwise.

**Neutral**
- `main` lineage permanently skips the `2.6.3` version number (the `release` branch owns that tag; see the v2.6.4 release notes). Acceptable; semver gaps are harmless.

## Implementation plan

1. **Reconcile** — in an isolated worktree, branch off `release`, `git merge origin/main`, resolve the ~9 conflicts (CHANGELOG: keep both sections; pyproject: take 2.6.4; compose/core.yml + public-safety-gate.sh: manual), PR → `release`, merge. Success: `git rev-list --count origin/release..origin/main == 0`.
2. **Routing gate** — add a CI/PR-base check + `CONTRIBUTING.md` rule: feature & dependabot PRs target `release`; only `/release-cut` PRs target `main`.
3. **Cut v2.7.0** via `/release-cut` from the reconciled `release` (kopia feature ⇒ minor).

## Revisit when

- `/release-cut` success rate drops below ~80%, OR the operator measures release-branch ceremony at >1h/month → reopen toward trunk-based (Option A/C).
- The deploy model changes to continuous pull of `main` HEAD (no tags) → the buffer loses its purpose; revisit.
- A second operator joins → re-evaluate routing enforcement (review gates become viable).
- Drift re-accumulates within 60 days *despite* the routing gate → the gate is insufficient; escalate to stronger enforcement (branch-protection rule blocking non-release-cut PRs to main).
