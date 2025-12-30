#!/usr/bin/env python3
"""
Container Management Service
Handles Docker container operations for homelab services
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import docker
from rich.console import Console

from ..models.service import ServiceRegistry

# Initialize console
console = Console()


class ContainerManager:
    """Modern container management for homelab services"""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.project_root = Path(__file__).parent.parent.parent
        self.backup_dir = self.project_root / "backups"
        self.appdata_dir = self.project_root / "appdata"

        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)

        # Load service registry
        self.registry = ServiceRegistry()

    def get_container_status(self) -> List[Dict]:
        """Get status of all homelab containers"""
        containers = []

        try:
            for container in self.docker_client.containers.list(all=True):
                # Try to match container to a known service
                service = self.registry.get_service_by_container(container.name)

                if service:
                    containers.append(
                        {
                            "name": container.name,
                            "service_name": service.name,
                            "category": service.category,
                            "status": container.status,
                            "port": service.port,
                            "health": self._check_container_health(container.name),
                            "image": (
                                container.image.tags[0]
                                if container.image.tags
                                else "unknown"
                            ),
                            "sensitive": service.sensitive,
                        }
                    )
                else:
                    # Include containers that might be part of homelab but not in registry
                    if self._is_homelab_container(container.name):
                        containers.append(
                            {
                                "name": container.name,
                                "service_name": container.name,
                                "category": "unknown",
                                "status": container.status,
                                "port": None,
                                "health": self._check_container_health(container.name),
                                "image": (
                                    container.image.tags[0]
                                    if container.image.tags
                                    else "unknown"
                                ),
                                "sensitive": False,
                            }
                        )
        except Exception as e:
            console.print(f"Error getting container status: {e}")

        return containers

    def _is_homelab_container(self, container_name: str) -> bool:
        """Check if a container belongs to the homelab stack"""
        # Known container name patterns
        homelab_patterns = [
            "nginx",
            "homepage",
            "portainer",
            "grafana",
            "prometheus",
            "pihole",
            "homeassistant",
            "jellyfin",
            "stremio",
            "uptime",
            "whats-up",
            "netdata",
            "loki",
            "promtail",
            "alertmanager",
            "cadvisor",
            "node-exporter",
            "vaultwarden",
            "authentik",
            "paperless",
            "nextcloud",
            "n8n",
            "filebrowser",
            "blackbox",
        ]
        return any(pattern in container_name.lower() for pattern in homelab_patterns)

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

    def get_service_info(self, service_id: str) -> Optional[Dict]:
        """Get detailed information about a service from the registry"""
        service = self.registry.get_service(service_id)
        if not service:
            return None

        return {
            "id": service.id,
            "name": service.name,
            "category": service.category,
            "container_name": service.container_name,
            "port": service.port,
            "health_url": service.health_url,
            "sensitive": service.sensitive,
            "description": service.description,
        }

    def get_services_by_category(self, category: str) -> List[Dict]:
        """Get all services in a category"""
        services = self.registry.get_services_by_category(category)
        return [
            {
                "id": s.id,
                "name": s.name,
                "container_name": s.container_name,
                "port": s.port,
                "sensitive": s.sensitive,
            }
            for s in services
        ]
