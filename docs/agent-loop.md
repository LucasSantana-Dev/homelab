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
- One issue per repo per run, under a lock. Daily budget of `AGENT_MAX_RUNS_PER_DAY` (6) claude runs, shared by worker and autofix.
- Autofix at most `fix_attempts` (2) per PR, then `agent-failed` + `needs-human`.
- PRs idle for `stale_days` (5) are closed and the issue gets `agent-failed`, so it is not picked again.
- Any PR or issue another human authored or commented on is never touched.
- Pause everything: `touch ~/agent-paused` inside agent-box (resume: `rm ~/agent-paused`).

## Issue selection

Open, `ready-for-agent`, `effort:s`, authored by the owner, no foreign comments, no open agent PR,
no skip label, no sensitive word in title or labels (auth, oauth, payment, deploy, migration,
workflow, secret). Ranked: bug/docs/ci/test first, then P1, then oldest.

## Merge gate: 4 pillars

| Pillar | Green | Yellow | Red |
|---|---|---|---|
| Size | <= 150 lines and <= 5 files | <= 400 lines and <= 12 files | larger: split it |
| Impact | only docs, tests, lint config | runtime code | `.github/`, migrations, SQL, Dockerfile, compose, deploy, infra, Makefile, agent rules (CLAUDE.md, AGENTS.md, `.claude/`), the agent loop itself, > 2 modules |
| Value | closes an owner `ready-for-agent` issue that is P1 or bug, with a new test | closes an owner issue | no linked issue, or issue not owner/ready-for-agent |
| Security | no sensitive path, no manifest change, checks green | dependency manifest changed, checks pending or failing | auth/oauth/secret/token/password/session/permission/payment/crypto/key/.env paths |

Decision order (pillars before CI, so a risky PR never gets an autofix run): value red -> `close`;
security or impact red -> `needs-human`; size red -> `split`; failing checks -> `autofix`; pending or
no checks yet -> `wait`; 4 greens and `auto_merge: true` -> `auto-merge`; else `owner-review`.
A PR or linked issue with a comment from another human (or a deleted account) -> `halt`.
The gate posts one comment per head commit with the grades. Stale-close applies only to
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

Repos in scope: `AGENT_REPOS` (default `LucasSantana-Dev/Lucky`). Add homelab only after the pilot;
its PRs target `release`.

## Discord channel (phase 3)

A separate Discord bot for the agent (not Lucky), using the official Claude Code channel plugin in a
tmux session on agent-box:

```bash
claude plugin install discord@claude-plugins-official
claude --channels plugin:discord@claude-plugins-official
```

Inside the session: `/discord:configure <bot token>`, pair from a DM, then
`/discord:access policy allowlist` so only the owner's account is accepted. Never start it with
`--dangerously-skip-permissions`: approval prompts are relayed to Discord. The channel may create
`ready-for-agent` issues, report queue status and pause/resume the loop. It never merges.
