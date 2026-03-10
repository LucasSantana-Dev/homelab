# Auto-Start Services Setup - Quick Reference

This document provides a quick reference for the auto-start services configuration.

## What Was Configured

1. **Systemd Service Files** - Managed in `scripts/systemd/`:
   - `homelab-docker.service` - Main homelab stack
   - `satisfactory-server.service` - Game server + Cloudflared tunnel
   - `lukbot.service` - Discord bot

2. **Helper Scripts**:
   - `scripts/deployment/install-systemd-services.sh` - Install and enable all services
   - `scripts/deployment/startup-services.sh` - Manually start all services
   - `scripts/deployment/shutdown-services.sh` - Gracefully shutdown all services
   - `scripts/monitoring/status-services.sh` - Check status of all services
   - `scripts/maintenance/power-restore-check.sh` - Validate post-boot readiness

3. **Documentation**:
   - `docs/bios-power-on-setup.md` - BIOS configuration guide

## Next Steps

### 1. Install Systemd Services

Run the installation script with sudo:

```bash
cd /home/luk-server/homelab
sudo ./scripts/deployment/install-systemd-services.sh
```

This will:

- Copy service files to `/etc/systemd/system/`
- Reload systemd daemon
- Enable all services for auto-start

### 2. Configure BIOS (Manual)

Access your BIOS/UEFI during boot and enable "Power On After AC Loss":

1. Boot into BIOS (typically DEL or F2)
2. Navigate to Power Management settings
3. Set "Restore on AC/Power Loss" to **Power On**
4. Save and exit

See `docs/bios-power-on-setup.md` for detailed instructions.

### 3. Verify Configuration

```bash
# Check service status
./scripts/monitoring/status-services.sh

# Verify services are enabled
systemctl is-enabled homelab-docker satisfactory-server lukbot homelab-watchdog.timer homelab-update.timer

# Test manual start
./scripts/deployment/startup-services.sh

# Validate power-restore readiness
make power-restore-check
```

### 4. AC-Loss Drill (Mandatory)

To confirm true auto-recovery from power outages:

```bash
# 1) Ensure system is healthy
make watchdog-status

# 2) Graceful shutdown
sudo poweroff

# 3) Remove AC power for at least 15 seconds
# 4) Restore AC power

# 5) After host comes back, validate readiness
make power-restore-check
make watchdog-status
```

**Pass criteria**

- Host powers on automatically after AC returns (no button press).
- SSH is reachable.
- `docker.service`, `tailscaled.service`, `homelab-docker.service` are enabled and active.
- `homelab-update.timer` and `homelab-watchdog.timer` are enabled and active.

**Fail criteria**

- Host remains off after AC restore.
- Boot occurs but required services/timers are inactive or disabled.
- Manual power button press is required.

## Service Management

### Start Services Manually

```bash
./scripts/deployment/startup-services.sh
```

### Stop Services Gracefully

```bash
./scripts/deployment/shutdown-services.sh
```

### Check Service Status

```bash
./scripts/monitoring/status-services.sh
```

### View Service Logs

```bash
# Homelab services
sudo journalctl -u homelab-docker -n 50 -f

# Satisfactory server
sudo journalctl -u satisfactory-server -n 50 -f

# Lucky
sudo journalctl -u lukbot -n 50 -f
```

### Individual Service Control

```bash
# Start/stop individual services
sudo systemctl start homelab-docker
sudo systemctl stop homelab-docker
sudo systemctl restart homelab-docker

# Check status
sudo systemctl status homelab-docker
```

## Boot Sequence

1. **BIOS** - Auto power-on (if configured)
2. **Ubuntu Boot** - System initialization
3. **Docker Service** - Docker daemon starts
4. **Tailscale Daemon** - Tailscale network starts
5. **Network Online** - Network connectivity established
6. **Homelab Services** - Starts after 10s delay
7. **Satisfactory Server** - Starts 5s after homelab
8. **Lucky** - Starts 5s after homelab

## Troubleshooting

### Services Don't Start on Boot

1. **Check if services are enabled:**

   ```bash
   systemctl is-enabled homelab-docker satisfactory-server lukbot
   ```

2. **Check service logs:**

   ```bash
   sudo journalctl -u homelab-docker -n 100
   ```

3. **Verify Docker is running:**

   ```bash
   sudo systemctl status docker
   ```

4. **Check Tailscale connectivity:**

   ```bash
   tailscale status
   ```

### Service Fails to Start

1. **Check Docker Compose files:**

   ```bash
   cd /home/luk-server/homelab
   docker compose config
   ```

2. **Check for port conflicts:**

   ```bash
   sudo netstat -tulpn | grep LISTEN
   ```

3. **Verify environment variables:**

   ```bash
   cd /home/luk-server/homelab
   cat .env | grep -v "^#" | grep -v "^$"
   ```

## Related Documentation

- **BIOS Setup**: `docs/bios-power-on-setup.md`
- **Service Management**: `README.md#auto-start-services`
- **Changelog**: `CHANGELOG.md`
