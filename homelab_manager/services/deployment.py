#!/usr/bin/env python3
"""
Deployment Service
Handles Docker Compose deployment and service restart operations
"""

import os
import subprocess
from pathlib import Path
from typing import Dict

from rich.console import Console

console = Console()


class DeploymentManager:
    """Manages deployment and service restart operations"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent

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
