#!/usr/bin/env python3
"""
Deployment Service
Handles Docker Compose deployment and service restart operations
"""

from pathlib import Path
from typing import Dict, Optional

from rich.console import Console

from ..clients.compose_cli import ComposeCLI
from ..models.service import ServiceRegistry

console = Console()


class DeploymentManager:
    """Manages deployment and service restart operations"""

    def __init__(
        self,
        compose_cli: Optional[ComposeCLI] = None,
        registry: Optional[ServiceRegistry] = None,
    ):
        self.project_root = Path(__file__).parent.parent.parent
        self._cli = compose_cli or ComposeCLI()
        self.registry = registry or ServiceRegistry()

    def deploy(self) -> Dict:
        """Deploy homelab services"""
        console.print("🚀 Deploying homelab services...")
        result = self._cli.run_result(
            ["up", "-d"],
            cwd=self.project_root,
            context="deployment failed",
        )
        if result["success"]:
            return {"success": True, "message": "Homelab deployed successfully"}
        return {"success": False, "error": result["error"]}

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

    def _resolve_service_id(self, service_name: str) -> str:
        """`docker compose restart` targets the compose service id, not the
        container_name. If a container_name was passed, map it to its service id
        (cubic #6: accepting container_names let un-restartable targets through)."""
        if self.registry is None:
            return service_name
        for s in self.registry.services.values():
            if s.container_name == service_name and s.id != service_name:
                return s.id
        return service_name

    def restart_service(self, service_name: str) -> Dict:
        """Restart a specific service"""
        is_valid, error_msg = self._validate_service_name(service_name)
        if not is_valid:
            return {"success": False, "error": error_msg}

        service_id = self._resolve_service_id(service_name)
        console.print(f"🔄 Restarting {service_id}...")
        result = self._cli.run_result(
            ["restart", service_id],
            cwd=self.project_root,
            context=f"restart '{service_id}' failed",
        )
        if result["success"]:
            return {
                "success": True,
                "message": f"{service_id} restarted successfully",
            }
        return {"success": False, "error": result["error"]}
