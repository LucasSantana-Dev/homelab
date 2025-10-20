#!/usr/bin/env python3
"""
Container Management Service
Handles Docker container operations for homelab services
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

import docker
from rich.console import Console

# Initialize console
console = Console()


class ServiceInfo(TypedDict):
    """Type definition for service information"""

    port: int
    health_url: str
    data_path: str


class ContainerManager:
    """Modern container management for homelab services"""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.project_root = Path(__file__).parent.parent.parent
        self.backup_dir = self.project_root / "backups"
        self.appdata_dir = self.project_root / "appdata"

        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)

        # Service configurations
        self.services = {
            "homepage": {
                "port": 3000,
                "health_url": "http://localhost:3000",
                "data_path": "homepage",
            },
            "stremio": {
                "port": 8080,
                "health_url": "http://localhost:8080",
                "data_path": "stremio",
            },
            "homeassistant": {
                "port": 8123,
                "health_url": "http://localhost:8123",
                "data_path": "homeassistant",
            },
            "portainer": {
                "port": 9000,
                "health_url": "http://localhost:9000",
                "data_path": "portainer",
            },
            "pihole": {
                "port": 8054,
                "health_url": "http://localhost:8054",
                "data_path": "pihole",
            },
            "grafana": {
                "port": 3002,
                "health_url": "http://localhost:3002",
                "data_path": "grafana",
            },
            "uptime-kuma": {
                "port": 3001,
                "health_url": "http://localhost:3001",
                "data_path": "uptime-kuma",
            },
            "whats-up-docker": {
                "port": 3003,
                "health_url": "http://localhost:3003",
                "data_path": "whats-up-docker",
            },
        }

    def get_container_status(self) -> List[Dict]:
        """Get status of all homelab containers"""
        containers = []

        try:
            for container in self.docker_client.containers.list(all=True):
                if any(service in container.name for service in self.services.keys()):
                    service_info = self._get_service_info(container.name)
                    if service_info:
                        containers.append(
                            {
                                "name": container.name,
                                "status": container.status,
                                "port": service_info.get("port"),
                                "health": self._check_container_health(container.name),
                                "image": (
                                    container.image.tags[0]
                                    if container.image.tags
                                    else "unknown"
                                ),
                            }
                        )
        except Exception as e:
            console.print(f"Error getting container status: {e}")

        return containers

    def _get_service_info(self, container_name: str) -> Optional[ServiceInfo]:
        """Get service information for a container"""
        for service, info in self.services.items():
            if service in container_name:
                return ServiceInfo(info)  # type: ignore
        return None

    def _check_container_health(self, container_name: str) -> str:
        """Check if a container is healthy"""
        try:
            container = self.docker_client.containers.get(container_name)
            if container.status != "running":
                return "stopped"

            # Check if container has health status
            health = container.attrs.get("State", {}).get("Health", {})
            if health:
                return str(health.get("Status", "unknown"))

            return "running"
        except Exception:
            return "unknown"

    def deploy(self) -> Dict:
        """Deploy homelab services"""
        try:
            console.print("🚀 Deploying homelab services...")

            # Change to project directory
            os.chdir(self.project_root)

            # Run docker compose up
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                capture_output=True,
                text=True,
                check=True,
            )

            return {
                "success": True,
                "message": "Homelab deployed successfully",
                "output": result.stdout,
            }

        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Deployment failed: {e.stderr}",
                "output": e.stdout,
            }
        except Exception as e:
            return {"success": False, "error": f"Deployment error: {str(e)}"}

    def create_backup(self) -> Dict:
        """Create backup of homelab data"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"homelab_backup_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_name

            console.print(f"📦 Creating backup: {backup_name}")

            # Create backup of appdata directory
            subprocess.run(
                [
                    "tar",
                    "-czf",
                    str(backup_path),
                    "-C",
                    str(self.project_root),
                    "appdata",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            return {
                "success": True,
                "backup_path": str(backup_path),
                "message": f"Backup created: {backup_name}",
            }

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Backup failed: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": f"Backup error: {str(e)}"}

    def restore_backup(self, backup_path: str) -> Dict:
        """Restore homelab from backup"""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                return {
                    "success": False,
                    "error": f"Backup file not found: {backup_path}",
                }

            console.print(f"🔄 Restoring from backup: {backup_file.name}")

            # Stop services first
            subprocess.run(
                ["docker", "compose", "down"], capture_output=True, text=True
            )

            # Restore backup
            subprocess.run(
                ["tar", "-xzf", str(backup_file), "-C", str(self.project_root)],
                capture_output=True,
                text=True,
                check=True,
            )

            # Restart services
            subprocess.run(
                ["docker", "compose", "up", "-d"], capture_output=True, text=True
            )

            return {"success": True, "message": "Backup restored successfully"}

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Restore failed: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": f"Restore error: {str(e)}"}

    def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """Get logs for a specific service"""
        try:
            result = subprocess.run(
                ["docker", "compose", "logs", "--tail", str(lines), service_name],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"Error getting logs: {e.stderr}"
        except Exception as e:
            return f"Logs error: {str(e)}"

    def restart_service(self, service_name: str) -> Dict:
        """Restart a specific service"""
        try:
            console.print(f"🔄 Restarting {service_name}...")

            subprocess.run(
                ["docker", "compose", "restart", service_name],
                capture_output=True,
                text=True,
                check=True,
            )

            return {
                "success": True,
                "message": f"{service_name} restarted successfully",
            }

        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Restart failed for {service_name}: {e.stderr}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Restart error for {service_name}: {str(e)}",
            }
