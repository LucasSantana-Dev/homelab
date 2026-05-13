#!/usr/bin/env python3
"""
Deployment Service
Handles Docker Compose deployment and service restart operations
"""

import subprocess
from pathlib import Path
from typing import Dict

from rich.console import Console

from ..utils.command_sequence import CommandSequence, Step

console = Console()


class DeploymentManager:
    """Manages deployment and service restart operations"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent

    def deploy(self) -> Dict:
        """Deploy homelab services"""
        console.print("🚀 Deploying homelab services...")
        result = CommandSequence(
            [Step(["docker", "compose", "up", "-d"], "docker compose up")],
            cwd=self.project_root,
        ).run()
        if result["success"]:
            result["message"] = "Homelab deployed successfully"
        return result

    def restart_service(self, service_name: str) -> Dict:
        """Restart a specific service"""
        console.print(f"🔄 Restarting {service_name}...")
        result = CommandSequence(
            [
                Step(
                    ["docker", "compose", "restart", service_name],
                    f"restart {service_name}",
                )
            ],
            cwd=self.project_root,
        ).run()
        if result["success"]:
            result["message"] = f"{service_name} restarted successfully"
        return result
