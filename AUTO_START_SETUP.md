# Auto-Start Services Setup - Quick Reference

This document provides a quick reference for the auto-start services configuration.

## What Was Configured

1. **Systemd Service Files** - Created in `scripts/systemd-services/`:
   - `homelab-docker.service` - Main homelab stack
   - `satisfactory-server.service` - Game server + Cloudflared tunnel
   - `lukbot.service` - Discord bot

2. **Helper Scripts** - Created in `scripts/`:
   - `install-systemd-services.sh` - Install and enable all services
   - `startup-services.sh` - Manually start all services
   - `shutdown-services.sh` - Gracefully shutdown all services
   - `status-services.sh` - Check status of all services

3. **Documentation**:
   - `docs/bios-power-on-setup.md` - BIOS configuration guide

## Next Steps

### 1. Install Systemd Services

Run the installation script with sudo:

```bash
cd /home/luk-server/homelab
sudo ./scripts/install-systemd-services.sh
```

This will:
- Copy service files to `/etc/systemd/system/`
- Reload systemd daemon
- Enable all services for auto-start

### 2. Configure BIOS (Manual)

Access your BIOS/UEFI during boot and enable "Power On After AC Loss":

1. Boot into BIOS (typically DEL or F2 for Intel N100)
2. Navigate to Power Management settings
3. Set "Restore on AC/Power Loss" to **Power On**
4. Save and exit

See `docs/bios-power-on-setup.md` for detailed instructions.

### 3. Verify Configuration

```bash
# Check service status
./scripts/status-services.sh

# Verify services are enabled
systemctl is-enabled homelab-docker satisfactory-server lukbot

# Test manual start
./scripts/startup-services.sh
```

### 4. Test Auto-Start (Optional)

To test that services start automatically on boot:

```bash
# Reboot the server
sudo reboot

# After reboot, check services
./scripts/status-services.sh
```

## Service Management

### Start Services Manually
```bash
./scripts/startup-services.sh
```

### Stop Services Gracefully
```bash
./scripts/shutdown-services.sh
```

### Check Service Status
```bash
./scripts/status-services.sh
```

### View Service Logs
```bash
# Homelab services
sudo journalctl -u homelab-docker -n 50 -f

# Satisfactory server
sudo journalctl -u satisfactory-server -n 50 -f

# LukBot
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
8. **LukBot** - Starts 5s after homelab

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
