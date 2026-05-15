#!/usr/bin/env python3
"""
Status Service
Handles container status checks, health monitoring, and log retrieval
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from ..clients.compose_cli import ComposeCLI
from ..clients.docker_client import get_docker_client
from ..models.service import ServiceRegistry

console = Console()
logger = logging.getLogger(__name__)


class StatusManager:
    """Manages container status, health checks, and logs"""

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        # R1 Phase C: docker.from_env() centralised in clients.docker_client.
        # Behaviour change vs pre-R1: factory returns None on daemon failure
        # rather than raising — callers already guard with `if self.docker_client`.
        self.docker_client = get_docker_client()
        self.project_root = Path(__file__).parent.parent.parent
        self.registry = registry or ServiceRegistry()
        # R1 Phase D: compose CLI logic lives in clients.compose_cli; the
        # allowlist (H6) and stderr scrub (M1) are baked into ComposeCLI.
        self._compose = ComposeCLI(registry=self.registry)

    def get_container_status(self) -> List[Dict]:
        """Get status of all homelab containers"""
        containers = []

        try:
            assert self.docker_client is not None
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
            # M1 hardening: do NOT echo exception details — Docker SDK errors
            # can include auth tokens, env values, or socket paths in stderr.
            # Log full detail at DEBUG only; user sees a generic message.
            logger.debug("get_container_status failed", exc_info=True)
            console.print(
                "Error getting container status. Check Docker connectivity "
                f"(error type: {type(e).__name__})."
            )

        return containers

    def _is_homelab_container(self, container_name: str) -> bool:
        """Check if a container belongs to the homelab stack via the service registry"""
        return self.registry.get_service_by_container(container_name) is not None

    def _check_container_health(self, container_name: str) -> str:
        """Check if a container is healthy"""
        try:
            assert self.docker_client is not None
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
        """Get logs for a specific service.

        R1 Phase D: thin wrapper over ComposeCLI.logs(). H6 allowlist + M1
        stderr scrub live in clients.compose_cli — see audit-deep notes there.
        """
        return self._compose.logs(service_name, lines=lines)
