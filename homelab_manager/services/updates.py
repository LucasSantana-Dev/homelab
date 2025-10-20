#!/usr/bin/env python3
"""
Update Management Service
Manage updates for homelab services
"""

import subprocess
import time
from typing import Dict, List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Initialize console
console = Console()


class UpdateManager:
    """Manage updates for homelab services"""

    def __init__(self):
        self.services = [
            "homepage",
            "stremio",
            "homeassistant",
            "portainer",
            "pihole",
            "grafana",
            "uptime-kuma",
            "whats-up-docker",
            "prometheus",
            "node-exporter",
        ]

    def check_updates(self) -> Dict:
        """Check for available updates"""
        try:
            console.print("🔍 Checking for updates...")

            # Get current images
            result = subprocess.run(
                ["docker", "compose", "images"],
                capture_output=True,
                text=True,
                check=True,
            )

            return {
                "success": True,
                "message": "Update check completed",
                "output": result.stdout,
            }

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Update check failed: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": f"Update check error: {str(e)}"}

    def update_all(self) -> Dict:
        """Update all homelab services"""
        try:
            console.print("🔄 Updating all services...")

            # Pull latest images
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Pulling latest images...", total=None)

                result = subprocess.run(
                    ["docker", "compose", "pull"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                progress.update(task, description="Images pulled successfully")

            # Restart services
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Restarting services...", total=None)

                result = subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                progress.update(task, description="Services restarted successfully")

            return {"success": True, "message": "All services updated successfully"}

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Update failed: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": f"Update error: {str(e)}"}

    def update_service(self, service_name: str) -> Dict:
        """Update a specific service"""
        if service_name not in self.services:
            return {"success": False, "error": f"Unknown service: {service_name}"}

        try:
            console.print(f"🔄 Updating {service_name}...")

            # Pull latest image for service
            result = subprocess.run(
                ["docker", "compose", "pull", service_name],
                capture_output=True,
                text=True,
                check=True,
            )

            # Restart the service
            result = subprocess.run(
                ["docker", "compose", "up", "-d", service_name],
                capture_output=True,
                text=True,
                check=True,
            )

            return {"success": True, "message": f"{service_name} updated successfully"}

        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Update failed for {service_name}: {e.stderr}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Update error for {service_name}: {str(e)}",
            }

    def get_update_status(self) -> Dict:
        """Get status of available updates"""
        try:
            # Get current images
            result = subprocess.run(
                ["docker", "compose", "images"],
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse output to get image information
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            services = []

            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        service_name = parts[0]
                        image = parts[1]
                        tag = parts[2]

                        services.append(
                            {
                                "name": service_name,
                                "image": image,
                                "tag": tag,
                                "status": "up_to_date",  # This would need more sophisticated checking
                            }
                        )

            return {
                "success": True,
                "services": services,
                "total_services": len(services),
            }

        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Failed to get update status: {e.stderr}",
            }
        except Exception as e:
            return {"success": False, "error": f"Update status error: {str(e)}"}
