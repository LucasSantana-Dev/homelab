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
        """Get service URLs based on configuration"""
        env_vars = self.load_env()
        tailscale_ip = env_vars.get("TAILSCALE_IP", "127.0.0.1")
        domain = env_vars.get("DOMAIN", "localhost")

        return {
            "homepage": "http://localhost:3000",
            "stremio": "http://localhost:8080",
            "homeassistant": "http://localhost:8123",
            "portainer": "http://localhost:9000",
            "pihole": "http://localhost:8054",
            "grafana": "http://localhost:3002",
            "uptime-kuma": "http://localhost:3001",
            "whats-up-docker": "http://localhost:3003",
            "tailscale_homepage": f"http://{tailscale_ip}:3000",
            "tailscale_stremio": f"http://{tailscale_ip}:8080",
            "tailscale_homeassistant": f"http://{tailscale_ip}:8123",
            "tailscale_portainer": f"http://{tailscale_ip}:9000",
            "tailscale_pihole": f"http://{tailscale_ip}:8054",
            "tailscale_grafana": f"http://{tailscale_ip}:3002",
            "tailscale_uptime-kuma": f"http://{tailscale_ip}:3001",
            "tailscale_whats-up-docker": f"http://{tailscale_ip}:3003",
            "public_homepage": f"https://{domain}",
            "public_homeassistant": f"https://homeassistant.{domain}",
            "public_portainer": f"https://portainer.{domain}",
            "public_pihole": f"https://pihole.{domain}",
            "public_stremio": f"https://stremio.{domain}",
            "public_grafana": f"https://grafana.{domain}",
            "public_uptime": f"https://uptime.{domain}",
            "public_docker": f"https://docker.{domain}",
        }
