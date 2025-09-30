#!/usr/bin/env python3
"""
Homelab Configuration Manager
Environment variable loading and validation
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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
            "CF_API_TOKEN": r"^[a-zA-Z0-9_-]+$",
            "CF_TUNNEL_ID": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            "PIHOLE_WEB_PASSWORD": r"^.{8,}$",
            "PIHOLE_LOCAL_IPV4": r"^([0-9]{1,3}\.){3}[0-9]{1,3}$",
            "GRAFANA_PASSWORD": r"^.{8,}$",
            "HOMEASSISTANT_KEY": r"^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$",
            "LUKBOT_SENTRY_DSN": r"^https://[a-zA-Z0-9]+@[a-zA-Z0-9.-]+/[0-9]+$",
            "LUKBOT_SENTRY_ORG_SLUG": r"^[a-zA-Z0-9-]+$",
            "LUKBOT_SENTRY_PROJECT_SLUG": r"^[a-zA-Z0-9-]+$",
            "LUKBOT_SENTRY_AUTH_TOKEN": r"^[a-zA-Z0-9_-]+$",
            "WUD_DISCORD_WEBHOOK_URL": r"^https://discord\.com/api/webhooks/[0-9]+/[a-zA-Z0-9_-]+$",
            "WUD_SMTP_PASS": r"^.{8,}$",
        }

        # Optional variables
        self.optional_vars = {
            "WUD_SMTP_HOST": r"^([a-zA-Z0-9.-]+)$",
            "WUD_SMTP_PORT": r"^[0-9]+$",
            "WUD_SMTP_USER": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$|^[a-zA-Z0-9_.-]+$",
            "WUD_SMTP_FROM": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "WUD_SMTP_TO": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "MEDIA_PATH": r"^/.*",
            "USER_HOME": r"^/.*",
        }

    def load_environment(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars: Dict[str, str] = {}

        if not self.env_file.exists():
            console.print("❌ .env file not found", style="red")
            console.print(
                f"Please create {self.env_file} with your configuration", style="yellow"
            )
            return env_vars

        try:
            with open(self.env_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Check for valid variable assignment
                    if "=" not in line:
                        console.print(
                            f"⚠️ Invalid line {line_num}: {line}", style="yellow"
                        )
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    env_vars[key] = value
                    os.environ[key] = value

            console.print("✅ Environment variables loaded successfully", style="green")
            return env_vars

        except Exception as e:
            console.print(f"❌ Error loading environment: {e}", style="red")
            return env_vars

    def validate_environment(self) -> Tuple[bool, List[str]]:
        """Validate all environment variables"""
        console.print(Panel.fit("🔍 Validating Environment Variables", style="blue"))

        errors = []
        all_valid = True

        # Load environment first
        env_vars = self.load_environment()

        # Check required variables
        console.print("🔍 Checking required variables...", style="blue")
        for var_name, pattern in self.required_vars.items():
            value = env_vars.get(var_name, "")

            if not value:
                console.print(f"❌ {var_name} is not set", style="red")
                errors.append(f"{var_name} is not set")
                all_valid = False
            elif not re.match(pattern, value):
                console.print(
                    f"❌ {var_name} has invalid format: '{value}'", style="red"
                )
                errors.append(f"{var_name} has invalid format")
                all_valid = False
            else:
                console.print(f"✅ {var_name} is valid", style="green")

        # Check optional variables
        console.print("\n🔍 Checking optional variables...", style="blue")
        for var_name, pattern in self.optional_vars.items():
            value = env_vars.get(var_name, "")

            if not value:
                console.print(f"⚠️ {var_name} is not set (optional)", style="yellow")
            elif not re.match(pattern, value):
                console.print(
                    f"❌ {var_name} has invalid format: '{value}'", style="red"
                )
                errors.append(f"{var_name} has invalid format")
                all_valid = False
            else:
                console.print(f"✅ {var_name} is valid", style="green")

        # Security checks
        console.print("\n🔒 Security validation...", style="blue")
        self._security_checks(env_vars, errors)

        # Summary
        console.print("\n📊 Validation Summary", style="blue")
        if all_valid:
            console.print("✅ All environment variables are valid!", style="green")
            console.print("🚀 Ready to deploy homelab infrastructure", style="green")
        else:
            console.print(f"❌ {len(errors)} validation errors found", style="red")
            for error in errors:
                console.print(f"  - {error}", style="red")

        return all_valid, errors

    def _security_checks(self, env_vars: Dict[str, str], errors: List[str]):
        """Perform security-specific validation"""
        # Check Cloudflare token format
        cf_token = env_vars.get("CF_API_TOKEN", "")
        if cf_token and not re.match(r"^[a-zA-Z0-9_-]{36,48}$", cf_token):
            console.print(
                "⚠️ Cloudflare API token format looks suspicious", style="yellow"
            )

        # Check password strength
        passwords = ["PIHOLE_WEB_PASSWORD", "GRAFANA_PASSWORD", "WUD_SMTP_PASS"]
        for pwd_var in passwords:
            password = env_vars.get(pwd_var, "")
            if password and len(password) < 8:
                errors.append(f"{pwd_var} should be at least 8 characters")
                console.print(f"❌ {pwd_var} is too short", style="red")

        # Check for common weak passwords
        weak_passwords = ["password", "123456", "admin", "test"]
        for pwd_var in passwords:
            password = env_vars.get(pwd_var, "").lower()
            if password in weak_passwords:
                errors.append(f"{pwd_var} is too weak")
                console.print(f"❌ {pwd_var} is too weak", style="red")

    def create_env_example(self):
        """Create .env.example file from current .env"""
        if not self.env_file.exists():
            console.print("❌ .env file not found", style="red")
            return False

        try:
            with open(self.env_file, "r") as f:
                content = f.read()

            # Replace actual values with placeholders
            example_content = content
            for var_name in self.required_vars.keys():
                example_content = re.sub(
                    rf"^{var_name}=.*$",
                    f"{var_name}=your_{var_name.lower()}_here",
                    example_content,
                    flags=re.MULTILINE,
                )

            # Write example file
            with open(self.env_example, "w") as f:
                f.write(example_content)

            console.print(f"✅ Created {self.env_example}", style="green")
            return True

        except Exception as e:
            console.print(f"❌ Error creating example file: {e}", style="red")
            return False

    def show_config_summary(self):
        """Show configuration summary"""
        console.print(Panel.fit("📋 Configuration Summary", style="blue"))

        env_vars = self.load_environment()

        # Create summary table
        summary_table = Table(show_header=True, header_style="bold blue")
        summary_table.add_column("Variable", style="cyan")
        summary_table.add_column("Value", style="green")
        summary_table.add_column("Status", style="yellow")

        # Show required variables (masked)
        for var_name in self.required_vars.keys():
            value = env_vars.get(var_name, "")
            if value:
                # Mask sensitive values
                if "PASSWORD" in var_name or "TOKEN" in var_name or "KEY" in var_name:
                    masked_value = (
                        value[:4] + "*" * (len(value) - 4)
                        if len(value) > 4
                        else "*" * len(value)
                    )
                else:
                    masked_value = value
                status = "✅ Set"
            else:
                masked_value = "Not set"
                status = "❌ Missing"

            summary_table.add_row(var_name, masked_value, status)

        console.print(summary_table)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Homelab Configuration Manager")
    parser.add_argument(
        "action",
        choices=["load", "validate", "summary", "create-example"],
        help="Action to perform",
    )

    args = parser.parse_args()

    config = HomelabConfig()

    if args.action == "load":
        config.load_environment()
    elif args.action == "validate":
        config.validate_environment()
    elif args.action == "summary":
        config.show_config_summary()
    elif args.action == "create-example":
        config.create_env_example()


if __name__ == "__main__":
    main()
