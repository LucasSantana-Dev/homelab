#!/usr/bin/env python3
"""
Update Management Service
Manage updates for homelab services
"""

import logging
import subprocess
from typing import Dict, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..clients.compose_cli import ComposeCLI
from ..core.errors import scrub_subprocess_error
from ..models.service import ServiceRegistry

console = Console()
logger = logging.getLogger(__name__)


class UpdateManager:
    """Manage updates for homelab services"""

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        self.registry = registry or ServiceRegistry()
        # R1 Phase E: docker-compose invocations centralised in ComposeCLI;
        # M1 stderr-scrubbing is now baked into every error path.
        self._compose = ComposeCLI(registry=self.registry)

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

    # -- public API ----------------------------------------------------------

    def check_updates(self) -> Dict:
        """Check for available updates"""
        console.print("🔍 Checking for updates...")
        try:
            result = self._compose.run(["images"])
            return {
                "success": True,
                "message": "Update check completed",
                "output": result.stdout,
            }
        except subprocess.CalledProcessError as exc:
            logger.debug("docker compose images failed", exc_info=True)
            return {
                "success": False,
                "error": scrub_subprocess_error(exc, context="Update check failed"),
            }
        except Exception as exc:
            logger.debug("check_updates unexpected error", exc_info=True)
            return {
                "success": False,
                "error": f"Update check error (type: {type(exc).__name__}).",
            }

    def update_all(self) -> Dict:
        """Update all homelab services"""
        console.print("🔄 Updating all services...")
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Pulling latest images...", total=None)
                self._compose.run(["pull"])
                progress.update(task, description="Images pulled successfully")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Restarting services...", total=None)
                self._compose.run(["up", "-d"])
                progress.update(task, description="Services restarted successfully")

            return {"success": True, "message": "All services updated successfully"}

        except subprocess.CalledProcessError as exc:
            logger.debug("update_all failed", exc_info=True)
            return {
                "success": False,
                "error": scrub_subprocess_error(exc, context="Update failed"),
            }
        except Exception as exc:
            logger.debug("update_all unexpected error", exc_info=True)
            return {
                "success": False,
                "error": f"Update error (type: {type(exc).__name__}).",
            }

    def update_service(self, service_name: str) -> Dict:
        """Update a specific service"""
        is_valid, error_msg = self._validate_service_name(service_name)
        if not is_valid:
            return {"success": False, "error": error_msg}

        console.print(f"🔄 Updating {service_name}...")
        try:
            self._compose.run(["pull", service_name])
            self._compose.run(["up", "-d", service_name])
            return {"success": True, "message": f"{service_name} updated successfully"}
        except subprocess.CalledProcessError as exc:
            logger.debug("update_service failed", exc_info=True)
            return {
                "success": False,
                "error": scrub_subprocess_error(
                    exc, context=f"Update failed for {service_name}"
                ),
            }
        except Exception as exc:
            logger.debug("update_service unexpected error", exc_info=True)
            return {
                "success": False,
                "error": (
                    f"Update error for {service_name} (type: {type(exc).__name__})."
                ),
            }

    def get_update_status(self) -> Dict:
        """Get status of available updates"""
        try:
            result = self._compose.run(["images"])
        except subprocess.CalledProcessError as exc:
            logger.debug("get_update_status images failed", exc_info=True)
            return {
                "success": False,
                "error": scrub_subprocess_error(
                    exc, context="Failed to get update status"
                ),
            }
        except Exception as exc:
            logger.debug("get_update_status unexpected error", exc_info=True)
            return {
                "success": False,
                "error": f"Update status error (type: {type(exc).__name__}).",
            }

        services = []
        for line in result.stdout.strip().split("\n")[1:]:  # skip header
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            container_name, image, tag = parts[0], parts[1], parts[2]
            service = self.registry.get_service_by_container(container_name)
            services.append(
                {
                    "name": service.name if service else container_name,
                    "container": container_name,
                    "image": image,
                    "tag": tag,
                    "status": "up_to_date",
                }
            )

        return {
            "success": True,
            "services": services,
            "total_services": len(services),
        }

    def get_all_service_names(self):
        """Get all service names from registry"""
        return [s.id for s in self.registry.services.values()]
