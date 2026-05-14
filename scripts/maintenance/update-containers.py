#!/usr/bin/env python3
"""
Container Update CLI
Simple wrapper for container updates
"""

import argparse
import os
import sys
from pathlib import Path

# M2 hardening: replaced `exec(open(activate_script).read())` venv activation
# with site/sys path manipulation. exec() of a file from disk was a code-exec
# risk if the venv was ever tampered with; the same effect (importing from
# the venv's site-packages) is achieved with no exec call.
venv_path = Path(__file__).parent.parent / "venv"
if venv_path.exists():
    venv_python = venv_path / "bin" / "python"
    if venv_python.exists() and sys.executable != str(venv_python):
        # If invoked outside the venv, re-exec into it (no shell, list-form).
        # nosec B606: target is a fixed path derived from __file__, not user input;
        # we explicitly pass argv as a list to avoid any shell interpretation.
        os.execv(  # nosec B606
            str(venv_python), [str(venv_python), __file__, *sys.argv[1:]]
        )
    # If already running under the venv interpreter, its site-packages are
    # automatically on sys.path — nothing more to do.

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
