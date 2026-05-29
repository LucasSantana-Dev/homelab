#!/usr/bin/env python3
"""
Deployment Service
Handles Docker Compose deployment and service restart operations
"""

from pathlib import Path
from typing import Dict, Optional

from rich.console import Console

from ..clients.compose_cli import ComposeCLI

console = Console()


class DeploymentManager:
    """Manages deployment and service restart operations"""

    def __init__(self, compose_cli: Optional[ComposeCLI] = None):
        self.project_root = Path(__file__).parent.parent.parent
        self._cli = compose_cli or ComposeCLI()

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

    def restart_service(self, service_name: str) -> Dict:
        """Restart a specific service"""
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
