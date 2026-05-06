#!/usr/bin/env python3
"""
Backup Service
Handles backup and restore operations for homelab data
"""

import subprocess
import time
from pathlib import Path
from typing import Dict

from rich.console import Console

console = Console()


class BackupManager:
    """Manages backup and restore operations"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.backup_dir = self.project_root / "backups"
        self.appdata_dir = self.project_root / "appdata"

        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self) -> Dict:
        """Create backup of homelab data"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"homelab_backup_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_name

            console.print(f"📦 Creating backup: {backup_name}")

            # Create backup of appdata directory
            subprocess.run(
                [
                    "tar",
                    "-czf",
                    str(backup_path),
                    "-C",
                    str(self.project_root),
                    "appdata",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            return {
                "success": True,
                "backup_path": str(backup_path),
                "message": f"Backup created: {backup_name}",
            }

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Backup failed: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": f"Backup error: {str(e)}"}

    def restore_backup(self, backup_path: str) -> Dict:
        """Restore homelab from backup"""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                return {
                    "success": False,
                    "error": f"Backup file not found: {backup_path}",
                }

            console.print(f"🔄 Restoring from backup: {backup_file.name}")

            # Stop services first
            subprocess.run(
                ["docker", "compose", "down"], capture_output=True, text=True
            )

            # Restore backup
            subprocess.run(
                ["tar", "-xzf", str(backup_file), "-C", str(self.project_root)],
                capture_output=True,
                text=True,
                check=True,
            )

            # Restart services
            subprocess.run(
                ["docker", "compose", "up", "-d"], capture_output=True, text=True
            )

            return {"success": True, "message": "Backup restored successfully"}

        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Restore failed: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": f"Restore error: {str(e)}"}
