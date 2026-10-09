# Agent loop: autonomous development on agent-box

Headless `claude -p` (official binary, Max OAuth login) picks groomed issues, opens PRs and keeps
them moving. The guards live outside the model: token scope, the GitHub ruleset and these
wrappers. The agent-box hooks are an extra layer.

| Piece | File |
|---|---|
| Policy and thresholds | `config/agent-box/agent-gate.json` |
| Gate and issue picker (stdlib Python, tested) | `scripts/agent-tasks/agent_gate.py`, `tests/unit/test_agent_gate.py` |
| PR gate (runs first) | `scripts/agent-tasks/agent-pr-gate.sh` |
| Worker (runs second) | `scripts/agent-tasks/agent-worker.sh` |
| Schedule | `systemd/agent-loop.{service,timer}` (04, 10, 15, 20h) |

## Anti-pile-up rules

- At most `wip_cap` (2) open agent PRs per repo. When full, the worker starts nothing new.
- One issue and at most `AGENT_MAX_AUTOFIX_PER_RUN` (1) autofix per repo per run, under a lock. Daily budget of `AGENT_MAX_RUNS_PER_DAY` (6) claude runs, shared by worker and autofix.
- Autofix at most `fix_attempts` (2) per PR, then `agent-failed` + `needs-human`.
- PRs idle for `stale_days` (5) are closed and the issue gets `agent-failed`, so it is not picked again.
- Any PR or issue another human authored, commented on or pushed to is never touched.
- Pause everything: `touch ~/agent-paused` inside agent-box (resume: `rm ~/agent-paused`).

## Issue selection

Open, `ready-for-agent`, `effort:s`, authored by the owner, no foreign comments, no open agent PR,
no skip label, no sensitive word in title or labels (auth, oauth, payment, billing, deploy, migration,
workflow, secret). Ranked: bug/docs/ci/test first, then P1, then oldest.

## Merge gate: 4 pillars

| Pillar | Green | Yellow | Red |
|---|---|---|---|
| Size | <= 150 lines and <= 5 files | <= 400 lines and <= 12 files | larger: split it |
| Impact | only docs, tests, ESLint/Prettier config | runtime code | `.github/`, migrations, SQL, Dockerfile, compose, deploy, infra, Makefile, agent rules (CLAUDE.md, AGENTS.md, `.claude/`), the agent loop itself, > 2 modules |
| Value | closes an owner `ready-for-agent` issue that is P1 or bug, with a new test | closes an owner issue | no linked issue, or issue not owner/ready-for-agent |
| Security | no sensitive path, no manifest change, checks green | dependency manifest changed, checks pending or failing | a `sensitive_paths` match: auth, oauth, secret, token, credential, password, session, jwt, permission, payment, billing, crypto, env files, certificate and `.key` files, npm config (`agent-gate.json` is the source of truth) |

Decision order (pillars before CI, so a risky PR never gets an autofix run): value red -> `close`;
security or impact red -> `needs-human`; size red -> `split`; failing checks -> `autofix` (CI);
pending or no checks yet -> `wait`; unresolved review threads only from `bots` listed in
`agent-gate.json` -> `autofix`
(threads); an unresolved thread the owner joined -> `owner-review`; 4 greens and `auto_merge: true`
-> `auto-merge`; else `owner-review`. A PR or linked issue authored, commented on or pushed to by
another human (or a deleted account), including inside a review thread -> `halt`. In threads only a
GitHub App (`__typename: Bot`) on that list counts as a bot (another App's thread waits for the
owner), and more than 100 threads or 50 replies in one
thread (unfetched pages) -> `halt`. If the linked issue or the review threads (GraphQL) cannot be
loaded, the PR is skipped for that run.

Thread autofix: the worker verifies each bot claim against the code (at most 20 threads per run),
fixes the valid ones (adding or updating a test when behaviour changes), and writes
`.git/agent-thread-replies.json`
(`[{"id", "fixed", "reply"}]`). The model may not call `gh api` (a GraphQL mutation could merge),
so the gate posts the replies itself, after checking the tree is clean, `origin/<branch>` has every
local commit, and (reloading the PR and the issue) no human joined and the owner did not join a
thread during the run. Only threads marked fixed with
a new pushed commit are resolved; a dismissed claim keeps its thread open with the reply, which sends
the PR to `owner-review`. CI and thread fixes share the `fix_attempts` counter per PR (some bots
re-post identical threads on every push), then `needs-human`. Stale-close never applies to thread
autofix.

