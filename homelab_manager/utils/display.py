#!/usr/bin/env python3
"""
Display Utilities
Rich display helpers for homelab management
"""

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Initialize console
console = Console()


class DisplayManager:
    """Manage rich display output for homelab CLI"""

    @staticmethod
    def create_status_table(containers: List[Dict]) -> Table:
        """Create a status table for containers"""
        table = Table(title="Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Port", style="yellow")
        table.add_column("Health", style="magenta")

        for container in containers:
            status_icon = "✅" if container["status"] == "running" else "❌"
            health_icon = "🟢" if container.get("health") == "healthy" else "🔴"

            table.add_row(
                container["name"],
                f"{status_icon} {container['status']}",
                str(container.get("port", "N/A")),
                health_icon,
            )

        return table

    @staticmethod
    def create_health_table(health_status: Dict[str, Dict]) -> Table:
        """Create a health status table"""
        table = Table(title="Health Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Response Time", style="yellow")
        table.add_column("Last Check", style="magenta")

        for service, status in health_status.items():
            status_icon = "✅" if status["healthy"] else "❌"
            response_time = status.get("response_time")
            if response_time is not None:
                response_time = f"{response_time:.2f}ms"
            else:
                response_time = "N/A"

            table.add_row(
                service,
                f"{status_icon} {'Healthy' if status['healthy'] else 'Unhealthy'}",
                response_time,
                status.get("last_check", "Never"),
            )

        return table

    @staticmethod
    def create_config_table(config_info: Dict[str, Dict]) -> Table:
        """Create a configuration table"""
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Status", style="yellow")

        for setting, info in config_info.items():
            status_icon = "✅" if info["valid"] else "❌"

            table.add_row(
                setting,
                info["value"],
                f"{status_icon} {'Valid' if info['valid'] else 'Invalid'}",
            )

        return table

    @staticmethod
    def create_urls_table(urls: Dict[str, str]) -> Table:
        """Create a service URLs table"""
        table = Table(title="Service Access URLs")
        table.add_column("Service", style="cyan")
        table.add_column("Localhost", style="green")
        table.add_column("Tailscale", style="yellow")
        table.add_column("Public", style="magenta")

        services = [
            "homepage",
            "stremio",
            "homeassistant",
            "portainer",
            "pihole",
            "grafana",
            "uptime-kuma",
            "whats-up-docker",
        ]

        for service in services:
            localhost_url = urls.get(service, "N/A")
            tailscale_url = urls.get(f"tailscale_{service}", "N/A")
            public_url = urls.get(f"public_{service}", "N/A")

            table.add_row(service.title(), localhost_url, tailscale_url, public_url)

        return table

    @staticmethod
    def show_success(message: str):
        """Show success message"""
        console.print(f"✅ {message}")

    @staticmethod
    def show_error(message: str):
        """Show error message"""
        console.print(f"❌ {message}")

    @staticmethod
    def show_info(message: str):
        """Show info message"""
        console.print(f"ℹ️  {message}")

    @staticmethod
    def show_warning(message: str):
        """Show warning message"""
        console.print(f"⚠️  {message}")

    @staticmethod
    def create_progress_spinner(description: str) -> Progress:
        """Create a progress spinner"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        )
