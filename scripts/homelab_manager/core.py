"""
Core Homelab Manager - Main orchestration class
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

@dataclass
class Service:
    """Represents a homelab service"""
    name: str
    container_name: str
    port: int
    subdomain: str
    health_check: str
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)

@dataclass
class HomelabConfig:
    """Homelab configuration"""
    domain: str
    tailscale_ip: str
    cloudflare_token: str
    services: List[Service]
    backup_path: str
    log_level: str = "INFO"

class HomelabManager:
    """Main homelab management class"""

    def __init__(self, config_path: str = "config/homelab.yml"):
        self.console = Console()
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._setup_logging()

        # Initialize managers
        from .docker_manager import DockerManager
        from .cloudflare_manager import CloudflareManager
        from .monitor import HealthMonitor
        from .deploy import DeploymentManager

        self.docker = DockerManager(self.config)
        self.cloudflare = CloudflareManager(self.config)
        self.monitor = HealthMonitor(self.config)
        self.deploy = DeploymentManager(self.config)

    def _load_config(self) -> HomelabConfig:
        """Load configuration from YAML file and environment variables"""
        if not self.config_path.exists():
            self._create_default_config()

        with open(self.config_path) as f:
            data = yaml.safe_load(f)

        # Load from environment variables with fallback to config file
        domain = os.getenv("DOMAIN", data.get("domain", ""))
        tailscale_ip = os.getenv("TAILSCALE_IP", data.get("tailscale_ip", ""))
        cloudflare_token = os.getenv("CF_API_TOKEN", data.get("cloudflare_token", ""))

        services = [Service(**service) for service in data.get("services", [])]
        return HomelabConfig(
            domain=domain,
            tailscale_ip=tailscale_ip,
            cloudflare_token=cloudflare_token,
            services=services,
            backup_path=data.get("backup_path", "./backups"),
            log_level=data.get("log_level", "INFO")
        )

    def _create_default_config(self):
        """Create default configuration file"""
        default_config = {
            "domain": "",
            "tailscale_ip": "",
            "cloudflare_token": "",
            "backup_path": "./backups",
            "log_level": "INFO",
            "services": [
                {
                    "name": "homepage",
                    "container_name": "homepage",
                    "port": 3000,
                    "subdomain": "",
                    "health_check": "/",
                    "enabled": True,
                    "dependencies": []
                },
                {
                    "name": "stremio",
                    "container_name": "stremio-server",
                    "port": 8080,
                    "subdomain": "stremio",
                    "health_check": "/",
                    "enabled": True,
                    "dependencies": []
                },
                {
                    "name": "homeassistant",
                    "container_name": "homeassistant",
                    "port": 8123,
                    "subdomain": "homeassistant",
                    "health_check": "/",
                    "enabled": True,
                    "dependencies": []
                },
                {
                    "name": "grafana",
                    "container_name": "grafana",
                    "port": 3002,
                    "subdomain": "grafana",
                    "health_check": "/api/health",
                    "enabled": True,
                    "dependencies": []
                },
                {
                    "name": "portainer",
                    "container_name": "portainer",
                    "port": 9000,
                    "subdomain": "portainer",
                    "health_check": "/",
                    "enabled": True,
                    "dependencies": []
                },
                {
                    "name": "pihole",
                    "container_name": "pihole",
                    "port": 8054,
                    "subdomain": "pihole",
                    "health_check": "/admin",
                    "enabled": True,
                    "dependencies": []
                },
                {
                    "name": "prometheus",
                    "container_name": "prometheus",
                    "port": 9091,
                    "subdomain": "prometheus",
                    "health_check": "/",
                    "enabled": True,
                    "dependencies": []
                },
                {
                    "name": "node-exporter",
                    "container_name": "node-exporter",
                    "port": 9100,
                    "subdomain": "",
                    "health_check": "/metrics",
                    "enabled": True,
                    "dependencies": []
                }
            ]
        }

        self.config_path.parent.mkdir(exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)

        self.console.print(f"[green]Created default config at {self.config_path}[/green]")

    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('homelab.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def status(self):
        """Show homelab status"""
        table = Table(title="🏠 Luk's Homelab Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("URL", style="blue")
        table.add_column("Health", style="yellow")

        for service in self.config.services:
            if not service.enabled:
                continue

            status = self.docker.get_service_status(service.container_name)
            url = f"https://{service.subdomain}.{self.config.domain}" if service.subdomain else f"https://{self.config.domain}"
            health = self.monitor.check_service_health(service)

            table.add_row(
                service.name,
                status,
                url,
                health
            )

        self.console.print(table)

    def deploy_all(self):
        """Deploy all services"""
        self.console.print("[bold blue]🚀 Deploying Luk's Homelab[/bold blue]")

        # Start Docker services
        self.docker.start_all_services()

        # Configure Cloudflare
        self.cloudflare.setup_dns_records()
        self.cloudflare.setup_tunnel()

        # Verify deployment
        self.monitor.verify_deployment()

        self.console.print("[bold green]✅ Homelab deployment complete![/bold green]")

    def update_all(self):
        """Update all services"""
        self.console.print("[bold blue]🔄 Updating Luk's Homelab[/bold blue]")

        self.docker.update_all_services()
        self.cloudflare.update_dns_records()

        self.console.print("[bold green]✅ Homelab update complete![/bold green]")

    def backup_all(self):
        """Backup all services"""
        self.console.print("[bold blue]💾 Backing up Luk's Homelab[/bold blue]")

        backup_path = Path(self.config.backup_path)
        backup_path.mkdir(exist_ok=True)

        for service in self.config.services:
            if service.enabled:
                self.docker.backup_service(service, backup_path)

        self.console.print(f"[bold green]✅ Backup complete! Stored in {backup_path}[/bold green]")

    def monitor_services(self):
        """Start continuous monitoring"""
        self.console.print("[bold blue]📊 Starting homelab monitoring[/bold blue]")
        self.monitor.start_monitoring()

    def test_all_services(self):
        """Test all services health (replaces test-services.sh)"""
        self.console.print("[bold blue]🔍 Testing all homelab services[/bold blue]")
        self.monitor.test_all_services()

    def verify_environment(self):
        """Verify environment setup (replaces setup-verification.sh)"""
        self.console.print("[bold blue]🔧 Verifying environment setup[/bold blue]")
        self.monitor.verify_environment()
