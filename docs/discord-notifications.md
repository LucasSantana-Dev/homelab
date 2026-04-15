# Discord notifications via Lucky bot

Homelab notifications now route through the Lucky bot's `POST /api/internal/notify`
endpoint instead of channel webhooks. Webhooks were brittle (all 4 went 404 silently);
the Lucky bot keeps its identity as long as it stays in the channel.

## Config (in `~/homelab/.env`)
| Key | Value |
|---|---|
| `LUCKY_NOTIFY_URL` | `http://localhost:8090/api/internal/notify` (lucky-nginx → backend) |
| `LUCKY_NOTIFY_KEY` | Same value as `LUCKY_NOTIFY_API_KEY` set in `~/Lucky/.env` |
| `LUCKY_NOTIFY_CHANNEL_ID` | Discord channel ID — `#homelab` in Palácio do Loló is `1480939399922323567` |

## Test
```bash
curl -sS -m 5 -X POST "$LUCKY_NOTIFY_URL" \
  -H "X-Notify-Key: $LUCKY_NOTIFY_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"channelId\":\"$LUCKY_NOTIFY_CHANNEL_ID\",\"content\":\"hello from homelab\"}" \
  -w "\n%{http_code}\n"
```
Expect `204`.

## Deprecated env vars
The watchdog no longer reads these. Other consumers (WUD, Alertmanager,
update-containers cron) still expect a webhook URL — they migrate next wave
once a webhook-shape adapter wraps the Lucky endpoint. Until then, keep them
populated if you need those alerts.
- `WATCHDOG_DISCORD_WEBHOOK` (now ignored — superseded by LUCKY_NOTIFY_*)
- `WUD_DISCORD_WEBHOOK_URL`
- `ALERTMANAGER_DISCORD_WEBHOOK`
- `UPDATE_DISCORD_WEBHOOK_URL`
