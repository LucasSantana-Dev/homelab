#!/usr/bin/env python3
"""
Homelab Container Management System
Modern Python-based container status checking and updating
"""

import json
import os
import subprocess
import sys
import time
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


class ContainerManager:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.project_root = Path(__file__).parent.parent.parent
        self.backup_dir = self.project_root / "backups"
        self.appdata_dir = self.project_root / "appdata"

        # Container configurations
        self.containers = {
            "homeassistant": {
                "image": "ghcr.io/home-assistant/home-assistant:stable",
                "compose_service": "homeassistant",
                "data_path": "homeassistant",
                "port": 8123,
                "health_check_url": "http://localhost:8123",
            },
            "homepage": {
                "image": "ghcr.io/gethomepage/homepage:latest",
                "compose_service": "homepage",
                "data_path": "homepage",
                "port": 3000,
                "health_check_url": "http://localhost:3000",
            },
            "grafana": {
                "image": "grafana/grafana-oss:latest",
                "compose_service": "grafana",
                "data_path": "grafana",
                "port": 3002,
                "health_check_url": "http://localhost:3002",
            },
            "filebrowser": {
                "image": "filebrowser/filebrowser:latest",
                "compose_service": None,  # Not in compose
                "data_path": "filebrowser",
                "port": 8080,
                "health_check_url": "http://localhost:8080",
            },
        }

    def check_docker_running(self) -> bool:
        """Check if Docker is running and accessible"""
        try:
            self.docker_client.ping()
            return True
        except docker.errors.APIError:
            console.print("❌ Docker is not running or not accessible", style="red")
            return False

    def get_container_status(self) -> List[Dict]:
        """Get status of all homelab containers"""
        containers = []

        for name, config in self.containers.items():
            try:
                container = self.docker_client.containers.get(name)
                containers.append(
                    {
                        "name": name,
                        "status": container.status,
                        "image": (
                            container.image.tags[0]
                            if container.image.tags
                            else "unknown"
                        ),
                        "ports": container.ports,
                        "running": container.status == "running",
                    }
                )
            except docker.errors.NotFound:
                containers.append(
                    {
                        "name": name,
                        "status": "not found",
                        "image": "unknown",
                        "ports": {},
                        "running": False,
                    }
                )

        return containers

    def display_container_status(self):
        """Display current container status in a nice table"""
        console.print(
            Panel.fit("🔍 Homelab Container Status", style="blue", border_style="blue")
        )

        containers = self.get_container_status()

        table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
        table.add_column("Container", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Image", style="magenta")
        table.add_column("Ports", style="green")

        for container in containers:
            status_color = "green" if container["running"] else "red"
            status_text = "🟢 Running" if container["running"] else "🔴 Stopped"

            ports = []
            for port_info in container["ports"].values():
                for port in port_info:
                    host_port = port.get("HostPort", "unknown")
                    private_port = port.get(
                        "PrivatePort", port.get("TargetPort", "unknown")
                    )
                    ports.append(f"{host_port}:{private_port}")

            table.add_row(
                container["name"],
                f"[{status_color}]{status_text}[/{status_color}]",
                container["image"],
                ", ".join(ports) if ports else "No ports",
            )

        console.print(table)
        console.print()

    def check_for_updates(self) -> Dict[str, bool]:
        """Check for available container updates"""
        console.print("🔍 Checking for available updates...", style="blue")

        updates_available = {}

        for name, config in self.containers.items():
            try:
                # Get current image
                current_image = self.docker_client.images.get(config["image"])
                current_id = current_image.short_id

                # Pull latest image
                console.print(f"Checking {name}...", end=" ")
                latest_image = self.docker_client.images.pull(config["image"])
                latest_id = latest_image.short_id

                if current_id != latest_id:
                    updates_available[name] = True
                    console.print("🟡 UPDATE AVAILABLE", style="yellow")
                else:
                    updates_available[name] = False
                    console.print("✅ Up to date", style="green")

            except Exception as e:
                console.print(f"❌ Failed to check {name}: {e}", style="red")
                updates_available[name] = False

        return updates_available

    def backup_container_data(self, container_name: str) -> Path:
        """Backup container data before update"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{timestamp}_{container_name}"
        backup_path.mkdir(parents=True, exist_ok=True)

        config = self.containers[container_name]
        data_path = self.appdata_dir / config["data_path"]

        if data_path.exists():
            console.print(f"📦 Backing up {container_name} data...", style="blue")
            subprocess.run(["cp", "-r", str(data_path), str(backup_path)], check=True)
            console.print(f"✅ Backup created: {backup_path}", style="green")
        else:
            console.print(
                f"⚠️ No data directory found for {container_name}", style="yellow"
            )

        return backup_path

    def update_container(self, container_name: str) -> bool:
        """Update a specific container"""
        if container_name not in self.containers:
            console.print(f"❌ Unknown container: {container_name}", style="red")
            return False

        config = self.containers[container_name]

        console.print(f"🔄 Updating {container_name}...", style="blue")

        # Create backup
        self.backup_container_data(container_name)

        try:
            # Stop container if running
            try:
                container = self.docker_client.containers.get(container_name)
                if container.status == "running":
                    console.print(f"⏹️ Stopping {container_name}...", style="yellow")
                    container.stop()
                container.remove()
            except docker.errors.NotFound:
                pass

            # Pull latest image
            console.print(
                f"📥 Pulling latest image for {container_name}...", style="blue"
            )
            self.docker_client.images.pull(config["image"])

            # Start container using docker-compose
            if config["compose_service"]:
                console.print(
                    f"🚀 Starting {container_name} with docker-compose...", style="blue"
                )
                subprocess.run(
                    ["docker-compose", "up", "-d", config["compose_service"]],
                    cwd=self.project_root,
                    check=True,
                )
            else:
                console.print(
                    f"⚠️ {container_name} is not in docker-compose.yml", style="yellow"
                )
                return False

            # Wait for container to be healthy
            if self.wait_for_container_health(container_name):
                console.print(
                    f"✅ {container_name} updated successfully!", style="green"
                )
                return True
            else:
                console.print(
                    f"❌ {container_name} failed to start properly", style="red"
                )
                return False

        except Exception as e:
            console.print(f"❌ Failed to update {container_name}: {e}", style="red")
            return False

    def wait_for_container_health(
        self, container_name: str, max_attempts: int = 30
    ) -> bool:
        """Wait for container to be healthy"""
        config = self.containers[container_name]

        console.print(f"⏳ Waiting for {container_name} to be ready...", style="blue")

        for attempt in range(1, max_attempts + 1):
            try:
                container = self.docker_client.containers.get(container_name)
                if container.status == "running":
                    # Try to access the health check URL
                    if config["health_check_url"]:
                        import requests

                        try:
                            response = requests.get(
                                config["health_check_url"], timeout=5
                            )
                            if response.status_code < 500:
                                console.print(
                                    f"✅ {container_name} is healthy!", style="green"
                                )
                                return True
                        except requests.exceptions.RequestException:
                            pass
                    else:
                        console.print(f"✅ {container_name} is running!", style="green")
                        return True

                console.print(
                    f"⏳ Attempt {attempt}/{max_attempts}: {container_name} not ready yet...",
                    style="yellow",
                )
                time.sleep(2)

            except docker.errors.NotFound:
                console.print(
                    f"⏳ Attempt {attempt}/{max_attempts}: {container_name} not found yet...",
                    style="yellow",
                )
                time.sleep(2)

        console.print(f"❌ {container_name} failed to become healthy", style="red")
        return False

    def show_disk_usage(self):
        """Show Docker disk usage"""
        console.print("💾 Docker disk usage:", style="blue")

        try:
            result = subprocess.run(
                ["docker", "system", "df"], capture_output=True, text=True
            )
            console.print(result.stdout)
        except Exception as e:
            console.print(f"❌ Failed to get disk usage: {e}", style="red")

    def show_recent_logs(self, container_name: str, lines: int = 3):
        """Show recent logs for a container"""
        try:
            container = self.docker_client.containers.get(container_name)
            logs = container.logs(tail=lines).decode("utf-8")
            console.print(f"📋 Recent logs for {container_name}:", style="blue")
            console.print(f"```\n{logs}\n```")
        except Exception as e:
            console.print(
                f"❌ Failed to get logs for {container_name}: {e}", style="red"
            )

    def cleanup_old_images(self):
        """Clean up old Docker images"""
        console.print("🧹 Cleaning up old Docker images...", style="blue")

        try:
            subprocess.run(["docker", "image", "prune", "-f"], check=True)
            console.print("✅ Old images cleaned up", style="green")
        except Exception as e:
            console.print(f"❌ Failed to clean up images: {e}", style="red")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Homelab Container Manager")
    parser.add_argument(
        "action",
        choices=["status", "update", "check-updates"],
        help="Action to perform",
    )
    parser.add_argument("--container", "-c", help="Specific container to update")
    parser.add_argument(
        "--all", "-a", action="store_true", help="Update all containers"
    )

    args = parser.parse_args()

    manager = ContainerManager()

    # Check if Docker is running
    if not manager.check_docker_running():
        sys.exit(1)

    if args.action == "status":
        manager.display_container_status()
        manager.show_disk_usage()

    elif args.action == "check-updates":
        manager.display_container_status()
        manager.check_for_updates()

    elif args.action == "update":
        if args.all:
            console.print("🔄 Updating all containers...", style="blue")
            for container_name in manager.containers.keys():
                manager.update_container(container_name)
        elif args.container:
            if args.container in manager.containers:
                manager.update_container(args.container)
            else:
                console.print(f"❌ Unknown container: {args.container}", style="red")
                sys.exit(1)
        else:
            console.print("❌ Please specify --container or --all", style="red")
            sys.exit(1)

        manager.cleanup_old_images()
        manager.display_container_status()


if __name__ == "__main__":
    main()
