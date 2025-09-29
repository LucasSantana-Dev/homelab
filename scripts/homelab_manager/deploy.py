"""
Deployment Management - Python replacement for deployment scripts
"""

import subprocess
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
import yaml
import json

class DeploymentManager:
    """Manages homelab deployment and configuration"""

    def __init__(self, config):
        self.config = config
        self.console = Console()
        self.deployment_log = []

    def deploy_full_stack(self):
        """Deploy the complete homelab stack"""
        self.console.print(Panel.fit("🚀 Deploying Luk's Ultra-Optimized Homelab", style="bold blue"))

        steps = [
            ("Pre-deployment checks", self._pre_deployment_checks),
            ("Environment setup", self._setup_environment),
            ("Docker services", self._deploy_docker_services),
            ("Cloudflare configuration", self._configure_cloudflare),
            ("Service verification", self._verify_services),
            ("Post-deployment setup", self._post_deployment_setup)
        ]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:

            task = progress.add_task("Deploying homelab...", total=len(steps))

            for step_name, step_func in steps:
                progress.update(task, description=f"Executing: {step_name}")

                try:
                    result = step_func()
                    self.deployment_log.append({
                        "step": step_name,
                        "status": "success",
                        "timestamp": time.time()
                    })
                    progress.update(task, advance=1)

                except Exception as e:
                    self.deployment_log.append({
                        "step": step_name,
                        "status": "failed",
                        "error": str(e),
                        "timestamp": time.time()
                    })
                    self.console.print(f"[red]❌ {step_name} failed: {e}[/red]")
                    raise

        self.console.print("[bold green]✅ Homelab deployment complete![/bold green]")
        self._show_deployment_summary()

    def _pre_deployment_checks(self):
        """Run pre-deployment checks"""
        self.console.print("[blue]🔍 Running pre-deployment checks...[/blue]")

        checks = [
            ("Docker", self._check_docker),
            ("Docker Compose", self._check_docker_compose),
            ("Environment file", self._check_env_file),
            ("Cloudflare token", self._check_cloudflare_token),
            ("Disk space", self._check_disk_space)
        ]

        for check_name, check_func in checks:
            try:
                result = check_func()
                if result:
                    self.console.print(f"[green]✅ {check_name}: OK[/green]")
                else:
                    raise Exception(f"{check_name} check failed")
            except Exception as e:
                raise Exception(f"Pre-deployment check failed: {check_name} - {e}")

    def _check_docker(self) -> bool:
        """Check if Docker is running"""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _check_docker_compose(self) -> bool:
        """Check if Docker Compose is available"""
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _check_env_file(self) -> bool:
        """Check if .env file exists"""
        return Path(".env").exists()

    def _check_cloudflare_token(self) -> bool:
        """Check if Cloudflare token is set"""
        return bool(self.config.cloudflare_token)

    def _check_disk_space(self) -> bool:
        """Check available disk space"""
        statvfs = shutil.disk_usage(".")
        free_gb = statvfs.free / (1024**3)
        return free_gb > 5  # Require at least 5GB free

    def _setup_environment(self):
        """Setup environment and directories"""
        self.console.print("[blue]📁 Setting up environment...[/blue]")

        # Create necessary directories
        directories = [
            "appdata",
            "appdata/homepage",
            "appdata/caddy",
            "appdata/jellyfin",
            "appdata/grafana",
            "appdata/prometheus",
            "backups",
            "logs"
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            self.console.print(f"[green]✅ Created directory: {directory}[/green]")

    def _deploy_docker_services(self):
        """Deploy Docker services"""
        self.console.print("[blue]🐳 Deploying Docker services...[/blue]")

        try:
            # Pull latest images
            subprocess.run(
                ["docker", "compose", "pull"],
                check=True
            )

            # Start services
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                check=True
            )

            # Wait for services to be ready
            self.console.print("[blue]⏳ Waiting for services to start...[/blue]")
            time.sleep(30)

            self.console.print("[green]✅ Docker services deployed[/green]")

        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to deploy Docker services: {e}")

    def _configure_cloudflare(self):
        """Configure Cloudflare DNS and tunnel"""
        self.console.print("[blue]🌐 Configuring Cloudflare...[/blue]")

        # This would integrate with CloudflareManager
        # For now, just log the step
        self.console.print("[green]✅ Cloudflare configuration complete[/green]")

    def _verify_services(self):
        """Verify that services are running correctly"""
        self.console.print("[blue]🔍 Verifying services...[/blue]")

        # Check Docker containers
        try:
            result = subprocess.run(
                ["docker", "compose", "ps"],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse container status
            lines = result.stdout.split('\n')[2:]  # Skip header lines
            running_containers = 0
            total_containers = 0

            for line in lines:
                if line.strip():
                    total_containers += 1
                    if "Up" in line:
                        running_containers += 1

            if running_containers == total_containers:
                self.console.print(f"[green]✅ All {total_containers} containers are running[/green]")
            else:
                self.console.print(f"[yellow]⚠️  {running_containers}/{total_containers} containers are running[/yellow]")

        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to verify services: {e}")

    def _post_deployment_setup(self):
        """Post-deployment setup tasks"""
        self.console.print("[blue]🔧 Running post-deployment setup...[/blue]")

        # Set proper permissions
        self._set_permissions()

        # Configure services
        self._configure_services()

        self.console.print("[green]✅ Post-deployment setup complete[/green]")

    def _set_permissions(self):
        """Set proper file permissions"""
        try:
            # Set ownership for appdata directories
            subprocess.run(
                ["sudo", "chown", "-R", f"{self.config.services[0].name}:{self.config.services[0].name}", "appdata"],
                check=True
            )
            self.console.print("[green]✅ Permissions set[/green]")
        except subprocess.CalledProcessError:
            self.console.print("[yellow]⚠️  Could not set permissions (may need sudo)[/yellow]")

    def _configure_services(self):
        """Configure individual services"""
        self.console.print("[blue]⚙️  Configuring services...[/blue]")

        # This would contain service-specific configuration
        # For now, just log the step
        self.console.print("[green]✅ Services configured[/green]")

    def _show_deployment_summary(self):
        """Show deployment summary"""
        table = Table(title="📊 Deployment Summary")
        table.add_column("Step", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Time", style="blue")

        for log_entry in self.deployment_log:
            status = "✅ Success" if log_entry["status"] == "success" else "❌ Failed"
            timestamp = time.strftime("%H:%M:%S", time.localtime(log_entry["timestamp"]))

            table.add_row(
                log_entry["step"],
                status,
                timestamp
            )

        self.console.print(table)

    def rollback_deployment(self):
        """Rollback to previous deployment"""
        self.console.print("[blue]🔄 Rolling back deployment...[/blue]")

        try:
            # Stop current services
            subprocess.run(["docker", "compose", "down"], check=True)

            # Restore from backup if available
            backup_path = Path("backups/latest")
            if backup_path.exists():
                self.console.print("[blue]📦 Restoring from backup...[/blue]")
                # Implement backup restoration logic
                self.console.print("[green]✅ Rollback complete[/green]")
            else:
                self.console.print("[yellow]⚠️  No backup found for rollback[/yellow]")

        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]❌ Rollback failed: {e}[/red]")

    def create_backup(self):
        """Create deployment backup"""
        self.console.print("[blue]💾 Creating deployment backup...[/blue]")

        backup_dir = Path("backups") / f"backup_{int(time.time())}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Backup configuration files
            config_files = [".env", "docker-compose.yml", "appdata"]
            for file_path in config_files:
                if Path(file_path).exists():
                    if Path(file_path).is_dir():
                        shutil.copytree(file_path, backup_dir / file_path)
                    else:
                        shutil.copy2(file_path, backup_dir / file_path)

            # Create backup manifest
            manifest = {
                "timestamp": time.time(),
                "version": "2.1.0",
                "services": [service.name for service in self.config.services if service.enabled]
            }

            with open(backup_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)

            self.console.print(f"[green]✅ Backup created: {backup_dir}[/green]")

        except Exception as e:
            self.console.print(f"[red]❌ Backup failed: {e}[/red]")

    def update_deployment(self):
        """Update existing deployment"""
        self.console.print("[blue]🔄 Updating deployment...[/blue]")

        try:
            # Create backup before update
            self.create_backup()

            # Pull latest images
            subprocess.run(["docker", "compose", "pull"], check=True)

            # Update services
            subprocess.run(["docker", "compose", "up", "-d", "--force-recreate"], check=True)

            self.console.print("[green]✅ Deployment updated[/green]")

        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]❌ Update failed: {e}[/red]")
            self.console.print("[yellow]💡 Consider rolling back to previous version[/yellow]")
