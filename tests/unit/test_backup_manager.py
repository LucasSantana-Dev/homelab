#!/usr/bin/env python3
"""
Unit tests for homelab_manager.services.backup_manager (audit-deep H7).

Covers create_backup happy/failure paths and restore_backup with
existence check + 3-step sequence. Heavy use of CommandSequence patching
to keep tests fast and side-effect-free.
"""

from unittest.mock import patch

import pytest

from homelab_manager.services.backup_manager import BackupManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    # Redirect project_root onto a temp dir to keep tests hermetic.
    monkeypatch.chdir(tmp_path)
    m = BackupManager()
    m.project_root = tmp_path
    m.backup_dir = tmp_path / "backups"
    m.appdata_dir = tmp_path / "appdata"
    m.backup_dir.mkdir(exist_ok=True)
    m.appdata_dir.mkdir(exist_ok=True)
    return m


class TestCreateBackup:
    def test_creates_backup_dir_on_init(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        m = BackupManager()
        # The constructor mkdir's backup_dir under the real project root.
        # Just verify the attribute exists; can't assert tmp_path content
        # because the real project_root is computed relative to module path.
        assert m.backup_dir.name == "backups"

    def test_success_attaches_backup_path_and_message(self, manager):
        with patch(
            "homelab_manager.services.backup_manager.CommandSequence"
        ) as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}
            result = manager.create_backup()
            assert result["success"] is True
            assert "backup_path" in result
            assert result["backup_path"].endswith(".tar.gz")
            assert "homelab_backup_" in result["backup_path"]
            assert "Backup created" in result["message"]

    def test_failure_omits_backup_path(self, manager):
        with patch(
            "homelab_manager.services.backup_manager.CommandSequence"
        ) as mock_seq:
            mock_seq.return_value.run.return_value = {
                "success": False,
                "error": "tar failed",
            }
            result = manager.create_backup()
            assert result["success"] is False
            assert "backup_path" not in result
            assert result["error"] == "tar failed"

    def test_command_uses_appdata_target(self, manager):
        captured = {}
        with patch(
            "homelab_manager.services.backup_manager.CommandSequence"
        ) as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}

            def remember(steps):
                captured["steps"] = steps
                return mock_seq.return_value

            mock_seq.side_effect = remember
            manager.create_backup()
            step = captured["steps"][0]
            assert "tar" in step.cmd
            assert "-czf" in step.cmd
            assert "appdata" in step.cmd
            assert step.label == "create archive"


class TestRestoreBackup:
    def test_path_traversal_outside_backup_dir(self, manager, tmp_path):
        """Test that paths outside backup_dir are rejected"""
        # Try to restore from parent directory
        traversal_path = manager.backup_dir.parent / "etc" / "shadow"
        result = manager.restore_backup(str(traversal_path))
        assert result["success"] is False
        assert "must be within the backup directory" in result["error"]

    def test_path_traversal_with_dotdot(self, manager, tmp_path):
        """Test that ../ sequences are rejected"""
        # Construct a path that uses ../ to escape backup_dir
        traversal_path = str(manager.backup_dir / ".." / "evil.tar.gz")
        result = manager.restore_backup(traversal_path)
        assert result["success"] is False
        assert "must be within the backup directory" in result["error"]

    def test_valid_path_within_backup_dir_succeeds_with_valid_file(
        self, manager, tmp_path
    ):
        """Test that valid paths within backup_dir are accepted"""
        # Create a real backup file inside backup_dir
        backup_file = manager.backup_dir / "homelab_backup_test.tar.gz"
        backup_file.write_bytes(b"")
        captured = {}

        with patch(
            "homelab_manager.services.backup_manager.CommandSequence"
        ) as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}

            def remember(steps, cwd=None):
                captured["steps"] = steps
                captured["cwd"] = cwd
                return mock_seq.return_value

            mock_seq.side_effect = remember
            result = manager.restore_backup(str(backup_file))
            assert result["success"] is True
            assert "restored successfully" in result["message"]

    def test_directory_not_file_rejected(self, manager, tmp_path):
        """Test that directories are rejected"""
        # Create a directory inside backup_dir
        backup_dir_path = manager.backup_dir / "subdir"
        backup_dir_path.mkdir(exist_ok=True)
        result = manager.restore_backup(str(backup_dir_path))
        assert result["success"] is False
        assert "must be a regular file" in result["error"]

    def test_missing_file_returns_error(self, manager, tmp_path):
        """Test that missing files within backup_dir are reported"""
        missing = manager.backup_dir / "no-such.tar.gz"
        result = manager.restore_backup(str(missing))
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_success_runs_three_steps_and_attaches_message(self, manager, tmp_path):
        """Test successful restore runs all three steps"""
        # Create file in the backup_dir to pass validation
        backup_file = manager.backup_dir / "homelab_backup_x.tar.gz"
        backup_file.write_bytes(b"")
        captured = {}

        with patch(
            "homelab_manager.services.backup_manager.CommandSequence"
        ) as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}

            def remember(steps, cwd=None):
                captured["steps"] = steps
                captured["cwd"] = cwd
                return mock_seq.return_value

            mock_seq.side_effect = remember
            result = manager.restore_backup(str(backup_file))
            assert result["success"] is True
            assert "restored successfully" in result["message"]
            labels = [s.label for s in captured["steps"]]
            assert labels == ["stop services", "extract backup", "restart services"]
            assert captured["cwd"] == manager.project_root

    def test_failure_propagates_error(self, manager, tmp_path):
        """Test that command failure is propagated"""
        # Create file in the backup_dir to pass validation
        backup_file = manager.backup_dir / "homelab_backup_y.tar.gz"
        backup_file.write_bytes(b"")
        with patch(
            "homelab_manager.services.backup_manager.CommandSequence"
        ) as mock_seq:
            mock_seq.return_value.run.return_value = {
                "success": False,
                "error": "extract backup failed: corrupt archive",
            }
            result = manager.restore_backup(str(backup_file))
            assert result["success"] is False
            assert "corrupt archive" in result["error"]
            assert "message" not in result
