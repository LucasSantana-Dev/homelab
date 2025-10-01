"""
Simple unit tests for update management
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager.updates import HomelabUpdateManager


class TestHomelabUpdateManagerSimple:
    """Simple test cases for HomelabUpdateManager class"""

    def test_init(self):
        """Test HomelabUpdateManager initialization"""
        with patch("homelab_manager.updates.docker.from_env"):
            manager = HomelabUpdateManager()
            assert manager is not None
            assert hasattr(manager, 'services')
            assert isinstance(manager.services, list)
            assert len(manager.services) > 0

    def test_check_image_updates_success(self):
        """Test successful image update check"""
        mock_client = Mock()
        mock_image = Mock()
        mock_image.tags = ["test/image:latest"]
        mock_image.short_id = "abc123"
        mock_client.images.pull.return_value = mock_image
        mock_client.images.get.return_value = Mock(short_id="def456")

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client):
            manager = HomelabUpdateManager()
            has_update, current_id, latest_id = manager.check_image_updates("test/image:latest", "test/image:old")

            assert has_update is True
            assert current_id == "def456"
            assert latest_id == "abc123"

    def test_check_image_updates_failure(self):
        """Test failed image update check"""
        mock_client = Mock()
        mock_client.images.pull.side_effect = Exception("Pull failed")

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client):
            manager = HomelabUpdateManager()
            has_update, current_id, latest_id = manager.check_image_updates("test/image:latest", "test/image:old")

            assert has_update is False
            assert current_id == "Error"
            assert latest_id == "Error"

    def test_check_all_updates(self):
        """Test checking all updates"""
        mock_client = Mock()
        mock_image = Mock()
        mock_image.tags = ["test/image:latest"]
        mock_client.images.pull.return_value = mock_image

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client):
            manager = HomelabUpdateManager()
            updates = manager.check_all_updates()

            assert isinstance(updates, list)
            # Should check all services defined in the manager
            assert len(updates) > 0

    def test_update_service_success(self):
        """Test successful service update"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_client.containers.list.return_value = [mock_container]

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client), \
             patch("subprocess.run") as mock_run, \
             patch("time.sleep"):

            mock_run.return_value = Mock(returncode=0)

            manager = HomelabUpdateManager()
            result = manager.update_service("test-service")

            assert result is True

    def test_update_service_failure(self):
        """Test failed service update"""
        with patch("homelab_manager.updates.docker.from_env"), \
             patch("subprocess.run") as mock_run:

            # Mock subprocess to raise CalledProcessError
            from subprocess import CalledProcessError
            mock_run.side_effect = CalledProcessError(1, "docker-compose", "Command failed")

            manager = HomelabUpdateManager()
            result = manager.update_service("nonexistent-service")

            assert result is False

    def test_update_all_services(self):
        """Test updating all services"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_client.containers.list.return_value = [mock_container]

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client), \
             patch("subprocess.run") as mock_run, \
             patch("time.sleep"):

            mock_run.return_value = Mock(returncode=0)

            manager = HomelabUpdateManager()
            result = manager.update_all_services()

            assert isinstance(result, bool)

    def test_show_versions(self, capsys):
        """Test showing service versions"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-service"
        mock_container.image.tags = ["test/image:latest"]
        mock_client.containers.list.return_value = [mock_container]

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client):
            manager = HomelabUpdateManager()
            manager.show_versions()

            captured = capsys.readouterr()
            assert "Service Versions" in captured.out or "test-service" in captured.out

    def test_auto_check(self):
        """Test automatic update check"""
        mock_client = Mock()
        mock_image = Mock()
        mock_image.tags = ["test/image:latest"]
        mock_client.images.pull.return_value = mock_image

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client), \
             patch("homelab_manager.updates.HomelabUpdateManager.check_all_updates") as mock_check:

            mock_check.return_value = []

            manager = HomelabUpdateManager()
            manager.auto_check()

            # Should not raise any exceptions
            assert True

    def test_services_configuration(self):
        """Test that services configuration is correct"""
        with patch("homelab_manager.updates.docker.from_env"):
            manager = HomelabUpdateManager()

            # Check that services are properly configured
            assert hasattr(manager, 'services')
            assert isinstance(manager.services, list)
            assert len(manager.services) > 0

            # Check that services contain expected images
            service_images = manager.services
            assert any("home-assistant" in service for service in service_images)
            assert any("homepage" in service for service in service_images)

    def test_main_function(self):
        """Test the main function"""
        from homelab_manager.updates import main
        from unittest.mock import patch

        # Mock the argument parsing to avoid sys.argv conflicts
        with patch('sys.argv', ['updates.py', 'check']):
            # Should not raise any exceptions
            main()
            assert True

    def test_check_image_updates_same_tag(self):
        """Test checking image updates with same tag (no update)"""
        mock_client = Mock()
        mock_image = Mock()
        mock_image.tags = ["test/image:latest"]
        mock_image.short_id = "abc123"
        mock_client.images.pull.return_value = mock_image
        mock_client.images.get.return_value = Mock(short_id="abc123")  # Same ID

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client):
            manager = HomelabUpdateManager()
            has_update, current_id, latest_id = manager.check_image_updates("test/image:latest", "test/image:latest")

            # Should return False if same ID (no update needed)
            assert has_update is False
            assert current_id == "abc123"
            assert latest_id == "abc123"

    def test_show_versions_empty_containers(self, capsys):
        """Test showing versions when no containers are running"""
        mock_client = Mock()
        mock_client.containers.list.return_value = []

        with patch("homelab_manager.updates.docker.from_env", return_value=mock_client):
            manager = HomelabUpdateManager()
            manager.show_versions()

            captured = capsys.readouterr()
            # Should handle empty container list gracefully
            assert True

    def test_check_image_updates_with_exception(self, mock_docker_client):
        """Test checking image updates with exception"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            mock_docker_client.images.get.side_effect = Exception("Image not found")

            manager = HomelabUpdateManager()
            result = manager.check_image_updates("test/image", "latest")

            assert result == (False, "Error", "Error")

    def test_check_image_updates_image_not_found(self, mock_docker_client):
        """Test checking image updates when image not found"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            mock_docker_client.images.get.side_effect = Exception("Image not found")

            manager = HomelabUpdateManager()
            result = manager.check_image_updates("test/image", "latest")

            assert result == (False, "Error", "Error")

    def test_update_service_with_exception(self, mock_docker_client):
        """Test updating service with exception"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            mock_run.side_effect = Exception("Subprocess failed")

            manager = HomelabUpdateManager()
            result = manager.update_service("test-service")

            assert result is False

    def test_update_all_services_with_exception(self, mock_docker_client):
        """Test updating all services with exception"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            mock_run.side_effect = Exception("Subprocess failed")

            manager = HomelabUpdateManager()
            result = manager.update_all_services()

            assert result is False

    def test_auto_check_with_exception(self, mock_docker_client):
        """Test auto check with exception"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            mock_docker_client.containers.list.side_effect = Exception("Docker error")

            manager = HomelabUpdateManager()
            result = manager.auto_check()

            # The auto_check method doesn't return a boolean, it just prints
            assert result is None

    def test_show_versions_with_exception(self, mock_docker_client):
        """Test showing versions with exception"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            mock_docker_client.containers.list.side_effect = Exception("Docker error")

            manager = HomelabUpdateManager()
            manager.show_versions()

            # Should not raise any exceptions
            assert True

    def test_check_all_updates_with_exception(self, mock_docker_client):
        """Test checking all updates with exception"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            mock_docker_client.containers.list.side_effect = Exception("Docker error")

            manager = HomelabUpdateManager()
            manager.check_all_updates()

            # Should not raise any exceptions
            assert True

    def test_update_service_with_subprocess_failure(self, mock_docker_client):
        """Test updating service with subprocess failure"""
        import subprocess

        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            mock_run.side_effect = subprocess.CalledProcessError(1, "docker-compose")

            manager = HomelabUpdateManager()
            result = manager.update_service("test-service")

            assert result is False

    def test_update_all_services_with_subprocess_failure(self, mock_docker_client):
        """Test updating all services with subprocess failure"""
        import subprocess

        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            mock_run.side_effect = subprocess.CalledProcessError(1, "docker-compose")

            manager = HomelabUpdateManager()
            result = manager.update_all_services()

            assert result is False

    def test_check_image_updates_with_different_tags(self, mock_docker_client):
        """Test checking image updates with different tag scenarios"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = HomelabUpdateManager()

            # Test case 1: Different tag (update available)
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"
            mock_latest_image = Mock()
            mock_latest_image.short_id = "def456"

            mock_docker_client.images.get.return_value = mock_current_image
            mock_docker_client.images.pull.return_value = mock_latest_image

            result = manager.check_image_updates("test/image", "latest")

            assert result == (True, "abc123", "def456")

    def test_check_image_updates_with_same_tags(self, mock_docker_client):
        """Test checking image updates with same tags"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = HomelabUpdateManager()

            # Test case 2: Same tag (no update)
            mock_image = Mock()
            mock_image.short_id = "abc123"

            mock_docker_client.images.get.return_value = mock_image
            mock_docker_client.images.pull.return_value = mock_image

            result = manager.check_image_updates("test/image", "latest")

            assert result == (False, "abc123", "abc123")

    def test_update_service_with_success(self, mock_docker_client):
        """Test updating service with success"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock container list
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_container.status = "running"
            mock_docker_client.containers.list.return_value = [mock_container]

            manager = HomelabUpdateManager()
            result = manager.update_service("test-service")

            assert result is True

    def test_update_service_with_container_not_found(self, mock_docker_client):
        """Test updating service when container is not found"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock empty container list
            mock_docker_client.containers.list.return_value = []

            manager = HomelabUpdateManager()
            result = manager.update_service("nonexistent-service")

            assert result is False

    def test_update_all_services_with_success(self, mock_docker_client):
        """Test updating all services with success"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock container list
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_container.status = "running"
            mock_docker_client.containers.list.return_value = [mock_container]

            manager = HomelabUpdateManager()
            result = manager.update_all_services()

            assert result is True

    def test_auto_check_with_success(self, mock_docker_client):
        """Test auto check with success"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            # Mock container list
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_container.status = "running"
            mock_docker_client.containers.list.return_value = [mock_container]

            manager = HomelabUpdateManager()
            result = manager.auto_check()

            # The auto_check method doesn't return a boolean, it just prints
            assert result is None

    def test_show_versions_with_containers(self, mock_docker_client, capsys):
        """Test showing versions with containers"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            # Mock container list
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_container.status = "running"
            mock_container.image.tags = ["test/image:latest"]
            mock_docker_client.containers.list.return_value = [mock_container]

            manager = HomelabUpdateManager()
            manager.show_versions()

            captured = capsys.readouterr()
            # The show_versions method shows a table, so we check for the table structure
            assert "Service Versions" in captured.out

    def test_check_all_updates_with_success(self, mock_docker_client):
        """Test checking all updates with success"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            # Mock container list
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_container.status = "running"
            mock_docker_client.containers.list.return_value = [mock_container]

            manager = HomelabUpdateManager()
            manager.check_all_updates()

            # Should not raise any exceptions
            assert True

    def test_check_image_updates_with_pull_failure(self, mock_docker_client):
        """Test checking image updates with pull failure"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = HomelabUpdateManager()

            # Mock image get success but pull failure
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"
            mock_docker_client.images.get.return_value = mock_current_image
            mock_docker_client.images.pull.side_effect = Exception("Pull failed")

            result = manager.check_image_updates("test/image", "latest")

            assert result == (False, "Error", "Error")

    def test_update_service_with_subprocess_success(self, mock_docker_client):
        """Test updating service with subprocess success"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock container list
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_container.status = "running"
            mock_docker_client.containers.list.return_value = [mock_container]

            manager = HomelabUpdateManager()
            result = manager.update_service("test-service")

            assert result is True

    def test_update_all_services_with_subprocess_success(self, mock_docker_client):
        """Test updating all services with subprocess success"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run, patch("os.chdir"), patch("homelab_manager.automation.HomelabAutomation") as mock_automation, patch("homelab_manager.health.HomelabHealthMonitor") as mock_monitor:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock automation backup success
            mock_automation_instance = Mock()
            mock_automation_instance.backup.return_value = "/path/to/backup"
            mock_automation.return_value = mock_automation_instance

            # Mock health monitor
            mock_monitor_instance = Mock()
            mock_monitor.return_value = mock_monitor_instance

            # Mock container list
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_container.status = "running"
            mock_docker_client.containers.list.return_value = [mock_container]

            manager = HomelabUpdateManager()
            result = manager.update_all_services()

            assert result is True
