#!/usr/bin/env python3
"""
Status Service
Handles container status checks, health monitoring, and log retrieval
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import docker
from rich.console import Console

from ..models.service import ServiceRegistry

console = Console()


class StatusManager:
    """Manages container status, health checks, and logs"""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.project_root = Path(__file__).parent.parent.parent
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
