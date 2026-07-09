# ADR 0039: AI code review is advisory, not a required-approval merge gate

- **Status:** Proposed
- **Date:** 2026-07-09
- **Deciders:** Lucas (solo operator)
- **Supersedes:** —
- **Superseded by:** —
- **Related:** [ADR-0037](./0037-agent-box-resilient-boot-and-deploy-runbook.md) (hermes review automation), [ADR-0022 release workflow]

---

## Context

The release PR **#368 (`v2.12.0`)** was `MERGEABLE` but `BLOCKED`. Investigation
(not assumption) found the real gate, which was not what a prior session summary
claimed ("swap the `CodeRabbit` required status-check to `cubic`").

**Measured state of `main` branch protection (2026-07-09):**
- `required_approving_review_count: 1`, `dismiss_stale_reviews: false`, `enforce_admins: true`.
- Required status contexts: `pre-commit, test (3.12), repo-hygiene, terraform-check, CodeQL, CodeRabbit` — all **SUCCESS** on #368, including the `CodeRabbit` *status* context.
- Two AI reviewers run on **every** PR:
  - **CodeRabbit** — a GitHub App reviewer that submits `APPROVED` / `CHANGES_REQUESTED` **reviews**. Its `APPROVED` is what satisfied the required-1-approval on every recently-merged PR (#292, #300, #303, #309 all `reviewDecision=APPROVED` via CodeRabbit — the solo author cannot approve their own PR).
  - **cubic** — submits `COMMENTED` (non-blocking) reviews plus a passing `cubic · AI code reviewer` status check. **Never `APPROVED`.**

**Root cause of the deadlock:** On #368, CodeRabbit posted `CHANGES_REQUESTED`
(12 comments, 0 postable inline; sampled content was a stale-doc nitpick —
`512M` in a comment vs a `1G` limit — plus 2 nitpicks). `reviewDecision` therefore
= `CHANGES_REQUESTED`, the required approval is unmet, and `enforce_admins: true`
means the admin operator **cannot** admin-merge past it. The merge gate is a
**bot's approval verdict**, and any CodeRabbit `CHANGES_REQUESTED` — however
trivial — is a hard release deadlock.

Meanwhile **cubic** (advisory, non-gating) reported 8 issues "verified against the
latest diff", the top one a genuine **P1**: `run_on_agent` breaks multi-word remote
commands because `printf '%q'` quotes the whole command as a single remote shell
word (same remote-command-quoting bug-class seen earlier this session with
`pkill -f`). The higher-signal reviewer was the one that did **not** block; the
lower-signal reviewer was the one holding the release.

## Decision

**Merges on this repo are gated on objective required status checks, not on an AI
bot's approval. Both AI reviewers are advisory (non-gating).**

Concretely, recommend to the operator (branch-protection change on `main` — see
"Consequences → action required"):

1. **Set `required_approving_review_count: 0`.** For a **solo** operator with
   `enforce_admins: true`, a required *approval* that only a configured bot can
   supply provides no independent-review value — the "reviewer" is a tool the
   operator owns — while creating a hard-deadlock failure mode on any bot
   `CHANGES_REQUESTED`. Quality is already enforced objectively by the required
   status checks (tests across 3.10–3.12, CodeQL, pre-commit, repo-hygiene,
   terraform-check, container-security, Trivy, GitGuardian, Socket, plus the
   CodeRabbit and cubic **status** checks).
2. **Keep BOTH CodeRabbit and cubic as advisory reviewers.** With approval-count
   0, neither can deadlock a merge; their comments and the `CHANGES_REQUESTED`
   state become signal the operator reads and acts on, not a gate. Optionally set
   CodeRabbit `reviews.request_changes_workflow: false` (via the `.coderabbit.yaml`
   from PR #312, already `profile: chill`) so it stops emitting `CHANGES_REQUESTED`
   noise — but note this is cosmetic once approval-count is 0.

Do **not** decide "cubic vs CodeRabbit, keep one" now — see *revisit*. Both are
advisory and cost only ignorable comment-noise; the keep-one question is
low-stakes and premature on the current evidence (one PR of divergence).

## Alternatives considered

- **Keep CodeRabbit-approval as the required gate (status quo).** Rejected:
  periodic hard deadlocks on nitpick `CHANGES_REQUESTED`, unescapable under
  `enforce_admins: true`. This is what blocked #368.
- **Demote CodeRabbit review to non-blocking only (`request_changes_workflow:
  false`), leave approval-count at 1.** Rejected: CodeRabbit would then post
  `COMMENT`, not `APPROVED` → the required approval is *still* unmet → still
  blocked. Demotion alone does not unblock. (Confirmed against branch-protection
  rules, not assumed.)
- **cubic-only, drop CodeRabbit.** Rejected: cubic never `APPROVED`s, so it cannot
  fill the required-review role; choosing it *forces* the approval-count-0 change
  anyway, and drops a second advisory lens for no gain.
- **Toggle `enforce_admins` off per-release to self-merge, then back on.** Rejected
  as the standing model (fine as a one-off escape hatch): turns every release into
  a manual protection dance; the deadlock class remains.
- **Keep both, claim complementary specialization (cubic→logic, CodeRabbit→docs).**
  Rejected as a *justification*: n=1 PR cannot distinguish specialization from
  coincidence (critic finding). The decision to keep both rests on "advisory is
  near-free", not on proven division of labor.

## Consequences

**Positive:**
- The release-deadlock failure mode is eliminated (the gate no longer depends on a
  bot's approval verdict).
- Merge gating rests on objective, reproducible status checks.
- Both AI lenses are retained as advisory signal.

**Negative / neutral:**
- Losing a required *approval* removes the "second pair of eyes" ceremony — but on
  a solo repo the only eyes were a bot's. Real second-reviewer value returns only
  with a second human (see revisit).
- Advisory reviewers can be habituated-away: a real P1 posted as a `COMMENT` can be
  ignored. Mitigation: the cubic P1 from #368 is tracked as a fix before v2.12.0
  ships; treat cubic/CodeRabbit `CHANGES_REQUESTED`/high-severity items as a
  read-before-merge checklist, not a gate.
- Running two AI reviewers on every PR is mild redundancy (compute + comment
  noise). Accepted as near-free for a low-volume repo; revisited on a schedule.

**Action required (operator — not yet done; branch-protection change on `main`
needs explicit operator consent):**
- `PATCH main` protection: `required_approving_review_count → 0`.
- Then #368 merges on green status checks; tag `v2.12.0`.
- Pre-merge: fix the cubic P1 (`run_on_agent` `printf '%q'`) — separate commit.

## Revisit when

- **A second human contributor joins the repo** → a required approval becomes a
  meaningful independent-review gate; re-add `required_approving_review_count ≥ 1`
  with the human (not a bot) as the approver.
- **A P1 ships that an advisory reviewer had flagged and was ignored** → tighten:
  make the higher-signal reviewer's high-severity findings a blocking status check.
- **A 30-day usage review** shows one reviewer strictly dominates true positives
  (or one is pure noise) → drop the weaker; this is when the "cubic vs CodeRabbit"
  question is decided on real frequency data, not anecdote.
