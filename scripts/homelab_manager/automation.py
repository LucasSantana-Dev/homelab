#!/usr/bin/env python3
"""
Homelab Automation System
Python-based automation for homelab management
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import docker
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Initialize console for rich output
console = Console()


class HomelabAutomation:
    """Main automation class for homelab management"""

    def __init__(self, homelab_dir: Optional[str] = None):
        self.homelab_dir = (
            Path(homelab_dir) if homelab_dir else Path(__file__).parent.parent.parent
        )
        self.backup_dir = self.homelab_dir / "backups"
        self.log_dir = self.homelab_dir / "logs"
        self.env_file = self.homelab_dir / ".env"

        # Create directories
        self.backup_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)

        # Setup logging
        self.setup_logging()

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except docker.errors.DockerException:
            console.print("❌ Docker is not running or not accessible", style="red")
            sys.exit(1)

    def setup_logging(self):
        """Setup logging configuration"""
        log_file = self.log_dir / "homelab.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def load_environment(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars: Dict[str, str] = {}

        if not self.env_file.exists():
            console.print("❌ .env file not found", style="red")
            return env_vars

        try:
            with open(self.env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key] = value
                        os.environ[key] = value

            self.logger.info("Environment variables loaded successfully")
            return env_vars

        except Exception as e:
            console.print(f"❌ Error loading environment: {e}", style="red")
            return env_vars

    def check_docker_running(self) -> bool:
        """Check if Docker is running"""
        try:
            self.docker_client.ping()
            return True
        except docker.errors.APIError:
            return False

    def deploy(self):
        """Deploy homelab services"""
        console.print(Panel.fit("🚀 Deploying Homelab Services", style="blue"))

        if not self.check_docker_running():
            console.print("❌ Docker is not running", style="red")
            return False

        try:
            # Change to homelab directory
            os.chdir(self.homelab_dir)

            # Create networks if they don't exist
            self.create_networks()

            # Start services
            console.print("📦 Starting services...", style="blue")
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                capture_output=True,
                text=True,
                check=True,
            )

            # Wait for services to be ready
            console.print("⏳ Waiting for services to start...", style="yellow")
            time.sleep(30)

            # Check health
            self.check_health()

            console.print("✅ Homelab deployment complete!", style="green")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"❌ Deployment failed: {e}", style="red")
            return False

    def create_networks(self):
        """Create Docker networks if they don't exist"""
        networks = ["homelab", "monitoring"]

        for network_name in networks:
            try:
                self.docker_client.networks.get(network_name)
                console.print(
                    f"✅ Network '{network_name}' already exists", style="green"
                )
            except docker.errors.NotFound:
                try:
                    self.docker_client.networks.create(network_name, driver="bridge")
                    console.print(f"✅ Created network '{network_name}'", style="green")
                except Exception as e:
                    console.print(
                        f"⚠️ Could not create network '{network_name}': {e}",
                        style="yellow",
                    )

    def update(self):
        """Update homelab services"""
        console.print(Panel.fit("🔄 Updating Homelab Services", style="blue"))

        try:
            # Create backup first
            self.backup()

            # Change to homelab directory
            os.chdir(self.homelab_dir)

            # Pull latest images
            console.print("📥 Pulling latest images...", style="blue")
            subprocess.run(["docker-compose", "pull"], check=True)

            # Restart services
            console.print("🔄 Restarting services...", style="blue")
            subprocess.run(
                ["docker-compose", "up", "-d", "--remove-orphans"], check=True
            )

            # Clean up old images
            console.print("🧹 Cleaning up old images...", style="blue")
            subprocess.run(["docker", "image", "prune", "-f"], check=True)

            # Check health
            self.check_health()

            console.print("✅ Update complete!", style="green")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"❌ Update failed: {e}", style="red")
            return False

    def backup(self):
        """Create backup of homelab"""
        console.print(Panel.fit("💾 Creating Backup", style="blue"))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / timestamp
        backup_path.mkdir(exist_ok=True)

        try:
            # Backup Docker volumes
            volumes = [
                "portainer_data",
                "prometheus_data",
                "uptime_kuma_data",
                "whats_up_docker_data",
            ]

            for volume in volumes:
                try:
                    console.print(f"📦 Backing up {volume}...", style="blue")
                    subprocess.run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "-v",
                            f"{volume}:/data",
                            "-v",
                            f"{backup_path}:/backup",
                            "alpine",
                            "tar",
                            "czf",
                            f"/backup/{volume}.tar.gz",
                            "-C",
                            "/data",
                            ".",
                        ],
                        check=True,
                        capture_output=True,
                    )
                except subprocess.CalledProcessError:
                    console.print(f"⚠️ Could not backup {volume}", style="yellow")

            # Backup application data
            appdata_path = self.homelab_dir / "appdata"
            if appdata_path.exists():
                console.print("📁 Backing up application data...", style="blue")
                shutil.make_archive(
                    str(backup_path / "appdata"), "gztar", str(appdata_path)
                )

            # Backup configuration files
            config_files = ["docker-compose.yml", ".env"]
            console.print("⚙️ Backing up configuration...", style="blue")

            for config_file in config_files:
                src = self.homelab_dir / config_file
                if src.exists():
                    shutil.copy2(src, backup_path / config_file)

            # Create backup manifest
            manifest = {
                "backup_created": datetime.now().isoformat(),
                "hostname": os.uname().nodename,
                "docker_version": subprocess.run(
                    ["docker", "--version"], capture_output=True, text=True
                ).stdout.strip(),
                "services": self.get_service_status(),
            }

            with open(backup_path / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)

            # Clean up old backups (keep last 7 days)
            self.cleanup_old_backups()

            console.print(f"✅ Backup created: {backup_path}", style="green")
            console.print(
                f"📊 Backup size: {self.get_directory_size(backup_path)}", style="blue"
            )

            return str(backup_path)

        except Exception as e:
            console.print(f"❌ Backup failed: {e}", style="red")
            return None

    def restore(self, backup_path: str):
        """Restore from backup"""
        console.print(
            Panel.fit(f"🔄 Restoring from Backup: {backup_path}", style="blue")
        )

        backup_dir = Path(backup_path)
        if not backup_dir.exists():
            console.print(f"❌ Backup directory not found: {backup_path}", style="red")
            return False

        try:
            # Stop services
            os.chdir(self.homelab_dir)
            subprocess.run(["docker-compose", "down"], check=True)

            # Restore volumes
            volumes = [
                "portainer_data",
                "prometheus_data",
                "uptime_kuma_data",
                "whats_up_docker_data",
            ]

            for volume in volumes:
                volume_file = backup_dir / f"{volume}.tar.gz"
                if volume_file.exists():
                    console.print(f"📦 Restoring {volume}...", style="blue")
                    subprocess.run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "-v",
                            f"{volume}:/data",
                            "-v",
                            f"{backup_dir}:/backup",
                            "alpine",
                            "tar",
                            "xzf",
                            f"/backup/{volume}.tar.gz",
                            "-C",
                            "/data",
                        ],
                        check=True,
                    )

            # Restore application data
            appdata_archive = backup_dir / "appdata.tar.gz"
            if appdata_archive.exists():
                console.print("📁 Restoring application data...", style="blue")
                shutil.unpack_archive(str(appdata_archive), str(self.homelab_dir))

            # Restore configuration files
            config_files = ["docker-compose.yml", ".env"]
            for config_file in config_files:
                src = backup_dir / config_file
                if src.exists():
                    shutil.copy2(src, self.homelab_dir / config_file)

            # Start services
            subprocess.run(["docker-compose", "up", "-d"], check=True)

            # Check health
            self.check_health()

            console.print("✅ Restore complete!", style="green")
            return True

        except Exception as e:
            console.print(f"❌ Restore failed: {e}", style="red")
            return False

    def check_health(self):
        """Check health of all services"""
        console.print(Panel.fit("🔍 Health Check", style="blue"))

        services = [
            ("Homepage", "http://localhost:3000"),
            ("Home Assistant", "http://localhost:8123"),
            ("Grafana", "http://localhost:3002"),
            ("Portainer", "http://localhost:9000"),
            ("Pi-hole", "http://localhost:8054"),
        ]

        healthy = 0
        total = len(services)

        for name, url in services:
            try:
                import requests

                response = requests.get(url, timeout=5)
                if response.status_code < 500:
                    console.print(f"✅ {name} is healthy", style="green")
                    healthy += 1
                else:
                    console.print(
                        f"❌ {name} returned status {response.status_code}", style="red"
                    )
            except Exception:
                console.print(f"❌ {name} is not responding", style="red")

        console.print(
            f"\n📊 Health Summary: {healthy}/{total} services healthy", style="blue"
        )

        if healthy == total:
            console.print("🎉 All services are healthy!", style="green")
        else:
            console.print("⚠️ Some services are not responding", style="yellow")

    def get_service_status(self) -> List[Dict]:
        """Get status of all services"""
        try:
            containers = self.docker_client.containers.list()
            return [
                {
                    "name": container.name,
                    "status": container.status,
                    "image": (
                        container.image.tags[0] if container.image.tags else "unknown"
                    ),
                }
                for container in containers
            ]
        except Exception:
            return []

    def get_directory_size(self, path: Path) -> str:
        """Get human-readable directory size"""
        total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

        for unit in ["B", "KB", "MB", "GB"]:
            if total_size < 1024.0:
                return f"{total_size:.1f} {unit}"
            total_size /= 1024.0
        return f"{total_size:.1f} TB"

    def cleanup_old_backups(self, days: int = 7):
        """Clean up old backups"""
        cutoff_time: float = time.time() - (days * 24 * 60 * 60)

        for backup_dir in self.backup_dir.iterdir():
            if backup_dir.is_dir() and backup_dir.stat().st_mtime < cutoff_time:
                shutil.rmtree(backup_dir)
                console.print(
                    f"🗑️ Removed old backup: {backup_dir.name}", style="yellow"
                )

    def cleanup(self):
        """Clean up unused Docker resources"""
        console.print(Panel.fit("🧹 Cleaning Up", style="blue"))

        try:
            # Remove stopped containers
            subprocess.run(["docker", "container", "prune", "-f"], check=True)

            # Remove unused images
            subprocess.run(["docker", "image", "prune", "-f"], check=True)

            # Remove unused volumes
            subprocess.run(["docker", "volume", "prune", "-f"], check=True)

            # Remove unused networks
            subprocess.run(["docker", "network", "prune", "-f"], check=True)

            console.print("✅ Cleanup complete!", style="green")

        except subprocess.CalledProcessError as e:
            console.print(f"❌ Cleanup failed: {e}", style="red")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Homelab Automation System")
    parser.add_argument(
        "action",
        choices=["deploy", "update", "backup", "restore", "health", "cleanup"],
        help="Action to perform",
    )
    parser.add_argument("--backup-path", help="Backup path for restore")

    args = parser.parse_args()

    automation = HomelabAutomation()

    if args.action == "deploy":
        automation.deploy()
    elif args.action == "update":
        automation.update()
    elif args.action == "backup":
        automation.backup()
    elif args.action == "restore":
        if not args.backup_path:
            console.print("❌ Please specify --backup-path for restore", style="red")
            sys.exit(1)
        automation.restore(args.backup_path)
    elif args.action == "health":
        automation.check_health()
    elif args.action == "cleanup":
        automation.cleanup()


if __name__ == "__main__":
    main()
