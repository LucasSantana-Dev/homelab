# Kopia Restore Runbook

This runbook covers how to restore files from kopia snapshots when needed.

## Prerequisites

- kopia container is running and healthy (`docker ps | grep kopia`)
- You have the repository encryption password (required to connect)
- You know which snapshot(s) contain the data you need to restore

## Snapshot Discovery

First, list all snapshots to find the one you want to restore:

```bash
docker exec kopia kopia snapshot list
```

Example output:
```
  2026-05-30 15:32:45 UTC k8s7a+2e4a...  /source/docker-volumes (12.3 GB)
  2026-05-29 15:32:41 UTC k8s7a+2e4b...  /source/docker-volumes (12.2 GB)
  2026-05-30 15:32:52 UTC k9f3b+5c1d...  /source/appdata (234 MB)
  2026-05-29 15:32:48 UTC k9f3b+5c1e...  /source/appdata (233 MB)
```

The format is: `TIMESTAMP SNAPSHOT_ID SOURCE_PATH (SIZE)`.

### Find by Source

- Docker volumes: Look for snapshots of `/source/docker-volumes`
- Homelab app data: Look for snapshots of `/source/appdata`

### Find by Timestamp

Pick the most recent snapshot before the data loss / corruption event.

## Restore Procedure

### 1. Connect to the Repository

The kopia server inside the container maintains an active connection to the repository. You can restore by executing kopia commands inside the container.

### 2. Restore to Staging Directory

Restore the entire snapshot to a staging area first (**never restore directly to live paths**):

```bash
docker exec kopia kopia restore <SNAPSHOT_ID> \
  --target=/tmp/restore-staging
```

Replace `<SNAPSHOT_ID>` with the actual ID from `snapshot list` output (e.g., `k8s7a+2e4a...`).

**Example**: Restore the latest docker-volumes snapshot:
```bash
docker exec kopia kopia snapshot list | grep "/source/docker-volumes" | head -1 | awk '{print $3}' > /tmp/snap_id.txt
docker exec kopia kopia restore "$(cat /tmp/snap_id.txt)" \
  --target=/tmp/restore-staging
```

### 3. Verify Contents

Browse the restored tree to confirm it contains what you expect:

```bash
ls -lah /tmp/restore-staging/source/docker-volumes/
# or for appdata:
ls -lah /tmp/restore-staging/source/appdata/
```

### 4. Validate Data Integrity (Optional)

Compare a sample file from the restore to the original (if the original is still intact):

```bash
# Example: check a specific Docker volume
diff -u /var/lib/docker/volumes/postgres_data/_data/some-file \
         /tmp/restore-staging/source/docker-volumes/postgres_data/_data/some-file
```

If files match, the restore is valid.

### 5. Copy to Live Path

Once verified, move the restored files to their live location:

```bash
# Example: restore a specific Docker volume
cp -r /tmp/restore-staging/source/docker-volumes/postgres_data/_data/* \
      /var/lib/docker/volumes/postgres_data/_data/

# Or for appdata:
cp -r /tmp/restore-staging/source/appdata/* \
      /home/luk-server/homelab/appdata/
```

### 6. Verify Service Health

After restoring critical data (e.g., databases), verify the affected services are healthy:

```bash
# Restart the service that uses the restored data:
docker compose -f compose/db.yml up -d

# Check logs for errors:
docker logs <service-name>
```

### 7. Cleanup

Remove the staging restore directory:

```bash
rm -rf /tmp/restore-staging
```

## Restore Latest Snapshot (Quick Path)

If you just want to restore the most recent snapshot of a source:

```bash
docker exec kopia kopia restore latest --target=/tmp/restore-staging
```

This restores whichever snapshot was created most recently (timestamp-wise).

## Restore a Specific File

To restore just one file (rather than the entire snapshot):

```bash
docker exec kopia kopia restore <SNAPSHOT_ID> \
  --include="/source/appdata/caddy/Caddyfile" \
  --target=/tmp/restore-staging
```

The `--include` filter uses glob patterns. The restored file path will match the original hierarchy within the snapshot (e.g., `/tmp/restore-staging/source/appdata/caddy/Caddyfile`).

## Restore with Verification

For critical data, do a full restore → diff → move cycle:

```bash
# 1. List snapshots and pick one
docker exec kopia kopia snapshot list

# 2. Restore to staging
docker exec kopia kopia restore <SNAPSHOT_ID> --target=/tmp/restore-test

# 3. Quick integrity check (sample files)
find /tmp/restore-test -type f | head -5 | while read f; do
  cmp "$f" "${f/restore-test/docker\/volumes}" && echo "✓ $f" || echo "✗ $f"
done

# 4. If all match, move to live location
# (see "Copy to Live Path" above)

# 5. Cleanup
rm -rf /tmp/restore-test
```

## Troubleshooting

### "Snapshot not found" error

Double-check the snapshot ID:
```bash
docker exec kopia kopia snapshot list | grep "<search-term>"
```

Ensure you're using the full ID from the `SNAPSHOT_ID` column, not just the first few characters.

### Restore appears to hang

Check kopia container logs:
```bash
docker logs kopia --tail 20
```

If the container is running but restore is slow, it may just be reading from disk. Large snapshots (>10 GB) can take several minutes.

### "Permission denied" during restore

Ensure the staging directory is writable:
```bash
mkdir -p /tmp/restore-staging
chmod 777 /tmp/restore-staging
```

Also check the user running the docker command has permission to read the restored files.

### Restored files are owned by root

kopia preserves original file ownership. If the snapshot was taken as root, restored files will be owned by root. Adjust ownership if needed:

```bash
chown -R luk-server:luk-server /tmp/restore-staging/
```

## When Snapshots Expire

Kopia's retention policy automatically prunes old snapshots:
- Latest 10 snapshots always kept
- 7 daily, 4 weekly, 3 monthly retained
- Everything else deleted

**Plan your restore before expiry.** If you suspect data loss, restore immediately. The oldest daily snapshot is retained for 7 days; older daily snapshots are deleted unless they fall into the weekly/monthly windows.

Check your backup policy:
```bash
docker exec kopia kopia policy show --global
```

## References

- Homelab backup strategy: [docs/backup.md](../backup.md)
- kopia restore command: https://kopia.io/docs/reference/command-line/common/restore/
- ADR-0016: [Keep kopia server-mode; add backup verification](../adr/0016-keep-kopia-server-mode-add-backup-verification.md)
