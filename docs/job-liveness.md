# Job liveness — no scheduled job dies silently

Generalizes the ADR-0026 dead-man pattern to **every** cron and systemd unit.
Motivated by 2026-07-08/09, when three separate scheduled jobs were found dead
with zero signal — the Lucky DB backup (weeks, no dumps), the resilience
watchdog itself (Python `SyntaxError`), and the offsite mirror (lost exec bit).
Root cause of the whole class: scheduled jobs logged to a file nobody read, and
nothing watched `systemctl --failed`.

## Model

Every job reports to the self-hosted **Healthchecks** instance
(`http://localhost:${HEALTHCHECKS_PORT:-8092}`). If a job stops pinging or starts
failing, Healthchecks emails — a path independent of Discord (which #296/#1651
showed can itself silently break). Uses **slug-based pinging with one project
ping key**, so checks auto-provision (`?create=1`) — no per-job secret.

Two complementary mechanisms:

| Mechanism | Covers | How |
|-----------|--------|-----|
| `hc-run.sh <slug> -- <cmd>` | **cron jobs** | wraps a command; pings start / success / fail with output as the body |
| `systemd-failed-check.sh` | **all systemd units at once** | one cron pings fail if *any* unit is in failed state (with the list) |

## Setup (operator — involves the ping key, a secret)

1. In Healthchecks → your project → **Ping key** (create if absent). Add to
   `~/homelab/.env` (never committed):
   ```
   HEALTHCHECKS_PING_KEY=<project ping key>
   ```
2. Wrap the cron jobs (idempotent, backs up + shows a diff before installing):
   ```sh
   ~/homelab/scripts/maintenance/install-liveness-crontab.sh
   ```
   Wraps: `lucky-db-backup`, `containers-weekly-update`, `docker-weekly-cleanup`.
3. Add the systemd watcher to cron (every 15 min):
   ```
   */15 * * * * /home/luk-server/homelab/scripts/maintenance/systemd-failed-check.sh >> /home/luk-server/homelab/logs/systemd-failed.log 2>&1
   ```
4. In Healthchecks, set each auto-created check's **period + grace** to match its
   schedule (e.g. `lucky-db-backup` = 1 day period / 2h grace; `systemd-failed-units`
   = 20m/10m) and confirm the email integration is attached.

## Verify

- `systemd-failed-check.sh` prints failed units + exits with the count. On a
  healthy host: `OK: no failed units`, exit 0.
- Break a check on purpose (stop a wrapped cron for > period+grace) → Healthchecks
  should email. Then restore.

## Fail-open guarantee

Both scripts run the real work regardless of Healthchecks: if `HEALTHCHECKS_PING_KEY`
is unset or the instance is unreachable, the job still executes and its exit code
is preserved. Liveness reporting must never block the work it watches.

## Known failed units found when this shipped (2026-07-09)

`systemd-failed-check.sh` immediately surfaced a backlog of silent failures —
exactly the point:
- `homelab-watchdog` — fixed (PR #363), revives on `make deploy`.
- `kopia-offsite-sync` — target `192.168.0.3` sshd refused (#361).
- `logrotate` — **NEW** (logs may not be rotating → disk-fill risk; triage).
- `satisfactory-server` — **NEW** (game server crashed; triage or disable).

## Related
- ADR-0026 (dead-man-switch for notifications) — this generalizes it.
- #360 (this), #361 (offsite), PR #362 (kopia covers DB dumps), PR #363 (revived jobs).
