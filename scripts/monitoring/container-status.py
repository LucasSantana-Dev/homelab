#!/usr/bin/env python3
"""
Container Status CLI
Simple wrapper for container management
"""

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
    """Main function for container status"""
    manager = ContainerManager()

    if not manager.check_docker_running():
        sys.exit(1)

    manager.display_container_status()
    manager.show_disk_usage()

    # Show recent logs for running containers
    containers = manager.get_container_status()
    for container in containers:
        if container["running"]:
            manager.show_recent_logs(container["name"], lines=2)


if __name__ == "__main__":
    main()
