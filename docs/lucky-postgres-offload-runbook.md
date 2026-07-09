# Runbook: Offload Lucky Postgres to managed (growth-readiness Phase 1)

Part of the decision to defer Kubernetes ([ADR-0037](./adr/0037-reaffirm-compose-over-kubernetes-2026.md)).
Goal: move Lucky's Postgres off the N100 to a managed provider → free ~0.5–1 GB
host headroom and decouple Lucky's growth from the single box. This is the
highest-leverage answer to "Lucky is growing" — it targets **state**, not
orchestration.

## Current state

- Lucky prod DB runs **on the homelab host** as the `lucky-postgres` container
  (not Supabase — see memory `lucky_prod_db_homelab_not_supabase`). Redis stays
  local (cheap, ephemeral-ish; no offload benefit).
- Staging DB is `lucky-staging-postgres`. **Migrate staging first**, validate,
  then prod.

## Operator decision required (before execution)

Pick a managed Postgres provider. Not auto-chosen — cost/data-residency is the
operator's call:

| Option | Notes |
|--------|-------|
| **Neon** | Serverless Postgres, generous free tier, scale-to-zero; good for bursty bot load. Region: pick EU/US near Discord gateway. |
| **Render Postgres** | Simple, paid; same platform if other Lucky pieces ever move there. |
| **Supabase** | Postgres + extras; heavier. Team previously chose *not* to use it for Lucky — reconfirm before reversing. |
| **Self-host on a 2nd box** | Only if a second node is already planned (also satisfies half the ADR-0037 trigger). |

Confirm: version parity (match current `lucky-postgres` major), connection
limits vs Lucky's pool size, and whether pgvector/extensions are used.

## Migration steps (staging → prod, per env)

1. **Provision** managed instance; capture connection string as a secret (never
   commit — Lucky reads `DATABASE_URL` from env/`.env`).
2. **Schema + data**: quiesce writes (stop `lucky-backend`/`lucky-bot` for the
   env, keep Discord gateway drain in mind), then
   `pg_dump -Fc` from the container →
   `pg_restore` into the managed instance. Verify row counts per table.
   ```sh
   ssh homelab 'docker exec lucky-postgres pg_dump -Fc -U <user> <db>' > lucky_prod.dump
   pg_restore --no-owner -d "$MANAGED_URL" lucky_prod.dump
   ```
3. **Cutover**: point Lucky's `DATABASE_URL` at the managed instance; redeploy
   the env (`up -d --no-deps` to recreate with new env — a plain restart keeps
   stale env, per memory `feedback_docker_restart_vs_recreate_env`).
4. **Verify**: Lucky healthy (Grafana `Lucky bot up` / `backend up`), no DB
   errors in `lucky-*` logs, guild count stable, a write path works
   (e.g. a settings change persists).
5. **Decommission local DB** only after 48 h stable: stop + remove the
   `lucky-postgres` container from `Lucky/docker-compose.yml`; keep a final dump
   in Kopia backup. **Measure freed headroom** (`free -h` before/after) — this
   feeds the ADR-0037 gate.

## Rollback

Keep the local `lucky-postgres` container **stopped, not deleted**, for 48 h.
If the managed DB misbehaves: point `DATABASE_URL` back, `up -d --no-deps`,
restart the local container. Data written to managed in the interim must be
re-dumped back — minimize the window by cutting over during low activity.

## Success criteria (Phase 1 exit)

- Managed DB serving prod, 48 h clean.
- Host headroom freed measured and recorded (target ≥ 500 MB; if < 500 MB →
  escalate to hardware per ADR-0037 Phase 3).
- Growth-gate dashboard live (host mem util %, Lucky/Postgres container mem,
  guild trend) — see `config/grafana/provisioning/dashboards/lukbot/`.

## Safety notes

- Migrating a **production** database. Do staging first; take a fresh Kopia
  backup before prod cutover; cut over during low Discord activity; never delete
  the source until the target is proven for 48 h.
- Connection string is a secret — env/secret store only, never committed.
