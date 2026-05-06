#!/usr/bin/env python3
"""Status and diagnostic commands for homelab CLI"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.config import HomelabConfig
from ..models.service import ServiceRegistry
from ..services.containers import ContainerManager
from ..services.health import HealthMonitor

console = Console()


def register_status_commands(
    app: typer.Typer,
    config_manager: HomelabConfig,
    container_manager: ContainerManager,
    health_monitor: HealthMonitor,
    registry: ServiceRegistry,
):
    """Register all status and diagnostic commands with the Typer app"""

    @app.command()
    def status():
        """Show homelab status and service information"""
        console.print(Panel.fit("🏠 Homelab Status", style="bold blue"))

        # Get container status
        containers = container_manager.get_container_status()

        # Create status table
        table = Table(title="Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Port", style="yellow")
        table.add_column("Health", style="magenta")

        for container in containers:
            status_icon = "✅" if container["status"] == "running" else "❌"
            health_icon = (
                "🟢" if container.get("health") in {"healthy", "running"} else "🔴"
            )

            table.add_row(
                container["name"],
                f"{status_icon} {container['status']}",
                str(container.get("port", "N/A")),
                health_icon,
            )

        console.print(table)

    @app.command()
    def health():
        """Check homelab health"""
        console.print(Panel.fit("🏥 Health Check", style="bold red"))

        try:
            health_status = health_monitor.check_all_services()

            # Create health table
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

            console.print(table)

        except Exception as e:
            console.print(f"❌ Health check error: {str(e)}")
            raise typer.Exit(1)

    @app.command()
    def config():
        """Show configuration information"""
        console.print(Panel.fit("⚙️  Configuration", style="bold magenta"))

        try:
            config_info = config_manager.get_config_summary()

            # Create config table
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

            console.print(table)

        except Exception as e:
            console.print(f"❌ Config error: {str(e)}")
            raise typer.Exit(1)

    @app.command()
    def urls():
        """Show service URLs and access methods"""
        console.print(Panel.fit("🔗 Service URLs", style="bold blue"))

        try:
            # Get services from config (which uses registry)
            services = config_manager.get_services_for_display()

            # Create URLs table
            table = Table(title="Service Access URLs")
            table.add_column("Service", style="cyan")
            table.add_column("Category", style="white")
            table.add_column("Localhost", style="green")
            table.add_column("Tailscale", style="yellow")
            table.add_column("Public", style="magenta")

            for svc in services:
                table.add_row(
                    svc["name"],
                    svc["category"],
                    svc.get("localhost", "N/A"),
                    svc.get("tailscale", "N/A"),
                    svc.get("public", "N/A"),
                )

            console.print(table)

        except Exception as e:
            console.print(f"❌ URLs error: {str(e)}")
            raise typer.Exit(1)

    @app.command()
    def logs(
        service: Optional[str] = typer.Argument(
            None, help="Service name to get logs for"
        )
    ):
        """Show service logs"""
        console.print(Panel.fit("📋 Service Logs", style="bold cyan"))

        try:
            if service:
                logs = container_manager.get_service_logs(service)
                console.print(f"Logs for {service}:")
                console.print(logs)
            else:
                # Show all services from registry
                console.print("Available services:")
                for svc in registry.get_services_with_ports():
                    console.print(f"  - {svc.id} ({svc.name})")
                console.print("\nUse: homelab logs <service-name>")

        except Exception as e:
            console.print(f"❌ Logs error: {str(e)}")
            raise typer.Exit(1)