For `owner-review`, `needs-human`, `split` and `auto-merge` the gate posts one comment per head
commit with the grades; `wait` and `autofix` post nothing until the fix cap is hit. Stale-close applies only to
`wait` and CI `autofix` PRs, never to ones waiting on the owner.

## Graduation

- Phase 1 (now): `auto_merge: false`. The gate grades and comments; the owner merges. Compare the grade with your merge decision.
- Phase 2: after 10 agent PRs merged without rework and the grade matching your decision in at least 9 of 10, set `auto_merge: true`. Merges use `gh pr merge --auto --squash --match-head-commit`, so required checks still gate.
- Brake: if an auto-merged PR is reverted or breaks the base branch, set `auto_merge: false` and tighten the pillar that missed.

## Worker permissions

Every `claude -p` run (worker and autofix) gets its mode and allow/deny lists from
`agent-gate.json` via `claude_cmd`. Push is not in the config: `claude_cmd` takes the run's branch,
refuses anything outside `agent/`, and allows exactly `git push origin <branch>` and
`git push -u origin <branch>`. A rule with no `*` matches one exact command, so refspecs
(`agent/x:main`, `+agent/x`), `--force` and `--delete` are not allowed; the deny list repeats them as
a backstop. The colon deny is `Bash(git push*:**)`: a pattern ending in `:*` is Claude Code's prefix
syntax, and `Bash(git push*:*)` matches nothing (verified on 2.1.292). `Edit(/.github/**)` blocks
workflow edits from the repo root; Edit rules also cover the Write tool, and `Write(path)` rules are
ignored. Bash rules are not a security boundary (`git -C . push` or a script can get around
them); in dontAsk mode the exact allow entries are what keeps those forms out.

