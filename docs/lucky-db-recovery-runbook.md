# Lucky DB Recovery Runbook

This runbook covers detection, backup, and recovery of the Lucky PostgreSQL
schema-loss incident caused by `postgres:18-alpine` data-path behavior.

## Incident Pattern

- Symptom: `lucky-backend` crash loop with `ERR_DB_SCHEMA_MISSING`.
- Root cause: PostgreSQL container writes data outside the mounted volume when
  `PGDATA` is not pinned.
- Prevention: set `PGDATA=/var/lib/postgresql/data` in Lucky `docker-compose.yml`.

## Preconditions

- Lucky repository path: `/home/luk-server/Lucky`
- Homelab repository path: `/home/luk-server/homelab`
- Recovery script: `scripts/maintenance/recover-lucky-db.sh`

## 1) Backup-Only Mode (safe default)

Run from homelab repo:

```bash
./scripts/maintenance/recover-lucky-db.sh --backup-only
```

Expected result:

- backup archive created under `backups/lucky/`
- no container recreation
- no schema mutation

## 2) Full Recovery Mode

Use only when backend is failing with missing schema.

```bash
./scripts/maintenance/recover-lucky-db.sh --full-recovery
```

This mode performs:

1. backup snapshot
2. compose validation with pinned PGDATA
3. schema recovery flow
4. migration baseline reconciliation
5. service health verification

## 3) Manual Verification

### Compose config includes PGDATA

```bash
cd /home/luk-server/Lucky
POSTGRES_PASSWORD=dummy docker compose config | rg -n "postgres:|PGDATA"
```

Expected line includes:

```text
PGDATA: /var/lib/postgresql/data
```

### Lucky services healthy

```bash
cd /home/luk-server/Lucky
docker compose ps
```

`lucky-postgres` and `lucky-backend` should be `Up` and healthy.

## 4) Daily Backup Check

Daily backup cron is expected at 03:00. Confirm files exist:

```bash
ls -lah /home/luk-server/homelab/backups/lucky/
```

If no recent backup exists, run `--backup-only` immediately and inspect cron
configuration.

## Out of Scope

- Application feature debugging unrelated to DB schema
- Secret rotation workflow
- k3s migration operations
