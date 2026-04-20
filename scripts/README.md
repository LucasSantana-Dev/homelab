# Scripts Directory

This directory contains utility scripts organized by function for homelab management.

## Directory Structure

```
scripts/
├── homelab              # Main CLI wrapper (entry point)
├── containers           # Container management wrapper
├── homelab-tools        # Python tools entry point
├── deployment/          # Service lifecycle management
│   ├── startup-services.sh
│   ├── shutdown-services.sh
│   ├── install-systemd-services.sh
│   ├── setup-serena-mcp.sh
│   └── setup-forge-space-mcp.sh
├── maintenance/         # Backup and update operations
│   ├── automated-backup.sh
│   ├── stabilize-host-prep.sh
│   ├── swap-recover.sh
│   ├── convert-to-server-mode.sh
│   ├── post-reboot-validate.sh
│   ├── update-containers.sh
│   └── update-containers.py
├── monitoring/          # Status and health monitoring
│   ├── container-status.py
│   └── status-services.sh
├── security/            # Security scanning and public release gates
│   ├── security-scan.sh
│   ├── secret-gate.sh
│   ├── public-safety-gate.sh
│   ├── pre-release-checkpoint.sh
│   └── rewrite-history.sh
├── systemd/             # Systemd service unit files
│   ├── homelab-docker.service
│   ├── homelab-update.service
│   ├── homelab-update.timer
│   ├── lukbot.service
│   └── satisfactory-server.service
└── hacs/                # Home Assistant specific scripts
    ├── install_hacs_addons.py
    ├── interactive_hacs_installer.py
    ├── requirements-hacs-installer.txt
    └── install_hacs_addons_guide.md
```

## Entry Point Scripts

### `homelab`

Main CLI wrapper for the Python homelab_manager package.

```bash
./scripts/homelab status
./scripts/homelab deploy
./scripts/homelab health
```

### `containers`

Container management wrapper for quick container operations.

```bash
./scripts/containers status    # Show container status
./scripts/containers update    # Update containers
./scripts/containers check     # Check for updates
```

## Deployment Scripts

### `deployment/startup-services.sh`

Start all homelab services with proper ordering.

### `deployment/shutdown-services.sh`

Gracefully stop all homelab services.

### `deployment/install-systemd-services.sh`

Install systemd service files for auto-start on boot.

### `deployment/setup-serena-mcp.sh`

Build and register a Serena MCP runtime image with node and terraform dependencies.

### `deployment/setup-forge-space-mcp.sh`

Register Forge Space MCP gateway in Codex using Dockerized `python -m mcpgateway.wrapper`.

## Maintenance Scripts

### `maintenance/automated-backup.sh`

Create automated backups of homelab data.

```bash
./scripts/maintenance/automated-backup.sh
./scripts/maintenance/automated-backup.sh --verify backup.tar.gz
```

### `maintenance/update-containers.sh`

Safe container update with health checks and rollback.

```bash
./scripts/maintenance/update-containers.sh
./scripts/maintenance/update-containers.sh --dry-run
```

## Monitoring Scripts

### `monitoring/status-services.sh`

Show systemd service status for homelab services.

### `monitoring/container-status.py`

Python script for detailed container status and health checks.

### `maintenance/stabilize-host-prep.sh`

Creates a recovery point before host package cleanup (app backup, baseline metrics, package/service snapshot, optional privileged `/etc` tarball). By default it runs backup through `sudo` to include root-owned container volumes.

### `maintenance/swap-recover.sh`

Performs controlled swap reset (`swapoff -a && swapon -a`) and logs before/after pressure metrics.

### `maintenance/convert-to-server-mode.sh`

Converts desktop host to server mode in place. Default is preview; use `--apply` to execute package purge and service target changes.

### `maintenance/post-reboot-validate.sh`

Validates server-mode reboot outcome, core services, timers, and homelab health.

## Security Scripts

### `security/security-scan.sh`

Run security scans on containers and images using Trivy.

### `security/secret-gate.sh`

Run gitleaks against tracked content (and optionally history) using `.gitleaks.toml`.

### `security/public-safety-gate.sh`

Fail when private infrastructure identifiers appear in tracked public files.

## Systemd Integration

Install and enable automatic startup:

```bash
./scripts/deployment/install-systemd-services.sh
```

Check service status:

```bash
./scripts/monitoring/status-services.sh
```

## Best Practices

1. **Always use scripts** instead of direct docker commands for automation
2. **Prefer the Python CLI** (`./scripts/homelab`) for interactive use
3. **Use Make targets** when available: `make deploy`, `make backup`, etc.
4. **Check logs** after operations: `make logs` or `./scripts/homelab logs`
