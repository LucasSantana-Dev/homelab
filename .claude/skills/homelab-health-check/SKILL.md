# Homelab Health Check

Comprehensive health assessment for the homelab infrastructure.

## When to Use
- Before any infrastructure changes (migration, terraform apply, service restart)
- After incidents or swap pressure events
- Routine health verification
- Assessing readiness for migration gates

## Quick Health Check
```bash
# Container status
docker ps --format 'table {{.Names}}\t{{.Status}}' | head -40

# Memory and swap
free -h
swapon --show

# Burn-in status (use shorter windows for recent-only assessment)
bash scripts/maintenance/burnin-status.sh --since '12 hours ago'
bash scripts/maintenance/burnin-status.sh --since '24 hours ago'

# Watchdog status
systemctl status homelab-watchdog.timer --no-pager
```

## Interpreting Burn-in Results
- **Overall PASS**: No failures in the time window
- **Overall FAIL**: Check `Watchdog service failures` count
  - Transient timeouts during swap spikes are common; check if resolved
  - Use a shorter window (12h) to see if recent health is clean
- **Key counters**: degraded detections, recovery actions, cAdvisor OOM events
- **Zero degraded + zero recovery = healthy** even if FAIL due to old transient timeout

## Swap Pressure Assessment
- **< 1.5 GiB used**: healthy
- **1.5 - 2.0 GiB**: elevated but acceptable
- **2.0 - 3.0 GiB**: structural pressure (Minecraft 3.1GB + k3s + services)
- **> 3.0 GiB**: consider reducing Minecraft heap or stopping non-essential services

## Top Memory Consumers (typical)
- java (Minecraft): ~3.1 GB RSS (-Xmx4G)
- k3s-server: ~500 MB
- opencode: ~350 MB (when active)
- homeassistant: ~270 MB
- authentik workers: ~200 MB each
- netdata: ~150 MB

## Scripts
- `scripts/maintenance/burnin-status.sh` — burn-in health summary
- `scripts/maintenance/capture-pressure-snapshot.sh` — labeled pressure snapshot
- `scripts/maintenance/pressure-watch.sh` — long-running pressure monitor
- `scripts/maintenance/swap-recover.sh` — swap reset (requires sudo)
- `scripts/maintenance/homelab-watchdog.sh` — per-minute health check (systemd)
