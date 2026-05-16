# Lucky observability runbook

Each section corresponds to a single alert in `config/prometheus/alerts.yml`
(group `lucky_alerts`). Sections are linked from the alert's
`annotations.runbook` field and surface in Alertmanager / Slack /
Grafana notifications.

**Default escalation:** maintainer is the operator; there is no on-call
rotation. Investigate first, escalate only if data loss / public outage.

**Common first step for every alert:** check the Lucky app dashboard in
Grafana ("Lucky — Application Metrics", uid `lucky-app-metrics`) for the
visual context, then drill into the linked subsystem.

---

## LuckyBotDown

**Means:** Prometheus has not scraped `lucky-bot:9091/metrics`
successfully for 2 minutes (`up{job="lucky-bot"} == 0`).

**Likely causes:**
1. Bot process crashed / OOMKilled
2. `METRICS_DISABLED=true` set on the bot env
3. Bot container removed from the `lucky-monitoring` external network
4. `METRICS_PORT` changed without updating the scrape target

**Investigate:**
```bash
ssh luk-server@192.168.0.11
cd lucky
docker compose ps bot
docker compose logs bot --tail=200
# Direct metrics check (inside the bot container)
docker compose exec bot wget -qO- http://localhost:9091/metrics | head -20
# Network membership
docker network inspect lucky-monitoring | jq '.[0].Containers'
```

**Fix:**
- Crash → restart `docker compose restart bot`; check stack trace in
  Sentry for the underlying cause.
- Wrong network → ensure `bot` service in `lucky/docker-compose.yml` has
  `networks: [lucky-network, lucky-monitoring]` and the network is
  declared as `external: true`.
- Disabled → unset `METRICS_DISABLED` env var.

---

## LuckyBackendDown

Same shape as `LuckyBotDown` but for `lucky-backend:5000/metrics`.

**Quick check:**
```bash
docker compose exec backend wget -qO- http://localhost:5000/metrics | head -20
```

The backend's `/metrics` is mounted before the `/api` rate limiter, so
401 / 429 should not appear.

---

## LuckyGuildCountDropping

**Means:** `lucky_bot_guilds_total{state="active"}` dropped >5% over a
10-minute rolling window.

**Triage path:**
1. Open Grafana → "Lucky — Application Metrics" → "Active guilds over
   time" panel. Confirm the drop is real (not just a single-scrape blip).
2. Check `lucky_bot_guilds_total{state="left"}` — did it INcrease by the
   same amount? If yes, real departures. If no, the bot may be failing
   to report a guild that hasn't actually left.
3. Cross-check the bot logs:
   ```bash
   docker compose logs bot --since 30m | grep -E "guildDelete|Left guild"
   ```

**Common real causes:**
- Mass kick from a network of servers (bot was added under false pretenses)
- ToS-flagged behavior that triggered Discord-side removal
- Owner of a megaserver cleaning up unused bots

**Common false-positive causes:**
- Deploy that briefly disconnected and re-connected the bot (the gauge
  is computed on-scrape from the DB, so this should self-heal within
  one scrape interval)
- DB outage that made the count query return 0 (look for `prometheus:
  failed to collect lucky_bot_guilds_total` in bot logs)

**Action if real:**
- Identify the deltas by querying the audit table:
  ```sql
  SELECT guild_discord_id, guild_name, kind, occurred_at
  FROM guild_membership_events
  WHERE occurred_at > now() - interval '15 minutes'
  ORDER BY occurred_at DESC;
  ```
- Post a short note in the Lucky Discord support channel if the drop
  was >50 guilds — community usually notices.

---

## LuckyBackendHighErrorRate

**Means:** A specific backend route is returning >0.1 5xx responses per
second, sustained 5 minutes.

**Triage:**
1. Read the `route` label off the alert — it's the Express route
   template (e.g. `/api/guilds/:guildId/settings`), not a raw path.
2. Open Sentry (project `lucky-backend`) and filter to that route — the
   stack trace is the actual root cause.
3. Cross-check the request rate on the dashboard panel "Backend request
   rate" — high error rate at very low total volume can be a single
   misbehaving client retrying; high at high volume is a real outage.

**Common causes:**
- Discord API 5xx propagating through (look for `discord.com` in stack)
- DB connection pool exhausted (look for `prisma` errors)
- Downstream service down (Spotify / Last.fm)

---

## LuckyBackendHighLatency

**Means:** p95 latency on a route >1s sustained 10 minutes.

**Triage:**
1. Compare p50 vs p95 on the dashboard latency panel. p95-only spike =
   long tail / a few slow requests. p50 + p95 climbing together = the
   whole route is slow (DB or downstream).
2. Open Sentry → Performance → filter to the route. Look at the trace
   waterfalls for the slow spans.

**Common causes:**
- Missing DB index on a query touched by the route
- Slow downstream API not honoring our timeout
- N+1 query pattern (look for repeated identical queries in the trace)

---

## LuckyBotEventLoopBlocked

**Means:** Node.js event loop p99 lag >200ms sustained 5 minutes.

**Triage:**
1. Compare against the heap panel — if heap is also climbing, this is
   GC pressure, not a hot path. Restart usually clears it.
2. If heap is flat: there's a sync hot path. Common offenders:
   - `JSON.parse` on a huge Discord payload (audit logs, etc.)
   - Regex over a large string (lyrics scraping, content moderation)
   - Synchronous file I/O on the request path
3. Take a CPU profile: send `SIGUSR2` to the bot if Inspector is on,
   or attach Chrome DevTools via `--inspect`.

---

## LuckyBotHeapHigh

**Means:** V8 heap >90% full sustained 10 minutes. Imminent OOMKilled.

**Triage:**
1. Did this start after a deploy? `git log --oneline -10 origin/main`
   on the Lucky repo. Likely a regression.
2. Otherwise: collect a heap snapshot before restart:
   ```bash
   docker compose exec bot kill -SIGUSR2 1
   # snapshot goes to /app
   docker compose cp bot:/app/heap-*.heapsnapshot ./
   ```
3. Restart to recover service: `docker compose restart bot`.
4. Analyze the snapshot in Chrome DevTools → Memory tab. Look for
   "Comparison" mode if you have a baseline snapshot from a healthy run.

**Action:** if leak found, file an issue with the snapshot attached and
the suspect retainer path.

---

## Adding a new alert

1. Add the alert to `lucky_alerts` in `config/prometheus/alerts.yml`.
   Always include `service` label (`lucky-bot` or `lucky-backend`) for
   routing.
2. Add a section here with the same heading-anchor as the
   `annotations.runbook` value.
3. Reload Prometheus rules: `docker compose kill -s HUP prometheus`.
   Verify in Prom UI → Status → Rules.

## Adding a new dashboard panel

The dashboard is provisioned from
`config/grafana/provisioning/dashboards/lukbot/lucky-app-metrics.json`.
Edit in Grafana UI, then "Save → Show JSON" and replace the file. Commit
the diff. Provisioning auto-reloads on the next interval (10s).