Accepted risk (owner decision, 2026-10-09): `Bash(npm *)`, `npx *`, `pnpm *`, `node *`,
`python3 *` and `cat *` stay allowed, because lint, typecheck and tests in the agent repos need
them. That is arbitrary code execution and file reads as the `agent` user with `agent-env.sh`
sourced, so a run (or a prompt injection through issue text, or review-bot text, which reaches the
autofix prompt since #489) can read the GitHub PAT and the Claude login, and can use the PAT
directly instead of going through `gh` or `git push`. What limits the damage: the PAT is
fine-grained to the agent repos (contents, pull requests, issues; no workflows, no admin), base
branches require a PR plus CI and Sonar, and the owner merges (`auto_merge: false`). Scoping the
allow list to named scripts would not help much, since `npm test` runs repo-controlled scripts the
agent can edit. The real fix is the Claude Code Bash sandbox, which agent-box cannot run (see the
Discord section). If the PAT leaks: revoke it, issue a new fine-grained token and replace
`AGENT_GITHUB_TOKEN`.

## Install (host, as luk-server)

Prerequisites, in order:
1. PAT rotated (backlog B4) to a fine-grained token limited to the agent repos: contents, pull_requests, issues write; no workflows, no admin.
2. Ruleset on the base branch: PR required, CI and Sonar required.
3. Inside agent-box, `env -u ANTHROPIC_API_KEY claude -p "say ok"` works and `/status` shows the Max login, not an API key.

Then:

```bash
AGENT_DRY_RUN=1 bash scripts/agent-tasks/agent-pr-gate.sh
AGENT_DRY_RUN=1 bash scripts/agent-tasks/agent-worker.sh
sudo cp systemd/agent-loop.service systemd/agent-loop.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now agent-loop.timer
```

Repos in scope: `AGENT_REPOS` (script default `LucasSantana-Dev/Lucky`; `agent-loop.service` sets Lucky and cojam). Configured repos: Lucky,
homelab (PRs target `release`) and cojam. cojam needs issues labeled `ready-for-agent` plus
`effort:s` before the picker selects anything.

## Discord channel (phase 3)

Bot `luk-agent` (app 1557913205966246039, not Lucky) talks to the owner by DM through the official
Claude Code channel plugin, in a tmux session on agent-box. The channel reports queue status,
creates `ready-for-agent` issues and pauses/resumes the loop. It never merges. Session rules:
`config/agent-box/discord-channel.md`.

Pieces. The image carries the supervisor, the session settings and rules; the SOPS values and
the plugin install are runtime state:

- SOPS keys in `secrets/agent-box.secrets.yaml.age`: `DISCORD_BOT_TOKEN` and `DISCORD_OWNER_ID` (the
  owner's Discord user ID). Set them with `scripts/security/agent-box-secret-set.sh KEY` on the
  host (value on stdin; validates the token against the bot's app ID, round-trip check, backup),
  then `docker restart agent-box`. On every boot the entrypoint writes the token to
  `~agent/.claude/channels/discord/.env` (0600), writes the owner ID to the root-owned
  `/etc/agent-box/discord-owner-id`, re-renders `access.json` from it, then unsets the token. Neither
  value goes into `agent-env.sh`.
- `config/agent-box/discord-channel.sh`: supervisor started by the entrypoint (log: `docker logs
  agent-box`). Every 30s, if the tmux session `discord` is gone, it starts `claude --channels
  plugin:discord@claude-plugins-official` with `DISCORD_ACCESS_MODE=static`, no API key (Max
  login), `--permission-mode default` and `discord-channel-settings.json` (enables the plugin for
  this session only; read-only allow list; denies secrets, `env`, `gh api`, PR merge/close/review,
  `git push`). It fails closed: no start unless the token and the plugin exist and `access.json`
  allows exactly the root-owned owner ID, with no guild groups. It pre-accepts the `/workspace`
  trust dialog, installs the plugin's bun dependencies before the first start, turns off
  the claude.ai connectors and prompt suggestions for the session, logs claude's exit code, backs
  off on fast exits (up to 15 min) and logs a warning when claude sits at a prompt or the bun MCP
  server is gone.
- `config/agent-box/discord-channel.md`: session rules, appended to the system prompt.

One-time setup inside agent-box, as `agent` (the plugin lives in the persistent volume):

```bash
claude plugin install discord@claude-plugins-official
```

Then `docker restart agent-box` on the host: the install also enables the plugin in the user
settings, which the entrypoint overwrites on boot; until then loop runs would load it too.

No pairing: static mode downgrades `pairing` to `allowlist` and never writes `access.json`, so
nothing said in the chat can widen access. Permission prompts reach the owner's DM as buttons.
Never start it with `--dangerously-skip-permissions`.

Accepted risk (owner decision, 2026-10-09, #485): the loop worker runs as the same unix user, so
`Bash(cat *)` can read the bot token file even though its gate denies Read/Edit on
`~/.claude/channels/**`. A leaked token lets someone post as the bot and read its DMs; it cannot
command the agent, because inbound messages must come from the root-owned owner ID, and tampering
with `access.json` only stops the channel. The loop can already read its own GitHub PAT and Claude
login, which matter more, so a separate unix user for the channel (a second Max login) was not
worth it. Claude Code's Bash sandbox is not available: unprivileged user namespaces are blocked
(Docker seccomp, `kernel.apparmor_restrict_unprivileged_userns=1`). If the token leaks: Reset
Token, store it with `agent-box-secret-set.sh`, restart agent-box.
The same uid can also stop the supervisor and run its own channel session; the allowlist only
holds against people on Discord, not against code already running as `agent`.

Boot fails closed: the entrypoint writes agent config as `agent` (never as root into agent
paths) under `set -e`, so if something under `/home/agent` blocks it (for example a directory
where `~/.claude/settings.json` should be), the container restarts without sshd. Recover with
`docker exec agent-box ...` from the host, or `docker logs agent-box` to see which step failed.

Stop: `touch ~/discord-channel-off && tmux kill-session -t discord` (resume: `rm ~/discord-channel-off`).
Rotate the token: Reset Token in the Developer Portal, store it in SOPS, `docker restart agent-box`.
