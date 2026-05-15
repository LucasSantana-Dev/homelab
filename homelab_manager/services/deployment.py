#!/usr/bin/env python3
"""
Deployment Service
Handles Docker Compose deployment and service restart operations
"""

import subprocess
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
        try:
            self._cli.run(["up", "-d"], cwd=self.project_root)
            return {"success": True, "message": "Homelab deployed successfully"}
        except subprocess.CalledProcessError as exc:
            return {"success": False, "error": exc.stderr if exc.stderr else str(exc)}

    def restart_service(self, service_name: str) -> Dict:
        """Restart a specific service"""
        console.print(f"🔄 Restarting {service_name}...")
        try:
            self._cli.run(["restart", service_name], cwd=self.project_root)
            return {
                "success": True,
                "message": f"{service_name} restarted successfully",
            }
        except subprocess.CalledProcessError as exc:
            return {"success": False, "error": exc.stderr if exc.stderr else str(exc)}
