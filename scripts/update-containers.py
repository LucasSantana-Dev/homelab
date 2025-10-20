#!/usr/bin/env python3
"""
Container Update CLI
Simple wrapper for container updates
"""

import argparse
import os
import sys
from pathlib import Path

# Activate virtual environment
venv_path = Path(__file__).parent.parent / "venv"
if venv_path.exists():
    activate_script = venv_path / "bin" / "activate_this.py"
    if activate_script.exists():
        exec(open(activate_script).read(), {"__file__": str(activate_script)})

# Add the homelab_manager to the path
sys.path.insert(0, str(Path(__file__).parent / "homelab_manager"))

from container_manager import ContainerManager


def main():
    """Main function for container updates"""
    parser = argparse.ArgumentParser(description="Update homelab containers")
    parser.add_argument(
        "container",
        nargs="?",
        choices=["homeassistant", "homepage", "grafana", "filebrowser", "all"],
        help="Container to update (or 'all' for all containers)",
    )
    parser.add_argument(
        "--check", "-c", action="store_true", help="Check for updates without updating"
    )

    args = parser.parse_args()

    manager = ContainerManager()

    if not manager.check_docker_running():
        sys.exit(1)

    if args.check:
        manager.display_container_status()
        manager.check_for_updates()
    elif args.container:
        if args.container == "all":
            console.print("🔄 Updating all containers...", style="blue")
            for container_name in manager.containers.keys():
                manager.update_container(container_name)
        else:
            manager.update_container(args.container)

        manager.cleanup_old_images()
        manager.display_container_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
