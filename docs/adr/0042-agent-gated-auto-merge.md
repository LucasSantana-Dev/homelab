# ADR 0042: Agent PRs merge through a checked auto-merge, not through the owner

- **Status:** Accepted
- **Date:** 2026-10-19
- **Deciders:** Lucas (solo operator)
- **Supersedes:** the "Discord session never merges" rule and the green-only Phase 2 in `docs/agent-loop.md`
- **Related:** [ADR-0039](./0039-ai-review-not-a-required-approval-gate.md), `docs/agent-loop.md`

---

## Context

On 2026-10-19 the owner asked the Discord agent for "auto merge em tudo" on 11 open PRs (Lucky
#2886-#2890, cojam #460-#464, homelab #522). Nothing merged on its own:

- The Discord session denies `gh pr merge*` (user settings and `discord-channel-settings.json`),
  `--auto` included. Its PRs (`fix/<slug>` branches, often without an issue) are not in the loop
  registry, so `agent-pr-gate.sh` never scores them.
- The loop gate merges only PRs with four green pillars (docs, tests, lint config). Runtime code
  went to `owner-review`.
- Local sessions are denied `gh pr merge` by the auto mode classifier.

For the owner a parked PR is not finished work: done means merged on the base branch and green
there.

Measured rulesets (2026-10-19):

| Repo, branch | Required checks | Threads resolved | Notes |
|---|---|---|---|
| Lucky `main` (ruleset 12822499) | Quality Gates, Security, SonarCloud Scan, madge, Build Docker images, Migrations | yes | admin role may bypass ("always") |
| cojam `main` (ruleset 19111697) | Go server, Web, Web e2e | **no** | no bypass actors |
| homelab `release` (branch protection) | pre-commit, test (3.12), repo-hygiene, strict | **no** | enforce_admins |

All three allow auto-merge and squash.

## Options

1. **Let the agent run `gh pr merge --auto` directly.** Simple, but the permission rule cannot
   tell the agent's PRs or safe paths from anything else, and a pattern allow is not a check.
2. **A GitHub Action that enables auto-merge on PRs with a label.** The agent can already add
   labels (issues write on the PAT), so the label proves nothing unless the Action repeats the
   whole check, in three repos, in `.github/workflows` the PAT cannot push. A merge done with the
   Action's `GITHUB_TOKEN` does not trigger `push` workflows, which breaks release-please and the
   deploy chain on Lucky and cojam; avoiding that needs an App key or a PAT stored as a secret in
   each repo, a new credential that can merge.
3. **A checked wrapper on agent-box (`pr-automerge`) plus a sweep from the host gate.** The agent
   may run one root-owned command that checks the PR with the loop's own gate code and only then
   queues `gh pr merge --squash --auto --match-head-commit <sha>`.

## Decision

Option 3, and the loop gate moves to `auto_merge: "no-red"`.

- `agent_gate.py merge-check` refuses unless: repo in the allowlist, open, not draft, not a fork,
  base is the repo's configured base (`release` for homelab), owner-authored with no other human
  activity on the PR or the issues it closes, no unresolved or unfetched review thread, complete
  file list, and no path in `high_impact_paths`, `sensitive_paths`, `dependency_files`,
  `merge_block_paths` (lockfiles, go.mod) or the repo's `repo_merge_block_paths` (homelab blocks
  its host config, scripts and dotfiles, so only docs and tests merge there). Missing data fails
  closed.
- `pr-automerge` (image copy, root-owned, with its own copy of the gate and config) queues the
  merge only after the check passes, never with `--admin`, and turns auto-merge off when a
  re-check fails. The image copy ignores the caller's `AGENT_GATE_CONFIG`, `PR_AUTOMERGE_STATE`
  and `PATH`. `gh pr merge` stays denied for the model everywhere. When nothing is pending, gh
  merges at once instead of queueing; the check has passed on that exact commit, so that is fine.
- GitHub keeps auto-merge queued when a user with write access pushes, which every agent push is.
  The `automerge-push-guard.sh` hook (PreToolUse, every agent-box session) turns auto-merge off
  on the pushed branch's PR before each `git push` and blocks the push when it cannot; the
  session runs pr-automerge again after the push.
- `agent-pr-gate.sh` runs `pr-automerge --sweep` on every run (four a day, also while the loop is
  paused) to re-check queued PRs.
- Loop PRs keep the immediate `--match-head-commit` merge; yellow pillars now qualify, red never,
  and the same merge check applies (dependency and lockfile changes go to the owner).
- Prompts: a task is done when the PR is merged and the base is green after it; until then the
  agent follows CI and fixes it, and re-runs pr-automerge after every push.

Why not the Action: it adds a merge-capable secret per repo or loses downstream workflows, and the
label it keys on is something the agent can set. Why not the bare command: no check at all. The
wrapper reuses tested gate code, ships in the image the agent cannot write, and merges with the
owner's PAT, so release-please and deploy workflows still fire.

## Consequences

- Discord PRs merge without the owner when CI passes and nothing sensitive is touched. PRs with
  bot review threads still stop, because the session cannot resolve threads (follow-up).
- The ruleset is the last gate for a queued merge. Owner actions to make it hold everywhere:
  turn on review thread resolution on cojam `main` and conversation resolution on homelab
  `release`. Lucky's admin bypass stays; pr-automerge never uses `--admin`.
- Accepted risk: a queued merge fires without a fresh check. A human comment that lands after
  the last check is caught only by the next sweep, and a push from outside agent-box (only the
  owner pushes there) skips the hook. On these solo repos a foreign human is rare.
- The sweep and the push hook turn auto-merge off on a PR even when another human commented on
  it. That is the one automated action allowed on such a PR: it stops a merge, it never makes
  one, and the alternative is merging over the comment.
- Same-uid caveat (agent-loop.md): code running as `agent` can use the PAT directly. This is the
  sanctioned path that makes the honest flow safe, not a boundary against a compromised session.
- Brake: if an auto-merged PR breaks a base branch, set `auto_merge` back to `true` (or `false`)
  and remove `pr-automerge` from the Discord rules until the missed check is added.
