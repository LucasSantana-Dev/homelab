#!/usr/bin/env python3
"""
Homelab Manager CLI
Main command-line interface for homelab management
"""

import argparse
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel

# Add the homelab_manager to the path
sys.path.insert(0, str(Path(__file__).parent))

from automation import HomelabAutomation
from config import HomelabConfig
from health import HomelabHealthMonitor
from updates import HomelabUpdateManager

# Initialize console
console = Console()


class HomelabCLI:
    """Main CLI interface for homelab management"""

    def __init__(self):
        self.automation = HomelabAutomation()
        self.health = HomelabHealthMonitor()
        self.updates = HomelabUpdateManager()
        self.config = HomelabConfig()

    def deploy(self):
        """Deploy homelab services"""
        return self.automation.deploy()

    def update(self):
        """Update homelab services"""
        return self.automation.update()

    def backup(self):
        """Create backup"""
        return self.automation.backup()

    def restore(self, backup_path: str):
        """Restore from backup"""
        return self.automation.restore(backup_path)

    def health_check(self):
        """Run health check"""
        self.health.run_health_check()

    def status(self):
        """Show quick status"""
        self.health.quick_status()

    def monitor(self, interval: int = 60):
        """Start continuous monitoring"""
        self.health.monitor_continuous(interval)

    def check_updates(self):
        """Check for updates"""
        self.updates.check_all_updates()

    def update_all(self):
        """Update all services"""
        return self.updates.update_all_services()

    def update_service(self, service_name: str):
        """Update specific service"""
        return self.updates.update_service(service_name)

    def versions(self):
        """Show service versions"""
        self.updates.show_versions()

    def cleanup(self):
        """Clean up unused resources"""
        self.automation.cleanup()

    def validate_config(self):
        """Validate configuration"""
        return self.config.validate_environment()

    def config_summary(self):
        """Show configuration summary"""
        self.config.show_config_summary()

    def setup_cron(self):
        """Setup automated tasks"""
        console.print(Panel.fit("⏰ Setting up Automated Tasks", style="blue"))

        homelab_dir = Path(__file__).parent.parent.parent
        script_path = homelab_dir / "scripts" / "homelab_manager" / "cli.py"

        # Create cron jobs
        cron_jobs = [
            f"0 2 * * * {script_path} backup >> {homelab_dir}/logs/backup.log 2>&1",
            f"0 3 * * 0 {script_path} update >> {homelab_dir}/logs/update.log 2>&1",
            f"0 4 * * * {script_path} cleanup >> {homelab_dir}/logs/cleanup.log 2>&1",
            f"0 5 * * * {script_path} update-check >> {homelab_dir}/logs/updates.log 2>&1",
        ]

        try:
            import subprocess

            # Get current crontab
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            current_cron = result.stdout if result.returncode == 0 else ""

            # Add new cron jobs
            new_cron = current_cron.rstrip()  # Remove trailing whitespace
            for job in cron_jobs:
                if job not in current_cron:
                    new_cron += f"\n{job}"

            # Ensure newline at end of file
            if new_cron and not new_cron.endswith("\n"):
                new_cron += "\n"

            # Update crontab
            subprocess.run(["crontab", "-"], input=new_cron, text=True, check=True)

            console.print("✅ Cron jobs configured successfully", style="green")
            console.print("📅 Daily backup at 2 AM", style="blue")
            console.print("📅 Weekly update check on Sunday at 3 AM", style="blue")
            console.print("📅 Daily cleanup at 4 AM", style="blue")
            console.print("📅 Daily update check at 5 AM", style="blue")

        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to setup cron jobs: {e}", style="red")
        except Exception as e:
            console.print(f"❌ Error setting up cron: {e}", style="red")


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Homelab Manager - Python-based homelab automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m homelab_manager deploy
  python -m homelab_manager update
  python -m homelab_manager backup
  python -m homelab_manager health-check
  python -m homelab_manager status
  python -m homelab_manager check-updates
  python -m homelab_manager setup-cron
        """,
    )

    parser.add_argument(
        "action",
        choices=[
            "deploy",
            "update",
            "backup",
            "restore",
            "health-check",
            "status",
            "monitor",
            "check-updates",
            "update-all",
            "update-service",
            "versions",
            "cleanup",
            "validate-config",
            "config-summary",
            "setup-cron",
        ],
        help="Action to perform",
    )

    parser.add_argument("--backup-path", help="Backup path for restore")
    parser.add_argument("--service", help="Service name for update-service")
    parser.add_argument(
        "--interval", type=int, default=60, help="Monitoring interval in seconds"
    )

    args = parser.parse_args()

    cli = HomelabCLI()

    # Show header
    console.print(Panel.fit("🏠 Homelab Manager", style="blue", box=box.DOUBLE))

    try:
        if args.action == "deploy":
            cli.deploy()
        elif args.action == "update":
            cli.update()
        elif args.action == "backup":
            cli.backup()
        elif args.action == "restore":
            if not args.backup_path:
                console.print(
                    "❌ Please specify --backup-path for restore", style="red"
                )
                sys.exit(1)
            cli.restore(args.backup_path)
        elif args.action == "health-check":
            cli.health_check()
        elif args.action == "status":
            cli.status()
        elif args.action == "monitor":
            cli.monitor(args.interval)
        elif args.action == "check-updates":
            cli.check_updates()
        elif args.action == "update-all":
            cli.update_all()
        elif args.action == "update-service":
            if not args.service:
                console.print(
                    "❌ Please specify --service for update-service", style="red"
                )
                sys.exit(1)
            cli.update_service(args.service)
        elif args.action == "versions":
            cli.versions()
        elif args.action == "cleanup":
            cli.cleanup()
        elif args.action == "validate-config":
            cli.validate_config()
        elif args.action == "config-summary":
            cli.config_summary()
        elif args.action == "setup-cron":
            cli.setup_cron()

    except KeyboardInterrupt:
        console.print("\n🛑 Operation cancelled by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        sys.exit(1)


if __name__ == "__main__":
    main()
