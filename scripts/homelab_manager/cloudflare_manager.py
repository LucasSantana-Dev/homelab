"""
Cloudflare Management - Python replacement for Cloudflare DNS and tunnel operations
"""

import requests
import json
import time
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
import subprocess
from pathlib import Path

class CloudflareManager:
    """Manages Cloudflare DNS and tunnel operations"""

    def __init__(self, config):
        self.config = config
        self.console = Console()
        self.api_token = config.cloudflare_token
        self.domain = config.domain
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        self.zone_id = None
        self._get_zone_id()

    def _get_zone_id(self):
        """Get Cloudflare zone ID for the domain"""
        try:
            response = requests.get(
                f"{self.base_url}/zones",
                headers=self.headers,
                params={"name": self.domain}
            )
            response.raise_for_status()

            zones = response.json()["result"]
            if zones:
                self.zone_id = zones[0]["id"]
                self.console.print(f"[green]✅ Found zone ID: {self.zone_id}[/green]")
            else:
                self.console.print(f"[red]❌ Zone not found for {self.domain}[/red]")
                raise Exception(f"Zone not found for {self.domain}")

        except requests.RequestException as e:
            self.console.print(f"[red]❌ Failed to get zone ID: {e}[/red]")
            raise

    def create_dns_record(self, name: str, content: str, record_type: str = "A", proxied: bool = False) -> bool:
        """Create a DNS record"""
        try:
            data = {
                "type": record_type,
                "name": name,
                "content": content,
                "proxied": proxied,
                "ttl": 1 if proxied else 300
            }

            response = requests.post(
                f"{self.base_url}/zones/{self.zone_id}/dns_records",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()

            result = response.json()
            if result["success"]:
                self.console.print(f"[green]✅ Created DNS record: {name} -> {content}[/green]")
                return True
            else:
                self.console.print(f"[red]❌ Failed to create DNS record: {result.get('errors', [{}])[0].get('message', 'Unknown error')}[/red]")
                return False

        except requests.RequestException as e:
            self.console.print(f"[red]❌ DNS record creation failed: {e}[/red]")
            return False

    def update_dns_record(self, name: str, content: str, record_type: str = "A", proxied: bool = False) -> bool:
        """Update an existing DNS record"""
        try:
            # First, get the record ID
            record_id = self._get_record_id(name, record_type)
            if not record_id:
                self.console.print(f"[yellow]⚠️  Record not found, creating new one: {name}[/yellow]")
                return self.create_dns_record(name, content, record_type, proxied)

            data = {
                "type": record_type,
                "name": name,
                "content": content,
                "proxied": proxied,
                "ttl": 1 if proxied else 300
            }

            response = requests.put(
                f"{self.base_url}/zones/{self.zone_id}/dns_records/{record_id}",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()

            result = response.json()
            if result["success"]:
                self.console.print(f"[green]✅ Updated DNS record: {name} -> {content}[/green]")
                return True
            else:
                self.console.print(f"[red]❌ Failed to update DNS record: {result.get('errors', [{}])[0].get('message', 'Unknown error')}[/red]")
                return False

        except requests.RequestException as e:
            self.console.print(f"[red]❌ DNS record update failed: {e}[/red]")
            return False

    def _get_record_id(self, name: str, record_type: str) -> Optional[str]:
        """Get record ID for a DNS record"""
        try:
            response = requests.get(
                f"{self.base_url}/zones/{self.zone_id}/dns_records",
                headers=self.headers,
                params={"name": f"{name}.{self.domain}", "type": record_type}
            )
            response.raise_for_status()

            records = response.json()["result"]
            if records:
                return records[0]["id"]
            return None

        except requests.RequestException:
            return None

    def setup_dns_records(self):
        """Setup all DNS records for homelab services"""
        self.console.print("[blue]🌐 Setting up Cloudflare DNS records...[/blue]")

        # Create main domain record
        self.create_dns_record("@", self.config.tailscale_ip, "A", False)
        self.create_dns_record("www", self.config.tailscale_ip, "A", False)

        # Create subdomain records
        for service in self.config.services:
            if service.enabled and service.subdomain:
                self.create_dns_record(
                    service.subdomain,
                    self.config.tailscale_ip,
                    "A",
                    False
                )

        self.console.print("[green]✅ DNS records setup complete[/green]")

    def update_dns_records(self):
        """Update all DNS records"""
        self.console.print("[blue]🔄 Updating Cloudflare DNS records...[/blue]")

        # Update main domain record
        self.update_dns_record("@", self.config.tailscale_ip, "A", False)
        self.update_dns_record("www", self.config.tailscale_ip, "A", False)

        # Update subdomain records
        for service in self.config.services:
            if service.enabled and service.subdomain:
                self.update_dns_record(
                    service.subdomain,
                    self.config.tailscale_ip,
                    "A",
                    False
                )

        self.console.print("[green]✅ DNS records updated[/green]")

    def setup_tunnel(self):
        """Setup Cloudflare tunnel"""
        self.console.print("[blue]🚇 Setting up Cloudflare tunnel...[/blue]")

        # Check if cloudflared is available
        if not self._check_cloudflared():
            self.console.print("[red]❌ cloudflared not found. Please install it first.[/red]")
            return False

        # Create tunnel if it doesn't exist
        tunnel_id = self._get_or_create_tunnel()
        if not tunnel_id:
            self.console.print("[red]❌ Failed to create/get tunnel[/red]")
            return False

        # Configure tunnel
        self._configure_tunnel(tunnel_id)

        # Update DNS records to point to tunnel
        self._update_tunnel_dns(tunnel_id)

        self.console.print("[green]✅ Cloudflare tunnel setup complete[/green]")
        return True

    def _check_cloudflared(self) -> bool:
        """Check if cloudflared is available"""
        try:
            result = subprocess.run(
                ["cloudflared", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _get_or_create_tunnel(self) -> Optional[str]:
        """Get existing tunnel or create new one"""
        try:
            # Try to get existing tunnel
            result = subprocess.run(
                ["cloudflared", "tunnel", "list"],
                capture_output=True,
                text=True,
                check=True
            )

            # Look for homelab tunnel
            for line in result.stdout.split('\n'):
                if 'homelab' in line.lower():
                    tunnel_id = line.split()[1]  # Assuming ID is second column
                    self.console.print(f"[green]✅ Found existing tunnel: {tunnel_id}[/green]")
                    return tunnel_id

            # Create new tunnel
            self.console.print("[blue]Creating new tunnel...[/blue]")
            result = subprocess.run(
                ["cloudflared", "tunnel", "create", "homelab"],
                capture_output=True,
                text=True,
                check=True
            )

            # Extract tunnel ID from output
            for line in result.stdout.split('\n'):
                if 'tunnel id' in line.lower():
                    tunnel_id = line.split()[-1]
                    self.console.print(f"[green]✅ Created tunnel: {tunnel_id}[/green]")
                    return tunnel_id

            return None

        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]❌ Tunnel operation failed: {e.stderr}[/red]")
            return None

    def _configure_tunnel(self, tunnel_id: str):
        """Configure tunnel with ingress rules"""
        config_path = Path.home() / ".cloudflared" / "config.yml"
        config_path.parent.mkdir(exist_ok=True)

        # Generate tunnel configuration
        config = {
            "tunnel": "homelab",
            "credentials-file": f"/home/luk-server/.cloudflared/{tunnel_id}.json",
            "ingress": []
        }

        # Add ingress rules for all services
        for service in self.config.services:
            if service.enabled:
                hostname = f"{service.subdomain}.{self.domain}" if service.subdomain else self.domain
                config["ingress"].append({
                    "hostname": hostname,
                    "service": f"http://{service.container_name}:{service.port}"
                })

        # Add catch-all rule
        config["ingress"].append({
            "service": "http_status:404"
        })

        # Write configuration
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        self.console.print(f"[green]✅ Tunnel configuration written to {config_path}[/green]")

    def _update_tunnel_dns(self, tunnel_id: str):
        """Update DNS records to point to tunnel"""
        self.console.print("[blue]🔄 Updating DNS records for tunnel...[/blue]")

        # Update main domain
        self.update_dns_record("@", f"{tunnel_id}.cfargotunnel.com", "CNAME", True)
        self.update_dns_record("www", f"{tunnel_id}.cfargotunnel.com", "CNAME", True)

        # Update subdomains
        for service in self.config.services:
            if service.enabled and service.subdomain:
                self.update_dns_record(
                    service.subdomain,
                    f"{tunnel_id}.cfargotunnel.com",
                    "CNAME",
                    True
                )

        self.console.print("[green]✅ DNS records updated for tunnel[/green]")

    def list_dns_records(self):
        """List all DNS records"""
        try:
            response = requests.get(
                f"{self.base_url}/zones/{self.zone_id}/dns_records",
                headers=self.headers
            )
            response.raise_for_status()

            records = response.json()["result"]

            table = Table(title="Cloudflare DNS Records")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Content", style="blue")
            table.add_column("Proxied", style="yellow")

            for record in records:
                table.add_row(
                    record["name"],
                    record["type"],
                    record["content"],
                    "Yes" if record["proxied"] else "No"
                )

            self.console.print(table)

        except requests.RequestException as e:
            self.console.print(f"[red]❌ Failed to list DNS records: {e}[/red]")

    def delete_dns_record(self, name: str, record_type: str = "A"):
        """Delete a DNS record"""
        try:
            record_id = self._get_record_id(name, record_type)
            if not record_id:
                self.console.print(f"[yellow]⚠️  Record not found: {name}[/yellow]")
                return False

            response = requests.delete(
                f"{self.base_url}/zones/{self.zone_id}/dns_records/{record_id}",
                headers=self.headers
            )
            response.raise_for_status()

            result = response.json()
            if result["success"]:
                self.console.print(f"[green]✅ Deleted DNS record: {name}[/green]")
                return True
            else:
                self.console.print(f"[red]❌ Failed to delete DNS record[/red]")
                return False

        except requests.RequestException as e:
            self.console.print(f"[red]❌ DNS record deletion failed: {e}[/red]")
            return False
