# ADR 0043: The loop follows session PRs to the merge and refills the backlog

- **Status:** Accepted
- **Date:** 2026-10-19
- **Deciders:** Lucas (solo operator)
- **Builds on:** [ADR-0042](./0042-agent-gated-auto-merge.md), `docs/agent-loop.md`

---

## Context

Owner, 2026-10-19: "Se o bot não consegue ativar o auto fix e o auto merge não existe autonomia.
E também precisamos fazer o bot puxar uma nova rodada de backlog após a finalização dela."

Measured the same day:

- 25 open PRs from the Discord session (cojam 459-473, Lucky 2878-2892) sat without a merge.
  pr-automerge (ADR 0042) is not on the agent-box image yet, and nothing follows a session PR
  once the chat ends: the loop gate tracks only the worker's registered PRs.
- 8 of them were `CONFLICTING`. GitHub runs no `pull_request` checks on a conflicting PR, so
  the loop gate saw "pending" forever and the stale rule would have closed its own PRs.
- The release-please PR (Lucky #2893) is opened with the owner's token. Its author is the
  owner, so nothing in the merge check kept it out; only its paths (`package.json`, lockfile)
  did. Merging it ships a release and starts the deploy.
- When the `ready-for-agent` queue runs dry the worker does nothing until the owner writes
  new issues.

## Decision

1. **Release and bot PRs are never the agent's.** `merge_check` refuses a head branch in
   `merge_block_branches` (`release-please--*`, `dependabot/*`, `renovate/*`) or a label in
   `merge_block_labels` (`autorelease: pending`, `autorelease: tagged`), and fails closed when
   either field is missing. pr-automerge now loads `headRefName` and `labels`. A direct merge
   (`gh pr merge` without `--auto`) and `--admin` stay denied for the model in every permission
   file; pr-automerge only ever queues `--auto` pinned to the checked head, or turns it off.
2. **The loop gate follows session PRs.** `session_prs` lists open owner PRs from the same repo
   whose head commit is the tip of the local branch of the same name in the agent-box clone
   (the Discord session cut and pushed it there; an old local copy or a push from elsewhere
   does not count), whose branch `claude_cmd` accepts (`BRANCH_RE`), minus loop PRs. They are
   scored with `score --session`: release or bot PR -> `skip` (silent); another human, a fork
   or unfetched threads -> `halt`; draft or `needs-human` -> `wait`; wrong base or stacked ->
   `needs-human`; truncated file list, an unchecked closing issue or owner paths ->
   `owner-review` before any fix run; conflict, red CI or bot-only threads -> `autofix`;
   pending -> `wait`; else `queue`, which runs `pr-automerge <repo> <n>`. Session PRs are never
   stale-closed or split. Thread replies go through `pr-automerge --replies`, so its thread
   check decides what is posted as the owner. The whole path is off until
   `command -v pr-automerge` succeeds on agent-box. An autofix waits an hour after the PR last
   changed and skips while the clone has a branch checked out (the loop leaves it detached on
   `origin/<base>`; a branch there means a chat is or was last working in it).
3. **Conflicts are fixed by merging the base in.** Both scorers send `mergeable == CONFLICTING`
   to `autofix` (fix `conflict`) before looking at checks. The gate checks out the branch, runs
   `git merge --no-edit origin/<base>` and hands only a real conflict (unmerged paths) to the
   model, which resolves, tests, commits with `--no-edit` and pushes with the plain
   `git push origin <branch>` rule. Never a rebase or force-push. Cleanup runs
   `git merge --abort` before detaching. The model cannot run `git merge` itself.
4. **Fix cap.** `fix_attempts` goes from 2 to 3, shared by CI, thread and conflict fixes per PR.
   At the cap the PR gets `needs-human` and one Discord alert per head commit.
5. **Backlog round.** When the worker finds no eligible issue, `backlog_round` runs at most once
   a day per repo (marker written before the run) and only while fewer than
   `backlog_round_max` (5) open `ready-for-agent` issues are being skipped. A read-only claude
   run (`claude_plan_cmd`) writes `backlog.json`. It gets Read on the repo workdir only, Glob,
   Grep and Edit inside its scratch dir: no Bash at all (`git grep -O` runs a command and
   `git log --output` writes a file), and `GITHUB_TOKEN`, `GH_TOKEN` and the Discord webhook are
   unset in its environment. Its prompt carries the last 50 commits and only the owner's issue
   titles (anyone can open an issue on a public repo). `agent_gate.py backlog-plan` then
   dedupes against every issue title, open or closed (same words after the conventional
   prefix, or 80% overlap), drops titles outside 10-120 characters, bodies over 4000, any
   `@mention` or slash command and anything shaped like a token, key or webhook URL, caps the
   round, and labels `ready-for-agent` + `effort:s` only when the model said `agent: true` and
   neither title nor body has a picker skip word; everything else is `ready-for-human`. A
   planning run that leaves the clone dirty creates nothing. The worker creates the issues as
   the owner and sends one Discord summary.
6. **Secrets are unreadable for every loop run.** `claude_disallowed_tools` now carries the
   Read denies the Discord session already had (`/etc/profile.d/agent-env.sh`, `~/.config/gh`,
   `~/.claude.json`, credentials, `/run/secrets`) plus `env`, `printenv` and `cat` of those
   paths.

## Options considered

- **Record session PRs in a registry from pr-create-guard.** Not now: the guard runs before the
  PR exists (no number), and the 25 PRs parked on 2026-10-19 would have no entry. "Head commit
  equals the clone's local tip" already drops stale local copies and pushes from elsewhere.
- **Run each autofix in its own `git worktree`.** Not now: a fresh worktree has no
  `node_modules` or generated clients (Lucky needs `db:generate`), so CI fixes would fail or
  reinstall every run. The detached-HEAD check keeps the gate out of a clone a chat holds.
- **Rebase conflicting branches.** Rejected: needs a force-push, denied by design.
- **Let the model call `gh issue create`.** Rejected: issue text is posted as the owner and
  picked up by the loop; the deterministic `backlog-plan` check decides what is created.

## Consequences

- Session PRs merge without the owner once CI is green, threads are resolved and nothing
  sensitive is touched; the loop fixes red CI, bot threads and conflicts in the meantime.
- Throughput is bounded by `AGENT_MAX_RUNS_PER_DAY` (6) and one autofix per repo per run. With
  25 parked PRs the owner may raise the budget for a few days.
- A stacked set (cojam 459-473 on 2026-10-19) goes to `needs-human`: rebuilding it is the
  owner's call. The gate does not turn off an auto-merge it did not queue.
- Generated issues may be wrong or low value. They are capped at 5 a day per repo and carry
  the normal picker rules; the owner can close them or add `blocked`.
- Accepted risk (owner, 2026-10-19: autonomy needs auto-fix and auto-merge): a generated
  `ready-for-agent` issue is owner-authored, so its PR passes the value pillar without an owner
  touch and can auto-merge when the size, impact and CI pillars allow it. Sensitive topics in
  title or body go to `ready-for-human`, and owner paths still block the merge.
- Owner actions that strengthen the queued-merge path: thread resolution in the cojam ruleset
  and in homelab `release` protection (ADR 0042).
