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
│   └── install-systemd-services.sh
├── maintenance/         # Backup and update operations
│   ├── automated-backup.sh
│   ├── update-containers.sh
│   └── update-containers.py
├── monitoring/          # Status and health monitoring
│   ├── container-status.py
│   └── status-services.sh
├── security/            # Security scanning
│   └── security-scan.sh
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

## Security Scripts

### `security/security-scan.sh`
Run security scans on containers and images using Trivy.

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
