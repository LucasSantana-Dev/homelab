# Backup Strategy

Homelab uses **kopia** with a **local filesystem repository** for automated encrypted snapshots.

## Overview

- **Backup engine**: kopia (https://kopia.io) — snapshot-based, deduplicated, encrypted
- **Repository**: Local filesystem at `/opt/kopia-repo` on the homelab host
- **Frequency**: Daily at configurable intervals (default 24 hours)
- **Retention**: 10 latest snapshots, 7 daily, 4 weekly, 3 monthly (auto-managed)
- **Compression**: zstd
- **Status**: Interim local-only; offsite B2 target deferred (see ADR-0016)

## Scope

The repository backs up three source trees:
- `/docker-volumes`: All Docker named volumes (e.g., PostgreSQL, Redis, app state)
- `~/homelab/appdata`: Application data (Pi-hole, Stremio, etc.)
- `~/homelab/config`: Service configurations (Caddy, Prometheus, Grafana, Pi-hole, Home Assistant, etc.)

**Excluded intentionally** (same-disk interim repo):
- `/home/` bulk media (~183 GB) — reserved for offsite target

See **Caveats** below.

## Architecture

### Container Setup

The kopia service runs in `compose/backup.yml`:
- **Image**: `kopia/kopia:0.21.1`
- **Port**: `127.0.0.1:51515` (HTTP, Tailscale-only reach)
- **Volumes**:
  - `kopia_config`, `kopia_cache`, `kopia_logs` (Docker named volumes for state)
  - `/opt/kopia-repo:/repo` (the actual backup destination, read-write)
  - `/var/lib/docker/volumes:/source/docker-volumes:ro` (backup source)
  - `/home/luk-server/homelab/appdata:/source/appdata:ro` (backup source)
  - `/home/luk-server/homelab/config:/source/config:ro` (service configurations, backed up since PR #247)

### Initialization

On first start, the container:
1. Connects to (or creates) the local repo at `/repo`
2. Sets a global policy: compression=zstd, daily snapshot interval, and retention rules
3. Takes an initial snapshot of both source trees
4. Starts the kopia server for status checks and restore operations

### Healthcheck

```
kopia repository status
```

Exits 0 if the repo is reachable; non-zero otherwise. Kopia container is considered healthy when this command succeeds.

## Daily Operation

### Check Backup Status

From the host, connect to the kopia server:
```bash
curl -s http://127.0.0.1:51515/api/v1/repository/status | jq .
```

Or via container logs:
```bash
docker logs kopia
```

Monitor for errors like "snapshot creation failed" or "repository disconnected".

### List Snapshots

```bash
docker exec kopia kopia snapshot list
```

Example output:
```
  2026-05-30 15:32:45 UTC k8s7a+2e4a...  /source/docker-volumes (12.3 GB)
  2026-05-29 15:32:41 UTC k8s7a+2e4b...  /source/docker-volumes (12.2 GB)
  2026-05-30 15:32:52 UTC k9f3b+5c1d...  /source/appdata (234 MB)
  2026-05-29 15:32:48 UTC k9f3b+5c1e...  /source/appdata (233 MB)
  2026-05-30 15:32:58 UTC k7d2c+9e5a...  /source/config (45 MB)
  2026-05-29 15:32:54 UTC k7d2c+9e5b...  /source/config (44 MB)
```

### Manual Snapshot (Force Backup Now)

```bash
docker exec kopia kopia snapshot create /source/docker-volumes /source/appdata /source/config
```

The server will also create snapshots automatically on its 24-hour schedule.

## Restore Procedure

See `docs/runbooks/kopia-restore.md` for detailed restore steps including verification.

Quick example (restore latest snapshot to staging):
```bash
docker exec kopia kopia restore latest \
  --target=/tmp/restore-staging
```

## Caveats

### Local Repository (Same Disk)

The repository lives on `/opt/kopia-repo`, which is **on the same physical disk** as the sources. This means:

- **Protects against**: Accidental data deletion, app errors, config corruption
- **Does NOT protect against**: Host disk failure, ransomware with root access, simultaneous disk + power loss
- **Recovery**: Restore to a USB drive or network mount, then assess damage

### Offsite Disaster Recovery (Deferred)

B2 integration is deferred. See **ADR-0016** for context:
- Timeline: Add once local snapshots are verified (Object Lock + freshness alerts)
- Cost: ~$6–10/month for ~100 GB
- Then: Daily incremental snapshots to B2 for true off-site redundancy

For now, **manual periodic B2 backup** is recommended if data loss from total host failure is unacceptable:
```bash
# Copy repo snapshot bundle to B2 manually (effort required):
# rclone sync /opt/kopia-repo b2:homelab-backup-b2/
```

### Repository Encryption Password

The repository is encrypted with `KOPIA_REPO_PASSWORD` (set in `.env`). **Losing this password makes snapshots unrecoverable.**

Treat the password file `/etc/homelab/.env` (on the host) the same as the SSH private key.

## Configuration

Repository policy is set once at startup and can be modified via:

```bash
docker exec kopia kopia policy set --global \
  --compression=zstd \
  --snapshot-interval=24h \
  --keep-latest=10 --keep-daily=7 --keep-weekly=4 --keep-monthly=3
```

Retention is **strict**: once a snapshot is pruned, it is gone.

## Troubleshooting

### Container won't start (repo password error)

Check that `KOPIA_REPO_PASSWORD` is set in `.env`:
```bash
grep KOPIA_REPO_PASSWORD /etc/homelab/.env
```

If missing, the container will fail to connect on restart.

### Snapshots not being created (stuck at initial snapshot)

Check logs:
```bash
docker logs kopia | tail -20
```

Common causes:
- Source paths `/source/docker-volumes`, `/source/appdata`, or `/source/config` not mounted
- Disk space at `/opt/kopia-repo` exhausted
- kopia server crashed and didn't restart (see container status)

### Restore fails with "snapshot not found"

Verify the snapshot ID:
```bash
docker exec kopia kopia snapshot list
```

Use the exact snapshot ID from the output, or use `latest` to restore the most recent.

## Cost & Space

Typical homelab (docker volumes ~5.4 GB + appdata ~7.3 GB + config ~45 MB):
- **Local repo size**: ~5–15 GB (depends on deduplication and retention count)
- **Offsite cost** (B2, future): ~$6–10/month for 100 GB
- **Network egress** (B2, future): Minimal after initial sync; incremental

Current: **$0** (local only).

## References

- ADR-0016: [Keep kopia server-mode; add backup verification](adr/0016-keep-kopia-server-mode-add-backup-verification.md)
- kopia docs: https://kopia.io/docs/
- kopia server: https://kopia.io/docs/server-mode/
