"""
Docker Management - Python replacement for Docker Compose operations
"""

import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import docker
from docker.errors import DockerException

class DockerManager:
    """Manages Docker containers and services"""

    def __init__(self, config):
        self.config = config
        self.console = Console()
        self.client = None
        self._connect_docker()

    def _connect_docker(self):
        """Connect to Docker daemon"""
        try:
            self.client = docker.from_env()
            self.client.ping()
        except DockerException as e:
            self.console.print(f"[red]Failed to connect to Docker: {e}[/red]")
            raise

    def get_service_status(self, container_name: str) -> str:
        """Get status of a specific service"""
        try:
            container = self.client.containers.get(container_name)
            return container.status
        except docker.errors.NotFound:
            return "Not Found"
        except Exception as e:
            return f"Error: {e}"

    def start_all_services(self):
        """Start all homelab services"""
        self.console.print("[blue]🐳 Starting Docker services...[/blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:

            # Start with docker-compose
            task = progress.add_task("Starting services with docker-compose...", total=None)

            try:
                result = subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    cwd=Path.cwd(),
                    capture_output=True,
                    text=True,
                    check=True
                )
                progress.update(task, description="✅ All services started")
            except subprocess.CalledProcessError as e:
                self.console.print(f"[red]Failed to start services: {e.stderr}[/red]")
                raise

    def stop_all_services(self):
        """Stop all homelab services"""
        self.console.print("[blue]🛑 Stopping Docker services...[/blue]")

        try:
            subprocess.run(
                ["docker", "compose", "down"],
                cwd=Path.cwd(),
                check=True
            )
            self.console.print("[green]✅ All services stopped[/green]")
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Failed to stop services: {e}[/red]")
            raise

    def restart_service(self, service_name: str):
        """Restart a specific service"""
        self.console.print(f"[blue]🔄 Restarting {service_name}...[/blue]")

        try:
            subprocess.run(
                ["docker", "compose", "restart", service_name],
                cwd=Path.cwd(),
                check=True
            )
            self.console.print(f"[green]✅ {service_name} restarted[/green]")
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Failed to restart {service_name}: {e}[/red]")
            raise

    def update_all_services(self):
        """Update all services to latest images"""
        self.console.print("[blue]🔄 Updating all services...[/blue]")

        try:
            # Pull latest images
            subprocess.run(
                ["docker", "compose", "pull"],
                cwd=Path.cwd(),
                check=True
            )

            # Recreate containers with new images
            subprocess.run(
                ["docker", "compose", "up", "-d", "--force-recreate"],
                cwd=Path.cwd(),
                check=True
            )

            self.console.print("[green]✅ All services updated[/green]")
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Failed to update services: {e}[/red]")
            raise

    def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """Get logs for a specific service"""
        try:
            result = subprocess.run(
                ["docker", "compose", "logs", "--tail", str(lines), service_name],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error getting logs: {e.stderr}"

    def backup_service(self, service, backup_path: Path):
        """Backup a specific service"""
        service_path = backup_path / service.name
        service_path.mkdir(exist_ok=True)

        try:
            # Get container volumes
            container = self.client.containers.get(service.container_name)
            volumes = container.attrs['Mounts']

            for volume in volumes:
                if volume['Type'] == 'bind':
                    source = volume['Source']
                    dest = service_path / Path(source).name

                    # Create tar backup
                    subprocess.run([
                        "tar", "-czf", str(dest) + ".tar.gz", "-C",
                        str(Path(source).parent), Path(source).name
                    ], check=True)

            self.console.print(f"[green]✅ Backed up {service.name}[/green]")

        except Exception as e:
            self.console.print(f"[red]Failed to backup {service.name}: {e}[/red]")

    def get_container_stats(self) -> Dict:
        """Get container statistics"""
        stats = {}

        for service in self.config.services:
            if not service.enabled:
                continue

            try:
                container = self.client.containers.get(service.container_name)
                stats[service.name] = {
                    "status": container.status,
                    "created": container.attrs['Created'],
                    "image": container.attrs['Config']['Image'],
                    "ports": container.attrs['NetworkSettings']['Ports']
                }
            except docker.errors.NotFound:
                stats[service.name] = {"status": "Not Found"}

        return stats

    def cleanup_containers(self):
        """Clean up unused containers and images"""
        self.console.print("[blue]🧹 Cleaning up Docker resources...[/blue]")

        try:
            # Remove stopped containers
            subprocess.run(["docker", "container", "prune", "-f"], check=True)

            # Remove unused images
            subprocess.run(["docker", "image", "prune", "-f"], check=True)

            # Remove unused volumes
            subprocess.run(["docker", "volume", "prune", "-f"], check=True)

            # Remove unused networks
            subprocess.run(["docker", "network", "prune", "-f"], check=True)

            self.console.print("[green]✅ Docker cleanup complete[/green]")

        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Cleanup failed: {e}[/red]")

    def health_check_all(self) -> Dict[str, bool]:
        """Perform health checks on all services"""
        results = {}

        for service in self.config.services:
            if not service.enabled:
                continue

            try:
                # Check if container is running
                container = self.client.containers.get(service.container_name)
                if container.status != "running":
                    results[service.name] = False
                    continue

                # Perform health check
                if service.health_check:
                    # This would be implemented based on the specific health check
                    results[service.name] = self._perform_health_check(service)
                else:
                    results[service.name] = True

            except Exception as e:
                self.console.print(f"[red]Health check failed for {service.name}: {e}[/red]")
                results[service.name] = False

        return results

    def _perform_health_check(self, service) -> bool:
        """Perform specific health check for a service"""
        # This would implement actual health checks
        # For now, just check if container is running
        try:
            container = self.client.containers.get(service.container_name)
            return container.status == "running"
        except:
            return False
