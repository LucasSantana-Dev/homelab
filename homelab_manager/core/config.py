#!/usr/bin/env python3
"""
Homelab Configuration Manager
Environment variable loading and validation
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from ..models.service import ServiceRegistry

# Initialize console
console = Console()


class HomelabConfig:
    """Configuration management for homelab"""

    def __init__(self, homelab_dir: Optional[str] = None):
        self.homelab_dir = (
            Path(homelab_dir) if homelab_dir else Path(__file__).parent.parent.parent
        )
        self.env_file = self.homelab_dir / ".env"
        self.env_example = self.homelab_dir / ".env.example"

        # Load service registry
        self.registry = ServiceRegistry()

        # Required variables with validation patterns
        self.required_vars = {
            "DOMAIN": r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "TIMEZONE": r"^[A-Za-z_/]+$",
            "PUID": r"^[0-9]+$",
            "PGID": r"^[0-9]+$",
            "TAILSCALE_IP": r"^([0-9]{1,3}\.){3}[0-9]{1,3}$",
        }

        # Optional variables
        self.optional_vars = {
            "CF_API_TOKEN": r"^[a-zA-Z0-9_-]+$",
            "CF_TUNNEL_ID": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            "PIHOLE_WEB_PASSWORD": r"^.{8,}$",
            "GRAFANA_PASSWORD": r"^.{8,}$",
            "HOMEASSISTANT_KEY": r"^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$",
        }

    def load_env(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars = {}

        if self.env_file.exists():
            with open(self.env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Handle variable substitution syntax
                        if value.startswith("${") and value.endswith("}"):
                            # Extract the variable name and default value
                            var_content = value[2:-1]  # Remove ${ and }
                            if ":-" in var_content:
                                var_name, default_value = var_content.split(":-", 1)
                                env_vars[key] = os.environ.get(var_name, default_value)
                            else:
                                env_vars[key] = os.environ.get(var_content, value)
                        else:
                            env_vars[key] = value

        return env_vars

    def validate_config(self) -> Dict[str, bool]:
        """Validate configuration variables"""
        env_vars = self.load_env()
        validation_results = {}

        # Check required variables
        for var_name, pattern in self.required_vars.items():
            value = env_vars.get(var_name, "")
            if not value or value.startswith("your_") or value == "your-domain.com":
                validation_results[var_name] = False
            else:
                validation_results[var_name] = bool(re.match(pattern, value))

        # Check optional variables
        for var_name, pattern in self.optional_vars.items():
            value = env_vars.get(var_name, "")
            if (
                not value
                or value.startswith("your_")
                or value == "your_cloudflare_api_token_here"
            ):
                validation_results[var_name] = False
            else:
                validation_results[var_name] = bool(re.match(pattern, value))

        return validation_results

    def get_config_summary(self) -> Dict[str, Dict]:
        """Get configuration summary"""
        env_vars = self.load_env()
        validation_results = self.validate_config()

        summary = {}

        # Required variables
        for var_name in self.required_vars.keys():
            value = env_vars.get(var_name, "Not set")
            if value.startswith("your_") or value == "your-domain.com":
                value = "Not configured"

            summary[var_name] = {
                "value": value,
                "valid": validation_results.get(var_name, False),
                "required": True,
            }

        # Optional variables
        for var_name in self.optional_vars.keys():
            value = env_vars.get(var_name, "Not set")
            if value.startswith("your_") or value == "your_cloudflare_api_token_here":
                value = "Not configured"

            summary[var_name] = {
                "value": value,
                "valid": validation_results.get(var_name, False),
                "required": False,
            }

        return summary

    def get_missing_config(self) -> List[str]:
        """Get list of missing or invalid configuration"""
        validation_results = self.validate_config()
        missing = []

        for var_name, is_valid in validation_results.items():
            if not is_valid:
                missing.append(var_name)

        return missing

    def get_service_urls(self) -> Dict[str, str]:
        """Get service URLs based on configuration and service registry"""
        env_vars = self.load_env()
        tailscale_ip = env_vars.get("TAILSCALE_IP", "127.0.0.1")
        domain = env_vars.get("DOMAIN", "localhost")

        urls = {}

        # Generate URLs from service registry
        for service_id, service in self.registry.services.items():
            if service.has_port and service.port:
                # Localhost URL
                urls[service_id] = f"http://localhost:{service.port}"

                # Tailscale URL
                if not service.localhost_only:
                    tailscale_url = service.get_tailscale_url(tailscale_ip)
                    if tailscale_url:
                        urls[f"tailscale_{service_id}"] = tailscale_url

                    # Public URL
                    public_url = service.get_public_url(domain)
                    if public_url:
                        urls[f"public_{service_id}"] = public_url

        return urls

    def get_services_for_display(self) -> List[Dict]:
        """Get services formatted for display in CLI"""
        env_vars = self.load_env()
        tailscale_ip = env_vars.get("TAILSCALE_IP", "127.0.0.1")
        domain = env_vars.get("DOMAIN", "localhost")

        services = []
        for service in self.registry.get_services_with_ports():
            if service.localhost_only:
                continue

            services.append(
                {
                    "name": service.name,
                    "id": service.id,
                    "category": service.category,
                    "localhost": f"http://localhost:{service.port}",
                    "tailscale": service.get_tailscale_url(tailscale_ip),
                    "public": service.get_public_url(domain),
                    "sensitive": service.sensitive,
                }
            )

        return services
