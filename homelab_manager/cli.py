#!/usr/bin/env python3
"""
Homelab Manager CLI
Modern command-line interface for homelab management
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import HomelabConfig
from .container_manager import ContainerManager
from .health import HomelabHealthMonitor
from .updates import HomelabUpdateManager

# Initialize console
console = Console()

# Create Typer app
app = typer.Typer(
    name="homelab",
    help="Modern homelab management CLI",
    add_completion=False,
    rich_markup_mode="rich"
)

# Global instances
config_manager = HomelabConfig()
container_manager = ContainerManager()
health_monitor = HomelabHealthMonitor()
update_manager = HomelabUpdateManager()


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
        health_icon = "🟢" if container.get("health") == "healthy" else "🔴"

        table.add_row(
            container["name"],
            f"{status_icon} {container['status']}",
            str(container.get("port", "N/A")),
            health_icon
        )

    console.print(table)


@app.command()
def deploy():
    """Deploy homelab services"""
    console.print(Panel.fit("🚀 Deploying Homelab", style="bold green"))

    try:
        result = container_manager.deploy()
        if result["success"]:
            console.print("✅ Homelab deployed successfully!")
        else:
            console.print(f"❌ Deployment failed: {result['error']}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Deployment error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def update():
    """Update homelab services"""
    console.print(Panel.fit("🔄 Updating Homelab", style="bold yellow"))

    try:
        result = update_manager.update_all()
        if result["success"]:
            console.print("✅ Homelab updated successfully!")
        else:
            console.print(f"❌ Update failed: {result['error']}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Update error: {str(e)}")
        raise typer.Exit(1)


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
            response_time = status.get('response_time')
            if response_time is not None:
                response_time = f"{response_time:.2f}ms"
            else:
                response_time = "N/A"

            table.add_row(
                service,
                f"{status_icon} {'Healthy' if status['healthy'] else 'Unhealthy'}",
                response_time,
                status.get("last_check", "Never")
            )

        console.print(table)

    except Exception as e:
        console.print(f"❌ Health check error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def backup():
    """Create homelab backup"""
    console.print(Panel.fit("💾 Creating Backup", style="bold blue"))

    try:
        result = container_manager.create_backup()
        if result["success"]:
            console.print(f"✅ Backup created: {result['backup_path']}")
        else:
            console.print(f"❌ Backup failed: {result['error']}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Backup error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def restore(
    backup_path: str = typer.Argument(..., help="Path to backup file")
):
    """Restore homelab from backup"""
    console.print(Panel.fit("🔄 Restoring from Backup", style="bold yellow"))

    try:
        result = container_manager.restore_backup(backup_path)
        if result["success"]:
            console.print("✅ Homelab restored successfully!")
        else:
            console.print(f"❌ Restore failed: {result['error']}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Restore error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def logs(
    service: Optional[str] = typer.Argument(None, help="Service name to get logs for")
):
    """Show service logs"""
    console.print(Panel.fit("📋 Service Logs", style="bold cyan"))

    try:
        if service:
            logs = container_manager.get_service_logs(service)
            console.print(f"Logs for {service}:")
            console.print(logs)
        else:
            # Show all services
            services = container_manager.get_container_status()
            console.print("Available services:")
            for container in services:
                console.print(f"  - {container['name']}")
            console.print("\nUse: homelab logs <service-name>")

    except Exception as e:
        console.print(f"❌ Logs error: {str(e)}")
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
                f"{status_icon} {'Valid' if info['valid'] else 'Invalid'}"
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
        urls = config_manager.get_service_urls()

        # Create URLs table
        table = Table(title="Service Access URLs")
        table.add_column("Service", style="cyan")
        table.add_column("Localhost", style="green")
        table.add_column("Tailscale", style="yellow")
        table.add_column("Public", style="magenta")

        services = [
            "homepage", "stremio", "homeassistant", "portainer",
            "pihole", "grafana", "uptime-kuma", "whats-up-docker"
        ]

        for service in services:
            localhost_url = urls.get(service, "N/A")
            tailscale_url = urls.get(f"tailscale_{service}", "N/A")
            public_url = urls.get(f"public_{service}", "N/A")

            table.add_row(
                service.title(),
                localhost_url,
                tailscale_url,
                public_url
            )

        console.print(table)

    except Exception as e:
        console.print(f"❌ URLs error: {str(e)}")
        raise typer.Exit(1)


@app.command()
def restart(
    service: Optional[str] = typer.Argument(None, help="Service name to restart")
):
    """Restart services"""
    console.print(Panel.fit("🔄 Restarting Services", style="bold yellow"))

    try:
        if service:
            result = container_manager.restart_service(service)
            if result["success"]:
                console.print(f"✅ {service} restarted successfully!")
            else:
                console.print(f"❌ Restart failed: {result['error']}")
                raise typer.Exit(1)
        else:
            # Restart all services
            console.print("🔄 Restarting all services...")
            result = container_manager.deploy()
            if result["success"]:
                console.print("✅ All services restarted successfully!")
            else:
                console.print(f"❌ Restart failed: {result['error']}")
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"❌ Restart error: {str(e)}")
        raise typer.Exit(1)


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main()
