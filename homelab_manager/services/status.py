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
        """Get status of all homelab containers.

        Failure modes are kept distinct (#214): a Docker-daemon/list() failure
        returns an empty list + a user-visible error (so callers don't mistake it
        for "no containers"), while a per-container processing error skips only
        that container — one bad container can't silently truncate the rest and
        make a partial result look complete.
        """
        if self.docker_client is None:
            console.print(
                "Error getting container status. Docker daemon is unreachable."
            )
            return []

        try:
            all_containers = self.docker_client.containers.list(all=True)
        except Exception as e:
            # M1 hardening: do NOT echo exception details — Docker SDK errors
            # can include auth tokens, env values, or socket paths in stderr.
            logger.debug("containers.list() failed", exc_info=True)
            console.print(
                "Error getting container status. Check Docker connectivity "
                f"(error type: {type(e).__name__})."
            )
            return []

        containers = []
        for container in all_containers:
            try:
                # Try to match container to a known service
                service = self.registry.get_service_by_container(container.name)
                image = container.image.tags[0] if container.image.tags else "unknown"

                # Registry is the source of truth — only registered services are
                # reported. (A prior "unknown container" branch guarded on
                # `_is_homelab_container`, which was the same registry lookup as
                # `service` above and so could never fire — dead code, removed.)
                if service:
                    containers.append(
                        {
                            "name": container.name,
                            "service_name": service.name,
                            "category": service.category,
                            "status": container.status,
                            "port": service.port,
                            "health": self._check_container_health(container.name),
                            "image": image,
                            "sensitive": service.sensitive,
                        }
                    )
            except Exception:
                # One unreadable container must not drop the rest of the list.
                logger.debug("skipping container that failed to process", exc_info=True)
                continue

        return containers

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

    def _validate_service_name(self, service_name: str) -> tuple[bool, str]:
        """Validate service_name is in the registry.

        Returns (is_valid, error_msg). If registry is None, skips validation.
        """
        if self.registry is None:
            return True, ""
        known = {s.id for s in self.registry.services.values()} | {
            s.container_name for s in self.registry.services.values()
        }
        if service_name not in known:
            return (
                False,
                f"unknown service {service_name!r}. Known services: {sorted(known)}",
            )
        return True, ""

    def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """Get logs for a specific service.

        R1 Phase D: thin wrapper over ComposeCLI.logs(). H6 allowlist + M1
        stderr scrub live in clients.compose_cli — see audit-deep notes there.
        """
        is_valid, error_msg = self._validate_service_name(service_name)
        if not is_valid:
            return error_msg
        return self._compose.logs(service_name, lines=lines)
