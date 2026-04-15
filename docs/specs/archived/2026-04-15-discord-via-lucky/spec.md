---
status: shipped
created: 2026-04-15
shipped: 2026-04-15
owner: lucassantana
pr: https://github.com/LucasSantana-Dev/homelab/pull/16
tags: discord,notify,watchdog
---

# discord-via-lucky

## Goal
Replace dead webhook URLs with Lucky bot's new /api/internal/notify endpoint so homelab alerts keep flowing.

## Approach
- homelab-watchdog.sh send_discord() now POSTs {channelId, content} to http://localhost:8090/api/internal/notify with X-Notify-Key.
- LUCKY_NOTIFY_URL + LUCKY_NOTIFY_KEY + LUCKY_NOTIFY_CHANNEL_ID env.
- CRITICAL_CONTAINERS list fixed to actual deployed services.
- send_discord logs HTTP code on failure.
- Companion: scripts/monitoring/test-discord-webhooks.sh validator.

## Verification
- Manual curl to /api/internal/notify returns 204 with Lucky bot user posting in #homelab (Palácio do Loló).
- Watchdog tick visible in Discord.
