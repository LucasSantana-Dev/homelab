# ADR-0019: Branch Reconciliation — Fetch + Rebase Over Hard Reset

**Status:** Accepted
**Date:** 2026-06-17

## Context

After squash-merging two local commits (homepage PGID fix + v2.6.3 release bump)
via the GitHub web UI, `main` appeared diverged: local had 2 commits not on origin,
origin had 1 squashed hotfix not in local. Same logical content, different commit
structure.

Options evaluated:

| Option | Approach | Risk |
|--------|----------|------|
| A | `git reset --hard origin/main` | Silently loses local commits if content differs |
| B | `git push --force origin main` | Rewrites shared history |
| C | `git pull --rebase origin main` | Surfaces conflicts; safe fallback |
| D | Soft-reset + re-commit + force-push | Complex; same risk as B |
| E | Merge commit | Adds noise; CHANGELOG conflict likely |

Decision-critic (NEEDS_REVISION) flagged 4 unverified claims before acting on
Option A. All 4 verified clean:

1. **Solo operator confirmed** — only `lucas.diassantana@gmail.com` and
   `98131142+LucasSantana-Dev@users.noreply.github.com` in last 30 commits.
   Both are Lucas Santana (local CLI vs GitHub web UI forms).
2. **Content identical** — `git diff 9e62939..9e52e66` across all 4 changed files
   returned empty. No hidden delta.
3. **No conflicts** — `git rebase --onto origin/main <merge-base> HEAD` succeeded
   with "HEAD is up to date." Commits were patch-equivalent; git dropped them
   cleanly.
4. **CI workflows** — checkout actions are pinned by commit SHA, not branch refs.
   No workflow clones `origin/main` by name.

## Decision

Use **Option C (fetch + rebase)** as the default branch reconciliation method,
not Option A (hard reset). Even when content equivalence is strongly suspected,
rebase is safer because:

- It surfaces any delta that slipped past inspection (conflicts = evidence).
- It never silently discards commits — it either applies them or drops them
  with a clear reason (already-applied detection).
- In this specific case, rebase auto-resolved to origin's tip because the local
  commits were patch-equivalent — identical outcome to a hard reset, but
  without the irreversibility risk.

Option A may be used **only after** running the 4 verification checks above and
confirming all pass.

## Consequences

**Positive:**
- Safe reconciliation with zero data loss risk.
- Auto-detection of equivalent patches avoids manual diff inspection.

**Negative:**
- Slightly more verbose than `git reset --hard origin/main`.
- Leaves HEAD detached if run directly on `HEAD`; must follow with
  `git checkout <branch>`.

**Neutral:**
- The underlying cause (local commit + GitHub web squash = apparent divergence)
  should be prevented by using one merge path consistently. Prefer GitHub PR
  merges for all changes; avoid parallel local commits + web squash of the
  same content.

## Revisit When

- A second operator joins the repo (removes "solo operator" verification shortcut).
- CI begins checking out a specific branch by name (invalidates check 4).
- The repo adopts a merge strategy that intentionally creates divergent histories
  (e.g., release branches with cherry-picks).
