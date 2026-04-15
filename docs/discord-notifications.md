# Discord notification channels

The homelab watchdog, What's-Up-Docker, Alertmanager, and the update-containers job
each send alerts to a dedicated Discord webhook. Keys live in `.env`:

| Env var | Source | Channel purpose |
|---|---|---|
| `WATCHDOG_DISCORD_WEBHOOK` | `scripts/maintenance/homelab-watchdog.sh` | Degraded-state + recovery-ladder + reboot escalation |
| `WUD_DISCORD_WEBHOOK_URL` | What's-Up-Docker container env | New image version available for any running container |
| `ALERTMANAGER_DISCORD_WEBHOOK` | Prometheus Alertmanager | Metric-based alerts |
| `UPDATE_DISCORD_WEBHOOK_URL` | `scripts/maintenance/update-containers.sh` | Cron-driven `docker compose pull` / `up -d` summary |

## Health check
```bash
bash scripts/monitoring/test-discord-webhooks.sh
```
Exit code 0 = all webhooks return HTTP 200. Non-zero = one or more are broken (404 = the webhook was deleted inside Discord and must be regenerated).

## Regenerating a webhook
Discord → channel gear → Integrations → Webhooks → New / Copy Webhook URL → paste into the matching key in `.env`. No container restart needed for script-based hooks; WUD and Alertmanager need a `docker compose up -d <svc>` to re-read the env.
