# Ops alert digest — cross-source feed (ADR-0025 Phase 2)

Unify the non-Prometheus event sources (**Sentry**, **healthchecks.io**, **WUD**)
into one Discord feed. Prometheus alerts are NOT here — they go directly via
Alertmanager (ADR-0025 keeps that path direct, no n8n in the critical path).

> **Decide first — do you even need n8n?** Each source can already post to Discord
> natively. If all you want is "one feed," the cheapest Phase 2 is **Option A**
> (zero n8n). Use **Option B** (n8n) only if you need rollup (e.g. WUD's many
> update pings collapsed into "5 images updated") or cross-source dedup.

## Option A — native integrations → one `#digest` channel (no n8n)

1. Create a Discord webhook for a `#digest` channel (Server Settings → Integrations
   → Webhooks → New).
2. Point each source at it:
   - **WUD:** configure a Discord **trigger** — WUD uses `WUD_TRIGGER_DISCORD_{name}_URL`
     (e.g. `WUD_TRIGGER_DISCORD_digest_URL=<webhook>`), **not** a bare
     `WUD_DISCORD_WEBHOOK_URL` (that var is ignored by WUD — see the wiring bug noted below).
   - **healthchecks.io:** per-check → Integrations → Discord → that webhook.
   - **Sentry:** Project → Alerts → add a Discord notification action to that channel.

Done. No workflow to maintain. Revisit Option B only if the raw volume is noisy.

## Option B — n8n aggregator with rollup (`config/n8n/workflows/ops-digest.json`)

A single n8n webhook receives all three, normalizes them, and posts to Discord
(extend the Code node for rollup/batching later).

1. **Import the workflow:** n8n UI → Workflows → Import from File →
   `config/n8n/workflows/ops-digest.json`. (Or `POST /api/v1/workflows` with an
   API key from n8n → Settings → API.)
2. **Set the Discord target** the workflow posts to — add `OPS_DIGEST_DISCORD_WEBHOOK`
   to the n8n container env (a Discord webhook URL), then restart n8n.
3. **Activate** the workflow. Its endpoint is
   `https://n8n.<domain>/webhook/ops-digest` (n8n's `WEBHOOK_URL` is already set).
4. **Point each source at it** (add `?source=sentry|healthchecks|wud` so the
   normalizer can branch reliably):
   - **WUD:** `WUD_DISCORD_WEBHOOK_URL` → `https://n8n.<domain>/webhook/ops-digest?source=wud`
     (WUD posts Discord-shaped JSON; the Code node reads `body.container`).
   - **healthchecks.io:** per-check webhook → `.../ops-digest?source=healthchecks`.
   - **Sentry:** project webhook/alert → `.../ops-digest?source=sentry`.
5. **Rollup (optional, later):** batch WUD events in the Code node (or an n8n
   Schedule trigger that drains a buffer daily) instead of one message per update.

### Dependencies / gotchas

- **A working Discord webhook is required either way.** As of 2026-06-21 the
  Alertmanager Discord webhook was found dead (404 Unknown Webhook — issue #296);
  mint a fresh one before wiring this, and reuse a valid one here.
- **WUD Discord wiring bug:** `compose/core.yml` sets `WUD_DISCORD_WEBHOOK_URL` on
  the WUD container, but WUD does not recognise that variable (it reads
  `WUD_TRIGGER_DISCORD_{name}_URL`), so WUD's own Discord notifications have not
  been firing. Fix that wiring (or route WUD through n8n via Option B) — tracked
  separately.
- The workflow's `Discord` node is a plain HTTP POST to `OPS_DIGEST_DISCORD_WEBHOOK`
  — no n8n credential needed, just the env var.
- The Code node's source-detection is best-effort on payload shape; the `?source=`
  query param makes it deterministic.
- This is **non-critical** by design: if n8n is down, Prometheus alerts are
  unaffected (they never traverse n8n).
