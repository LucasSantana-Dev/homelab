#!/usr/bin/env python3
"""Management and deployment commands for homelab CLI"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from ..core.config import HomelabConfig
from ..models.service import ServiceRegistry
from ..services.containers import ContainerManager
from ..services.updates import UpdateManager

console = Console()


def register_management_commands(
    app: typer.Typer,
    config_manager: HomelabConfig,
    container_manager: ContainerManager,
    update_manager: UpdateManager,
    registry: ServiceRegistry,
):
    """Register all management and deployment commands with the Typer app"""

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
    def restore(backup_path: str = typer.Argument(..., help="Path to backup file")):
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

    @app.command()
    def services():
        """List all registered services"""
        console.print(Panel.fit("📦 Registered Services", style="bold blue"))

        # Group by category
        categories = registry.categories
        for cat_id, category in categories.items():
            console.print(f"\n[bold]{category.description}[/bold]")
            cat_services = registry.get_services_by_category(cat_id)
            for svc in cat_services:
                port_info = f":{svc.port}" if svc.port else ""
                sensitive_badge = " [red](sensitive)[/red]" if svc.sensitive else ""
                console.print(f"  • {svc.name}{port_info}{sensitive_badge}")
