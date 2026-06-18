#!/usr/bin/env python3
"""
Backup Service
Handles backup and restore operations for homelab data
"""

import time
from pathlib import Path
from typing import Dict

from rich.console import Console

from ..utils.command_sequence import CommandSequence, Step

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
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"homelab_backup_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_name

        console.print(f"📦 Creating backup: {backup_name}")

        result = CommandSequence(
            [
                Step(
                    [
                        "tar",
                        "-czf",
                        str(backup_path),
                        "-C",
                        str(self.project_root),
                        "appdata",
                    ],
                    "create archive",
                )
            ]
        ).run()
        if result["success"]:
            result["backup_path"] = str(backup_path)
            result["message"] = f"Backup created: {backup_name}"
        return result

    def restore_backup(self, backup_path: str) -> Dict:
        """Restore homelab from backup"""
        # Resolve paths to prevent traversal attacks
        backup_file = Path(backup_path).resolve()
        backup_dir_resolved = Path(self.backup_dir).resolve()

        # Verify backup path is within backup directory
        try:
            backup_file.relative_to(backup_dir_resolved)
        except ValueError:
            return {
                "success": False,
                "error": "Backup path must be within the backup directory",
            }

        # Verify file exists
        if not backup_file.exists():
            return {"success": False, "error": f"Backup file not found: {backup_path}"}

        # Verify it's a regular file, not a directory or symlink
        if not backup_file.is_file():
            return {"success": False, "error": "Backup path must be a regular file"}

        console.print(f"🔄 Restoring from backup: {backup_file.name}")

        result = CommandSequence(
            [
                Step(["docker", "compose", "down"], "stop services"),
                Step(
                    ["tar", "-xzf", str(backup_file), "-C", str(self.project_root)],
                    "extract backup",
                ),
                Step(["docker", "compose", "up", "-d"], "restart services"),
            ],
            cwd=self.project_root,
        ).run()
        if result["success"]:
            result["message"] = "Backup restored successfully"
        return result
