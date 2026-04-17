# Backup Strategy

Homelab uses **restic** + **Backblaze B2** for automated encrypted backups.

## Architecture

- **Backup engine**: restic (https://restic.io) — incremental, deduplicated, encrypted
- **Storage**: Backblaze B2 (low-cost cloud storage, ~$0.006/GB/month)
- **Frequency**: Daily at 3:00 AM UTC (configurable via systemd timer)
- **Retention**: 7 daily, 4 weekly, 12 monthly snapshots (auto-pruned)

## Covered Data

- PostgreSQL: All databases (postgres, craftvaria, lucky)
- Redis: `dump.rdb` via BGSAVE
- Craftvaria: World files, player data
- Caddy: Reverse proxy config, certificates
- Pi-hole: DNS/DHCP config, blocklists
- Docker Compose: All YAML files, `docker-compose.yml`
- Environment: `.env` files (if present)

## Setup (One-time)

### 1. Install Restic
```bash
brew install restic
ssh root@homelab "apt install restic"  # or your package manager
```

### 2. Create Backblaze B2 Account
1. Sign up at https://www.backblaze.com/b2/cloud-storage.html
2. Create a **private** bucket (e.g., `homelab-backups`)
3. Create an application key with permissions:
   - `listBuckets`
   - `listFiles`
   - `readFiles`
   - `writeFiles`
   - `deleteFiles`
4. Note the **application key ID** and **application key**

### 3. Initialize Restic Repository
On your local machine:
```bash
export RESTIC_REPOSITORY="b2:homelab-backups:/restic-repo"
export RESTIC_PASSWORD_FILE="$HOME/.restic-password"

# Create strong password file (ONE TIME)
head -c 32 /dev/urandom | base64 > ~/.restic-password
chmod 600 ~/.restic-password

# Initialize repo
restic init
```

You'll be prompted for B2 credentials (application key ID and key).

### 4. Configure Server Environment
On the backup server (server-do-luk):
```bash
# Create password file
ssh root@homelab "echo 'YOUR_STRONG_PASSWORD' > /root/.restic-password && chmod 600 /root/.restic-password"

# Create environment file for systemd
ssh root@homelab "cat > /etc/homelab/.env << 'INNER_EOF'
RESTIC_REPOSITORY=b2:homelab-backups:/restic-repo
RESTIC_PASSWORD_FILE=/root/.restic-password
B2_ACCOUNT_ID=your_app_key_id
B2_ACCOUNT_KEY=your_app_key
INNER_EOF"

# Install scripts
ssh root@homelab "mkdir -p /opt/homelab/scripts/backup"
scp scripts/backup/*.sh root@homelab:/opt/homelab/scripts/backup/
chmod +x /opt/homelab/scripts/backup/*.sh

# Install systemd units
scp systemd/*.service systemd/*.timer root@homelab:/etc/systemd/system/
ssh root@homelab "systemctl daemon-reload && systemctl enable restic-daily.timer"
```

### 5. Test Backup (Dry Run)
```bash
ssh root@homelab "bash /opt/homelab/scripts/backup/restic-backup.sh"
```

Monitor logs:
```bash
ssh root@homelab "journalctl -u restic-daily.service -f"
```

### 6. Test Restore
Create a test backup of a small directory:
```bash
export RESTIC_REPOSITORY="b2:homelab-backups:/test-restore"
export RESTIC_PASSWORD_FILE="$HOME/.restic-password"

mkdir -p /tmp/restic-test
echo "test data" > /tmp/restic-test/file.txt

restic init
restic backup /tmp/restic-test
SNAP=$(restic snapshots --compact | tail -1 | awk '{print $1}')

# Restore to /tmp
mkdir -p /tmp/homelab-restore
restic restore "$SNAP" --target /tmp/homelab-restore

# Verify
diff -r /tmp/restic-test /tmp/homelab-restore/tmp/restic-test
echo "Restore test passed!"

# Cleanup
restic forget --prune --keep-daily 0
```

## Daily Operation

### Check Backup Status
```bash
ssh root@homelab "journalctl -u restic-daily.service -n 50"
```

### List Snapshots
```bash
export RESTIC_REPOSITORY="b2:homelab-backups:/restic-repo"
export RESTIC_PASSWORD_FILE="$HOME/.restic-password"
restic snapshots
```

### Restore a File
```bash
restic restore latest --include="/postgres.sql" --target=/tmp/restore
```

### Manual Backup
```bash
ssh root@homelab "bash /opt/homelab/scripts/backup/restic-backup.sh"
```

## Security Considerations

1. **B2 credentials**: Stored in `/etc/homelab/.env` on server only (root-readable)
2. **Restic password**: `~/.restic-password` on server (600 permissions)
3. **Encryption**: Restic encrypts all data with password before upload to B2
4. **Isolation**: B2 application key limited to this bucket only
5. **Network**: B2 API traffic over HTTPS

## Cost Estimation

For typical homelab (50-100 GB):
- **Storage**: 100 GB @ $0.006/GB/month = $0.60/month
- **Egress**: 1 GB restore/month @ $0.01/GB = $0.01/month
- **Total**: ~$0.65/month

Deduplication and incremental backups keep size well below full disk capacity.

## Troubleshooting

### "Bucket not found" error
- Verify B2 bucket name in RESTIC_REPOSITORY
- Confirm B2 application key is active

### "Authentication failed"
- Check B2_ACCOUNT_ID and B2_ACCOUNT_KEY in environment
- Regenerate application key if expired

### Backup slow / timeout
- Increase B2 connections in script: `restic backup ... -o b2.connections=20`
- Check network connectivity to B2
- Monitor server resources: `free -h && df -h`

### Restore failing
- Verify Restic version matches (use `restic version`)
- Check available disk space at restore target
- Run restore with verbose logging: `restic restore -v ...`

## References

- Restic docs: https://restic.readthedocs.io/
- B2 setup: https://www.backblaze.com/b2/docs/
- Restic B2 backend: https://restic.readthedocs.io/en/latest/030_preparing_a_new_repo.html#backblaze-b2
