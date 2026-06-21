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

### Offsite Disaster Recovery — rsync mirror to a second host/disk (#266)

The encrypted kopia repo is mirrored offsite by `scripts/maintenance/kopia-offsite-sync.sh`
(systemd `kopia-offsite-sync.timer`, daily 04:30). Because the repo is encrypted
at rest, the offsite copy needs no extra encryption — but recovery requires **both**
the mirror **and** `KOPIA_REPO_PASSWORD` (kept off-host in SOPS, #272).

**Enable:**
1. Set the target in `.env` (a remote host or a mounted disk):

   ```bash
   KOPIA_OFFSITE_TARGET=luk@pc-do-luk:/srv/kopia-offsite   # or /mnt/usb-backup/kopia-offsite
   ```

   For a remote host, ensure root on the homelab can ssh to it (`ssh-copy-id` a key).
2. Install + start the timer:

   ```bash
   sudo cp scripts/systemd/kopia-offsite-sync.{service,timer} /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now kopia-offsite-sync.timer
   sudo systemctl start kopia-offsite-sync.service   # first run now
   ```

   The script no-ops cleanly while no target is set, so installing the timer
   before choosing a target is safe.

**Alternative — cloud via rclone (e.g. Google Drive):** set an rclone remote
instead of (or in addition to) the rsync target. The encrypted repo (~11 GB) fits
Google Drive's free 15 GB.

1. Install rclone on the host: `sudo apt-get install -y rclone` (or `curl https://rclone.org/install.sh | sudo bash`).
2. Configure the remote **once** (interactive OAuth — needs a browser). Run it as
   the `luk-server` user (no sudo) so the config lands at
   `~/.config/rclone/rclone.conf` — the systemd service points `RCLONE_CONFIG`
   there, so the root-run sync reuses it. Run `rclone config`, choose `drive`,
   accept defaults, and at the "auto config?" prompt answer **No**, then run
   `rclone authorize "drive"` on a laptop and paste the token back. Name it
   `gdrive`. The config file holds the Drive OAuth token — keep it 0600.
3. Point the sync at it:

   ```bash
   KOPIA_OFFSITE_RCLONE_REMOTE=gdrive:homelab-kopia
   ```

   (rclone takes precedence over `KOPIA_OFFSITE_TARGET` if both are set.) Then
   install/enable the timer as above. `rclone sync` mirrors (propagates deletes),
   guarded by the same repo-marker source check.

**Restore from the offsite mirror (host lost):**
1. Bring the mirror back to a path, e.g. `/opt/kopia-repo` on the new host.
2. Recover `KOPIA_REPO_PASSWORD` from SOPS (`make sops-decrypt`, see docs/secrets.md).
3. `kopia repository connect filesystem --path=/opt/kopia-repo` (uses `KOPIA_PASSWORD`),
   then `kopia snapshot restore <id> <dest>`.

**Safety:** the sync refuses to run if `/opt/kopia-repo` lacks its repository marker,
so a missing/empty source can't `--delete` a good offsite copy.

#### Cloud object store (B2/S3) — still deferred (ADR-0016)

The `KOPIA_S3_*` vars scaffold a Backblaze B2 / S3 target (~$6–10/mo for 100 GB)
for a future second offsite tier. Not wired yet; the rsync mirror above already
covers the immediate same-disk-failure gap at $0. To add B2 later as a second tier:

```bash
# The repo is encrypted, so a plain sync of the repo files is safe:
rclone sync /opt/kopia-repo b2:homelab-backup-b2/
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

## Monitoring & Alerts

Two Prometheus alerts watch the backup (defined in `config/prometheus/alerts.yml`):

| Alert | Fires when | Severity | SLO / threshold |
|-------|-----------|----------|-----------------|
| `KopiaSnapshotStale` | `time() - kopia_last_snapshot_timestamp_seconds > 172800` for 10m | warning | **A successful snapshot every ≤48h.** Kopia can be "healthy" (container up) yet not actually snapshotting — this catches that. |
| `KopiaSnapshotListFailed` | `kopia_snapshot_list_ok == 0` for 5m | critical | Snapshot list query failed — container down, repo unreachable, or auth failed. |

**Runbook — `KopiaSnapshotStale`:**
1. `docker exec kopia kopia snapshot list --max-results 5` — is the newest snapshot really >48h old?
2. If stale, force one: `docker exec kopia kopia snapshot create /source/docker-volumes /source/appdata /source/config` (see [Daily Operation](#daily-operation)).
3. Check the scheduler: the server runs `--snapshot-interval=24h`; confirm the policy with `docker exec kopia kopia policy show --global`.
4. Check disk space (`df -h`) — a full disk silently stops snapshots.

**Runbook — `KopiaSnapshotListFailed`:**
1. `docker ps | grep kopia` and `docker logs kopia --tail 50`.
2. Verify the repo is connected: `docker exec kopia kopia repository status`.
3. If auth failed, confirm `KOPIA_PASSWORD` / `KOPIA_SERVER_PASSWORD` in `.env` are intact (see Caveats — losing `KOPIA_PASSWORD` makes the repo unrecoverable).

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
