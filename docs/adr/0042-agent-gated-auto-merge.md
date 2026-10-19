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

Two branch mistakes showed up in the same batch. Lucky #2886-#2890 were stacked: each branch was
cut from the previous one, all with base `main`, so one broken spec turned all five red. homelab
#522 was opened against `main`, while homelab PRs go to `release` (base-guard).

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
  `merge_block_paths` (lockfiles, go.mod) or the repo's `repo_merge_block_paths`, and on a repo
  with `repo_merge_allow_paths` only paths on that list (homelab: `docs/`, `tests/`, Markdown).
  Missing data fails closed. A queued PR the sweep cannot load or check loses its auto-merge;
  when turning it off fails too, the PR stays queued, the sweep alerts ("STILL QUEUED") and keeps
  it on its list so the next run tries again. Until then GitHub can merge it on its last checked
  commit, the one the merge was pinned to.
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
- Branch checks, deterministic in two places. The `pr-create-guard.sh` hook (PreToolUse, every
  agent-box session) blocks `gh pr create` unless `--base` is the repo's base from
  `agent-gate.json` (homelab `release`, Lucky and cojam `main`) and the branch, after a fresh
  fetch of every branch on origin, has commits on top of `origin/<base>` and shares none with
  another branch that is not its own descendant. The gate then checks the PR against open PRs
  only: a branch pushed after that fetch, with no PR yet, is caught by neither check until it
  has one. After the PR exists, the gate (`branch_problems` in
  `agent_gate.py`) refuses a wrong base or a PR that shares a commit with another open PR:
  pr-automerge refuses it and the loop gate sends it to `needs-human`. Missing data fails closed.
  The hook parses the command with shell quoting (a `--base` inside a title does not count),
  matches repo names without case, and blocks two PRs in one command and a `gh api .../pulls`
  write (a non-GET method, or a field or `--input` without `-X GET`); a GET that lists PRs
  passes.
  The gate check is the backstop for anything the hook misses. Limit: once the lower PR of a
  stack squash-merges and closes, its old commits in the upper PR no longer match an open PR;
  the hook is what stops that stack from being opened in the first place.
- Loop PRs keep the immediate `--match-head-commit` merge; yellow pillars now qualify, red never,
  and the same merge check applies (dependency and lockfile changes go to the owner).
- Prompts: a task is done when the PR is merged and the base is green after it; until then the
  agent follows CI and fixes it, and re-runs pr-automerge after every push. Each branch is cut
  from a freshly fetched `origin/<base>`, and `git rev-list --count origin/<base>..<branch>` must
  equal the change's own commits before the PR is opened.

Why not the Action: it adds a merge-capable secret per repo or loses downstream workflows, and the
label it keys on is something the agent can set. Why not the bare command: no check at all. The
wrapper reuses tested gate code, ships in the image the agent cannot write, and merges with the
owner's PAT, so release-please and deploy workflows still fire.

## Consequences

- Discord PRs merge without the owner when CI passes and nothing sensitive is touched. PRs with
  bot review threads stopped too, because the session could not resolve threads; the amendment
  below closes that gap.
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

## Amendment (2026-10-19): bot review threads on Discord PRs

**Context.** Review bots (cubic on Lucky most often, coderabbit) open threads on most Discord
PRs. `merge-check` refuses any unresolved thread and Lucky's ruleset requires them resolved, but
the session cannot read thread ids, reply or resolve: all of that is GraphQL, and `gh api` stays
denied because a mutation can merge. Every such PR waited for the owner. The loop already solves
this for its own PRs: the model writes a replies file and `agent-pr-gate.sh` posts the replies
and resolves only threads fixed in a pushed commit.

**Options.**

1. Allow `gh api graphql` for the session with a narrower pattern. A permission pattern cannot
   tell a reply mutation from `mergePullRequest` or `enablePullRequestAutoMerge`; no.
2. Let the host gate pick up Discord PRs and run the loop's thread flow. The gate only scores
   registry PRs on Lucky and cojam, four times a day, and would need a model run of its own to
   write replies the session already knows. Slow, and a second writer on the same branch.
3. Extend `pr-automerge` (root-owned, already the session's only merge path): `--threads` prints
   the open threads with their ids, `--replies <file>` posts the session's replies and resolves
   the fixed bot threads, then runs the normal merge check and queue.

**Decision.** Option 3. `agent_gate.py thread-replies` decides what is posted; the wrapper only
runs the two fixed mutations (`addPullRequestReviewThreadReply`, `resolveReviewThread`), so the
session gets no general GraphQL access. Rules, all fail closed:

- Nothing is posted on a PR that is not open, comes from a fork, has any human activity (PR,
  linked issues, any thread), has unfetched threads or pages, or whose replies file is not one
  JSON array (64 KiB cap).
- Only open threads where every comment is a listed bot (`__typename` Bot and in `bots`) are
  answered. A thread the owner joined, an unlisted App's thread and any human thread are skipped;
  the owner answers those.
- `fixed: true` resolves the thread only when the PR's commit list ends at the head and has a
  commit after the reviewed commit of every comment in the thread (`originalCommit`). Without
  that the entry is skipped entirely, so no reply claims a fix GitHub does not have; the session
  pushes and runs it again.
- `fixed: false` posts the reply and leaves the thread open. The thread then has an owner
  comment, so it is no longer bot-only: the session never touches it again and the PR waits for
  the owner, as in the loop.
- A thread named twice is skipped, and so is a reply with an `@mention` or a line starting
  with a slash command: posted as the owner it would start bots or comment-triggered workflows
  with owner trust, and the bot text the session reads could steer it into writing one.
  Replies are capped at 2000 characters and em and en dashes become commas.

**Consequences.** Discord PRs whose only blockers are valid bot claims now merge without the
owner. Replies are posted with the owner's PAT, as the loop's are; the session could already
comment through `gh pr comment`, so the new capability is resolving bot threads, bounded by the
pushed-commit rule. Accepted risk: "fixed" is the model's claim, checked only for a later push,
not for whether that push fixes the thread (same as the loop): an empty commit or a merge of
the base would satisfy the check. Requiring the later commits to touch the thread's file was
considered and left out: it needs per-commit file lists, and a valid fix often lives in a
caller or a test, which would send real fixes back to the owner. The reply stays on the PR for the
owner to read, and Lucky's own CI and review bots run on the new head.
