#!/usr/bin/env python3
"""
Homelab Update Manager
Python-based update management for homelab services
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import docker
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Initialize console
console = Console()


class HomelabUpdateManager:
    """Update management for homelab services"""

    def __init__(self):
        self.homelab_dir = Path(__file__).parent.parent.parent
        self.log_dir = self.homelab_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except docker.errors.DockerException:
            console.print("❌ Docker is not running or not accessible", style="red")
            sys.exit(1)

        # Services to check for updates
        self.services = [
            "ghcr.io/home-assistant/home-assistant:stable",
            "ghcr.io/gethomepage/homepage:latest",
            "grafana/grafana-oss:latest",
            "portainer/portainer-ce:latest",
            "pihole/pihole:latest",
            "prom/prometheus:latest",
            "prom/node-exporter:latest",
            "louislam/uptime-kuma:1",
            "fmartinou/whats-up-docker:latest",
        ]

    def check_image_updates(
        self, image: str, current_tag: str
    ) -> Tuple[bool, str, str]:
        """Check if an image has updates available"""
        try:
            # Get current image ID
            current_image = self.docker_client.images.get(f"{image}:{current_tag}")
            current_id = current_image.short_id

            # Pull latest image
            console.print(f"📥 Pulling latest image for {image}...", style="blue")
            latest_image = self.docker_client.images.pull(f"{image}:latest")
            latest_id = latest_image.short_id

            if current_id != latest_id:
                return True, current_id, latest_id
            else:
                return False, current_id, latest_id

        except docker.errors.ImageNotFound:
            return False, "Not found", "Not found"
        except Exception as e:
            console.print(f"⚠️ Error checking {image}: {e}", style="yellow")
            return False, "Error", "Error"

    def check_all_updates(self) -> List[Dict]:
        """Check all services for updates"""
        console.print(Panel.fit("🔍 Checking for Updates", style="blue"))

        updates_available = []

        for service in self.services:
            image, tag = service.split(":", 1)

            console.print(f"Checking {image}...", style="blue")
            has_update, current_id, latest_id = self.check_image_updates(image, tag)

            if has_update:
                updates_available.append(
                    {
                        "image": image,
                        "tag": tag,
                        "current_id": current_id,
                        "latest_id": latest_id,
                    }
                )
                console.print(f"🔄 Update available for {image}", style="yellow")
            else:
                console.print(f"✅ {image} is up to date", style="green")

        if updates_available:
            console.print(
                f"\n🔄 {len(updates_available)} updates available", style="yellow"
            )
        else:
            console.print("\n✅ All services are up to date", style="green")

        return updates_available

    def update_service(self, service_name: str) -> bool:
        """Update a specific service"""
        console.print(Panel.fit(f"🔄 Updating {service_name}", style="blue"))

        try:
            # Change to homelab directory
            os.chdir(self.homelab_dir)

            # Pull latest image
            console.print(
                f"📥 Pulling latest image for {service_name}...", style="blue"
            )
            subprocess.run(["docker-compose", "pull", service_name], check=True)

            # Restart service
            console.print(f"🔄 Restarting {service_name}...", style="blue")
            subprocess.run(["docker-compose", "up", "-d", service_name], check=True)

            # Wait and check if it's running
            time.sleep(10)

            # Check if service is running
            containers = self.docker_client.containers.list()
            service_running = any(
                container.name == service_name for container in containers
            )

            if service_running:
                console.print(f"✅ {service_name} updated successfully", style="green")
                return True
            else:
                console.print(f"❌ {service_name} update failed", style="red")
                return False

        except subprocess.CalledProcessError as e:
            console.print(f"❌ Update failed: {e}", style="red")
            return False

    def update_all_services(self) -> bool:
        """Update all services"""
        console.print(Panel.fit("🔄 Updating All Services", style="blue"))

        try:
            # Create backup first
            console.print("💾 Creating backup before update...", style="blue")
            from .automation import HomelabAutomation

            automation = HomelabAutomation()
            backup_path = automation.backup()

            if not backup_path:
                console.print("❌ Backup failed, aborting update", style="red")
                return False

            # Change to homelab directory
            os.chdir(self.homelab_dir)

            # Pull all latest images
            console.print("📥 Pulling latest images...", style="blue")
            subprocess.run(["docker-compose", "pull"], check=True)

            # Restart all services
            console.print("🔄 Restarting services...", style="blue")
            subprocess.run(
                ["docker-compose", "up", "-d", "--remove-orphans"], check=True
            )

            # Clean up old images
            console.print("🧹 Cleaning up old images...", style="blue")
            subprocess.run(["docker", "image", "prune", "-f"], check=True)

            # Check health
            console.print("🔍 Checking service health...", style="blue")
            from .health import HomelabHealthMonitor

            monitor = HomelabHealthMonitor()
            monitor.run_health_check()

            console.print("✅ Update complete!", style="green")
            return True

        except subprocess.CalledProcessError as e:
            console.print(f"❌ Update failed: {e}", style="red")
            return False

    def show_versions(self):
        """Show current versions of all services"""
        console.print(Panel.fit("📋 Service Versions", style="blue"))

        version_table = Table(show_header=True, header_style="bold blue")
        version_table.add_column("Service", style="cyan")
        version_table.add_column("Image", style="blue")
        version_table.add_column("Status", style="green")
        version_table.add_column("Created", style="yellow")

        try:
            containers = self.docker_client.containers.list()
            container_dict = {container.name: container for container in containers}

            for service in self.services:
                image, tag = service.split(":", 1)
                service_name = image.split("/")[-1]  # Get service name from image

                # Find matching container
                matching_container = None
                for container in containers:
                    if any(
                        service_name in image_tag for image_tag in container.image.tags
                    ):
                        matching_container = container
                        break

                if matching_container:
                    # Get image creation date
                    try:
                        image_info = self.docker_client.images.get(service)
                        created_date = image_info.attrs["Created"][:10]  # Get date part
                        status = (
                            "Running"
                            if matching_container.status == "running"
                            else "Stopped"
                        )
                        status_color = (
                            "green" if matching_container.status == "running" else "red"
                        )
                    except Exception:
                        created_date = "Unknown"
                        status = "Unknown"
                        status_color = "yellow"

                    version_table.add_row(
                        service_name,
                        service,
                        f"[{status_color}]{status}[/{status_color}]",
                        created_date,
                    )
                else:
                    version_table.add_row(
                        service_name, service, "[red]Not running[/red]", "N/A"
                    )

        except Exception as e:
            console.print(f"⚠️ Error getting versions: {e}", style="yellow")

        console.print(version_table)

    def auto_check(self):
        """Automated update check (for cron jobs)"""
        console.print("🤖 Automated update check started", style="blue")

        updates = self.check_all_updates()

        if updates:
            console.print(f"🔄 {len(updates)} updates available", style="yellow")
            console.print(
                "📧 Notification: Updates available for homelab services", style="blue"
            )

            # Log to file for cron jobs
            log_file = self.log_dir / "updates.log"
            with open(log_file, "a") as f:
                f.write(
                    f"{datetime.now().isoformat()} - {len(updates)} updates available\n"
                )
        else:
            console.print("✅ No updates available", style="green")

        console.print("🤖 Automated update check completed", style="blue")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Homelab Update Manager")
    parser.add_argument(
        "action",
        choices=["check", "update", "update-service", "versions", "auto-check"],
        help="Action to perform",
    )
    parser.add_argument("--service", help="Service name for update-service")

    args = parser.parse_args()

    update_manager = HomelabUpdateManager()

    if args.action == "check":
        update_manager.check_all_updates()
    elif args.action == "update":
        update_manager.update_all_services()
    elif args.action == "update-service":
        if not args.service:
            console.print("❌ Please specify --service for update-service", style="red")
            sys.exit(1)
        update_manager.update_service(args.service)
    elif args.action == "versions":
        update_manager.show_versions()
    elif args.action == "auto-check":
        update_manager.auto_check()


if __name__ == "__main__":
    main()
