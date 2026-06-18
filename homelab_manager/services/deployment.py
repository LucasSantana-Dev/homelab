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

    def restart_service(self, service_name: str) -> Dict:
        """Restart a specific service"""
        is_valid, error_msg = self._validate_service_name(service_name)
        if not is_valid:
            return {"success": False, "error": error_msg}

        console.print(f"🔄 Restarting {service_name}...")
        result = self._cli.run_result(
            ["restart", service_name],
            cwd=self.project_root,
            context=f"restart '{service_name}' failed",
        )
        if result["success"]:
            return {
                "success": True,
                "message": f"{service_name} restarted successfully",
            }
        return {"success": False, "error": result["error"]}
