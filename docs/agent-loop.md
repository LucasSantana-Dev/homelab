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
security or impact red -> `needs-human`; size red -> `split`; failing checks -> `autofix`; pending or
no checks yet -> `wait`; 4 greens and `auto_merge: true` -> `auto-merge`; else `owner-review`.
A PR or linked issue authored, commented on or pushed to by another human (or a deleted
account) -> `halt`. If the linked issue cannot be loaded, the PR is skipped for that run.
For `owner-review`, `needs-human`, `split` and `auto-merge` the gate posts one comment per head
commit with the grades; `wait` and `autofix` post nothing until the fix cap is hit. Stale-close applies only to
`wait`/`autofix` PRs, never to ones waiting on the owner.

## Graduation

- Phase 1 (now): `auto_merge: false`. The gate grades and comments; the owner merges. Compare the grade with your merge decision.
- Phase 2: after 10 agent PRs merged without rework and the grade matching your decision in at least 9 of 10, set `auto_merge: true`. Merges use `gh pr merge --auto --squash --match-head-commit`, so required checks still gate.
- Brake: if an auto-merged PR is reverted or breaks the base branch, set `auto_merge: false` and tighten the pillar that missed.

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

Known gap: the loop worker runs as the same unix user. Its gate denies Read/Edit/Write on
`~/.claude/channels/**`, but `Bash(cat *)` can still read the token file, as it can read the
Claude and gh credentials today. Tampering with `access.json` only blocks the channel (the
supervisor refuses to start); it cannot add an ID. The real fix is a separate unix user for the
channel.

Stop: `touch ~/discord-channel-off && tmux kill-session -t discord` (resume: `rm ~/discord-channel-off`).
Rotate the token: Reset Token in the Developer Portal, store it in SOPS, `docker restart agent-box`.
