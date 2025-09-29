"""
CLI Interface - Unified command-line interface for homelab management
"""

import click
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from pathlib import Path
import yaml

from .core import HomelabManager

console = Console()

@click.group()
@click.option('--config', '-c', default='config/homelab.yml', help='Configuration file path')
@click.pass_context
def cli(ctx, config):
    """🏠 Luk's Homelab Manager - Python-based automation system"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['manager'] = HomelabManager(config)

@cli.command()
@click.pass_context
def status(ctx):
    """Show homelab status"""
    manager = ctx.obj['manager']
    manager.status()

@cli.command()
@click.pass_context
def deploy(ctx):
    """Deploy the complete homelab stack"""
    manager = ctx.obj['manager']
    manager.deploy_all()

@cli.command()
@click.pass_context
def update(ctx):
    """Update all services"""
    manager = ctx.obj['manager']
    manager.update_all()

@cli.command()
@click.pass_context
def backup(ctx):
    """Backup all services"""
    manager = ctx.obj['manager']
    manager.backup_all()

@cli.command()
@click.pass_context
def monitor(ctx):
    """Start continuous monitoring"""
    manager = ctx.obj['manager']
    asyncio.run(manager.monitor_services())

@cli.command()
@click.pass_context
def test(ctx):
    """Test all services health (replaces test-services.sh)"""
    manager = ctx.obj['manager']
    manager.test_all_services()

@cli.command()
@click.pass_context
def verify(ctx):
    """Verify environment setup (replaces setup-verification.sh)"""
    manager = ctx.obj['manager']
    manager.verify_environment()

@cli.group()
def cloudflare():
    """Cloudflare management commands"""
    pass

@cloudflare.command()
@click.pass_context
def setup_tunnel(ctx):
    """Setup Cloudflare tunnel (replaces setup-cloudflare-tunnel.sh)"""
    manager = ctx.obj['manager']
    manager.cloudflare.setup_tunnel()

@cloudflare.command()
@click.pass_context
def configure_dns(ctx):
    """Configure DNS records (replaces configure-cloudflare-dns.sh)"""
    manager = ctx.obj['manager']
    manager.cloudflare.configure_dns_records()

@cloudflare.command()
@click.pass_context
def configure_tunnel_dns(ctx):
    """Configure tunnel DNS records (replaces configure-tunnel-dns.sh)"""
    manager = ctx.obj['manager']
    manager.cloudflare.configure_tunnel_dns()

@cloudflare.command()
@click.pass_context
def update_tunnel_dns(ctx):
    """Update tunnel DNS records (replaces update-tunnel-dns.sh)"""
    manager = ctx.obj['manager']
    manager.cloudflare.update_tunnel_dns()

@cli.group()
def docker():
    """Docker management commands"""
    pass

@docker.command()
@click.pass_context
def status(ctx):
    """Show Docker container status"""
    manager = ctx.obj['manager']
    stats = manager.docker.get_container_stats()

    table = Table(title="🐳 Docker Container Status")
    table.add_column("Container", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Image", style="blue")
    table.add_column("Created", style="yellow")

    for name, info in stats.items():
        table.add_row(
            name,
            info.get('status', 'Unknown'),
            info.get('image', 'Unknown'),
            info.get('created', 'Unknown')[:19] if info.get('created') else 'Unknown'
        )

    console.print(table)

@docker.command()
@click.argument('service')
@click.pass_context
def restart(ctx, service):
    """Restart a specific service"""
    manager = ctx.obj['manager']
    manager.docker.restart_service(service)

@docker.command()
@click.pass_context
def cleanup(ctx):
    """Clean up Docker resources"""
    manager = ctx.obj['manager']
    manager.docker.cleanup_containers()

@docker.command()
@click.argument('service')
@click.option('--lines', '-n', default=50, help='Number of log lines to show')
@click.pass_context
def logs(ctx, service, lines):
    """Show logs for a service"""
    manager = ctx.obj['manager']
    logs = manager.docker.get_service_logs(service, lines)
    console.print(Panel(logs, title=f"📋 {service} Logs"))

@cli.group()
def cloudflare():
    """Cloudflare management commands"""
    pass

@cloudflare.command()
@click.pass_context
def setup(ctx):
    """Setup Cloudflare DNS and tunnel"""
    manager = ctx.obj['manager']
    manager.cloudflare.setup_dns_records()
    manager.cloudflare.setup_tunnel()

@cloudflare.command()
@click.pass_context
def dns(ctx):
    """List DNS records"""
    manager = ctx.obj['manager']
    manager.cloudflare.list_dns_records()

@cloudflare.command()
@click.argument('name')
@click.argument('content')
@click.option('--type', default='A', help='Record type')
@click.option('--proxied/--no-proxied', default=False, help='Proxied status')
@click.pass_context
def add_record(ctx, name, content, type, proxied):
    """Add a DNS record"""
    manager = ctx.obj['manager']
    manager.cloudflare.create_dns_record(name, content, type, proxied)

@cloudflare.command()
@click.argument('name')
@click.option('--type', default='A', help='Record type')
@click.pass_context
def delete_record(ctx, name, type):
    """Delete a DNS record"""
    manager = ctx.obj['manager']
    manager.cloudflare.delete_dns_record(name, type)

@cli.group()
def health():
    """Health monitoring commands"""
    pass

@health.command()
@click.pass_context
def check(ctx):
    """Check health of all services"""
    manager = ctx.obj['manager']
    asyncio.run(manager.monitor.check_all_services())
    manager.monitor.show_health_status()

@health.command()
@click.option('--service', help='Specific service to check')
@click.option('--hours', default=24, help='Hours of history to show')
@click.pass_context
def history(ctx, service, hours):
    """Show health check history"""
    manager = ctx.obj['manager']
    manager.monitor.show_health_history(service, hours)

@health.command()
@click.argument('service')
@click.option('--hours', default=24, help='Hours of metrics to show')
@click.pass_context
def metrics(ctx, service, hours):
    """Show metrics for a service"""
    manager = ctx.obj['manager']
    metrics = manager.monitor.get_service_metrics(service, hours)

    table = Table(title=f"📊 {service} Metrics ({hours}h)")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for key, value in metrics.items():
        table.add_row(key.replace('_', ' ').title(), str(value))

    console.print(table)

@health.command()
@click.argument('filename')
@click.pass_context
def export(ctx, filename):
    """Export health data to JSON"""
    manager = ctx.obj['manager']
    manager.monitor.export_health_data(filename)

@cli.command()
@click.pass_context
def init(ctx):
    """Initialize homelab configuration"""
    config_path = Path(ctx.obj['config_path'])

    if config_path.exists():
        console.print(f"[yellow]⚠️  Configuration already exists at {config_path}[/yellow]")
        if not click.confirm("Overwrite existing configuration?"):
            return

    # Create default configuration
    manager = HomelabManager(str(config_path))
    console.print(f"[green]✅ Configuration initialized at {config_path}[/green]")
    console.print("[blue]💡 Edit the configuration file and run 'homelab deploy' to start[/blue]")

@cli.command()
@click.pass_context
def config(ctx):
    """Show current configuration"""
    manager = ctx.obj['manager']

    table = Table(title="⚙️  Homelab Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Domain", manager.config.domain)
    table.add_row("Tailscale IP", manager.config.tailscale_ip)
    table.add_row("Cloudflare Token", "***" if manager.config.cloudflare_token else "Not Set")
    table.add_row("Backup Path", manager.config.backup_path)
    table.add_row("Log Level", manager.config.log_level)
    table.add_row("Services", str(len(manager.config.services)))

    console.print(table)

if __name__ == '__main__':
    cli()
