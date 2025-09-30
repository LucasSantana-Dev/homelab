"""
Unit tests for automation system - Fixed version
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager.automation import HomelabAutomation


class TestHomelabAutomation:
    """Test cases for HomelabAutomation class"""

    def test_init(self, temp_homelab_dir, mock_docker_client):
        """Test HomelabAutomation initialization"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ):
            automation = HomelabAutomation(str(temp_homelab_dir))

            assert automation.homelab_dir == temp_homelab_dir
            assert automation.backup_dir == temp_homelab_dir / "backups"
            assert automation.log_dir == temp_homelab_dir / "logs"
            assert automation.env_file == temp_homelab_dir / ".env"

    def test_check_docker_running_success(self, mock_docker_client):
        """Test Docker running check success"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ):
            automation = HomelabAutomation()
            assert automation.check_docker_running() is True

    def test_check_docker_running_failure(self, temp_homelab_dir):
        """Test Docker running check failure"""
        mock_client = Mock()
        mock_client.ping.side_effect = Exception("Docker not running")

        with patch(
            "homelab_manager.automation.docker.from_env", return_value=mock_client
        ):
            automation = HomelabAutomation(str(temp_homelab_dir))
            assert automation.check_docker_running() is False

    def test_create_networks(self, mock_docker_client):
        """Test network creation"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ):
            automation = HomelabAutomation()
            automation.create_networks()

            # Should not raise any exceptions
            assert True

    def test_create_networks_existing(self, temp_homelab_dir):
        """Test network creation when networks already exist"""
        mock_client = Mock()
        mock_client.networks.get.return_value = Mock()  # Network exists
        mock_client.networks.create.side_effect = Exception("Network already exists")

        with patch(
            "homelab_manager.automation.docker.from_env", return_value=mock_client
        ):
            automation = HomelabAutomation(str(temp_homelab_dir))
            automation.create_networks()

            # Should not raise any exceptions
            assert True

    def test_deploy_success(self, mock_docker_client, mock_subprocess):
        """Test successful deployment"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ), patch("homelab_manager.automation.HomelabAutomation.check_health"):

            automation = HomelabAutomation()
            result = automation.deploy()

            assert result is True

    def test_deploy_failure(self, mock_docker_client, temp_homelab_dir):
        """Test deployment failure"""
        mock_client = Mock()
        mock_client.ping.side_effect = Exception("Docker not running")

        with patch(
            "homelab_manager.automation.docker.from_env", return_value=mock_client
        ):
            automation = HomelabAutomation(str(temp_homelab_dir))
            result = automation.deploy()

            assert result is False

    def test_backup_success(self, mock_docker_client, temp_homelab_dir):
        """Test successful backup creation"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess calls
            mock_run.return_value = Mock(returncode=0)

            automation = HomelabAutomation(str(temp_homelab_dir))
            backup_path = automation.backup()

            assert backup_path is not None
            assert Path(backup_path).exists()

    def test_backup_failure(self, mock_docker_client, temp_homelab_dir):
        """Test backup failure"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run", side_effect=Exception("Backup failed")):

            automation = HomelabAutomation(str(temp_homelab_dir))
            backup_path = automation.backup()

            assert backup_path is None

    def test_restore_success(
        self, mock_docker_client, temp_homelab_dir, mock_subprocess
    ):
        """Test successful restore"""
        # Create a backup directory
        backup_dir = temp_homelab_dir / "backups" / "test_backup"
        backup_dir.mkdir(parents=True)

        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ), patch("homelab_manager.automation.HomelabAutomation.check_health"):

            automation = HomelabAutomation(str(temp_homelab_dir))
            result = automation.restore(str(backup_dir))

            assert result is True

    def test_restore_failure_missing_backup(self, mock_docker_client, temp_homelab_dir):
        """Test restore failure with missing backup"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ):
            automation = HomelabAutomation(str(temp_homelab_dir))
            result = automation.restore("/nonexistent/backup")

            assert result is False

    def test_cleanup(self, mock_docker_client, mock_subprocess):
        """Test cleanup execution"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ):
            automation = HomelabAutomation()
            automation.cleanup()

            # Should not raise any exceptions
            assert True

    def test_get_service_status(self, mock_docker_client):
        """Test getting service status"""
        with patch(
            "homelab_manager.automation.docker.from_env",
            return_value=mock_docker_client,
        ):
            automation = HomelabAutomation()
            status = automation.get_service_status()

            assert isinstance(status, list)
            assert len(status) == 1
            assert status[0]["name"] == "test-container"
            assert status[0]["status"] == "running"

    def test_get_directory_size(self, temp_homelab_dir):
        """Test directory size calculation"""
        with patch("homelab_manager.automation.docker.from_env"):
            automation = HomelabAutomation(str(temp_homelab_dir))

            # Create a test file
            test_file = temp_homelab_dir / "test.txt"
            test_file.write_text("test content")

            size = automation.get_directory_size(temp_homelab_dir)
            assert "B" in size or "KB" in size or "MB" in size

    def test_cleanup_old_backups(self, temp_homelab_dir):
        """Test old backup cleanup"""
        with patch("homelab_manager.automation.docker.from_env"):
            automation = HomelabAutomation(str(temp_homelab_dir))

            # Create old backup directory
            old_backup = temp_homelab_dir / "backups" / "old_backup"
            old_backup.mkdir(parents=True)

            # Mock old modification time
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_mtime = 0  # Very old timestamp
                automation.cleanup_old_backups()

            # Should not raise any exceptions
            assert True
