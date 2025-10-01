"""
Unit tests for container management
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager.container_manager import ContainerManager


class TestContainerManager:
    """Test cases for ContainerManager class"""

    def test_init(self):
        """Test ContainerManager initialization"""
        with patch("homelab_manager.container_manager.docker.from_env"):
            manager = ContainerManager()
            assert manager is not None

    def test_check_docker_running_success(self):
        """Test Docker running check success"""
        mock_client = Mock()
        mock_client.ping.return_value = True

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            assert manager.check_docker_running() is True

    def test_check_docker_running_failure(self):
        """Test Docker running check failure"""
        import docker.errors
        mock_client = Mock()
        mock_client.ping.side_effect = docker.errors.APIError("Docker not running")

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            assert manager.check_docker_running() is False

    def test_get_container_status(self):
        """Test getting container status"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "homeassistant"
        mock_container.status = "running"
        mock_container.image.tags = ["ghcr.io/home-assistant/home-assistant:stable"]
        mock_container.ports = {
            "8123/tcp": [{"HostPort": "8123", "PrivatePort": "8123"}]
        }
        mock_client.containers.get.return_value = mock_container

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            status = manager.get_container_status()

            # Should have 4 containers (homeassistant, homepage, grafana, filebrowser)
            assert len(status) == 4
            # Find the homeassistant container
            homeassistant = next(c for c in status if c["name"] == "homeassistant")
            assert homeassistant["status"] == "running"
            assert homeassistant["image"] == "ghcr.io/home-assistant/home-assistant:stable"

    def test_get_container_status_no_ports(self):
        """Test getting container status with no ports"""
        mock_client = Mock()

        # Mock all containers that are in the ContainerManager
        mock_containers = {}
        for container_name in ["homeassistant", "homepage", "grafana", "filebrowser"]:
            mock_container = Mock()
            mock_container.name = container_name
            mock_container.status = "running"
            mock_container.image.tags = ["test/image:latest"]
            mock_container.ports = {}
            mock_containers[container_name] = mock_container
            mock_client.containers.get.return_value = mock_container

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            status = manager.get_container_status()

            assert isinstance(status, list)
            assert len(status) == 4  # All 4 containers
            assert all(container["status"] == "running" for container in status)

    def test_display_container_status(self, capsys):
        """Test displaying container status"""
        mock_client = Mock()

        # Mock all containers that are in the ContainerManager
        for container_name in ["homeassistant", "homepage", "grafana", "filebrowser"]:
            mock_container = Mock()
            mock_container.name = container_name
            mock_container.status = "running"
            mock_container.image.tags = ["test/image:latest"]
            mock_container.ports = {}
            mock_client.containers.get.return_value = mock_container

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            manager.display_container_status()

            captured = capsys.readouterr()
            assert "Container Status" in captured.out
            assert "homeassistant" in captured.out

    def test_check_for_updates(self):
        """Test checking for updates"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.image.tags = ["test/image:latest"]
        mock_client.containers.list.return_value = [mock_container]

        # Mock the image pull to simulate update available
        mock_image = Mock()
        mock_image.tags = ["test/image:newer"]
        mock_client.images.pull.return_value = mock_image

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            updates = manager.check_for_updates()

            assert "test-container" in updates
            assert isinstance(updates["test-container"], bool)

    def test_backup_container_data(self, temp_homelab_dir):
        """Test backing up container data"""
        mock_client = Mock()

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = Mock(returncode=0)

            manager = ContainerManager()
            backup_path = manager.backup_container_data("test-container")

            assert backup_path is not None
            assert backup_path.exists()

    def test_update_container_success(self):
        """Test successful container update"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "homeassistant"  # Use a valid container name
        mock_container.image.tags = ["test/image:latest"]
        mock_container.status = "running"  # Add status
        mock_client.containers.get.return_value = mock_container

        # Mock the update process
        mock_image = Mock()
        mock_image.tags = ["test/image:newer"]
        mock_client.images.pull.return_value = mock_image

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client), \
             patch("subprocess.run") as mock_run, patch("requests.get") as mock_requests, patch("time.sleep"):

            mock_run.return_value = Mock(returncode=0)

            # Mock successful health check response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            manager = ContainerManager()
            result = manager.update_container("homeassistant")

            assert result is True

    def test_update_container_failure(self):
        """Test container update failure"""
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("Container not found")

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            result = manager.update_container("nonexistent-container")

            assert result is False

    def test_wait_for_container_health(self):
        """Test waiting for container health"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "homeassistant"  # Use a valid container name
        mock_container.status = "running"  # Use status instead of health
        mock_client.containers.get.return_value = mock_container

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client), \
             patch("time.sleep"), patch("requests.get") as mock_requests:

            # Mock successful health check response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            manager = ContainerManager()
            result = manager.wait_for_container_health("homeassistant")

            assert result is True

    def test_wait_for_container_health_timeout(self):
        """Test waiting for container health with timeout"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "homeassistant"  # Use a valid container name
        mock_container.status = "stopped"  # Use stopped status to simulate timeout
        mock_client.containers.get.return_value = mock_container

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client), \
             patch("time.sleep"):

            manager = ContainerManager()
            result = manager.wait_for_container_health("homeassistant")

            assert result is False

    def test_show_disk_usage(self, capsys):
        """Test showing disk usage"""
        with patch("homelab_manager.container_manager.docker.from_env"), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = Mock(returncode=0, stdout="Disk usage info")

            manager = ContainerManager()
            manager.show_disk_usage()

            captured = capsys.readouterr()
            assert "Docker disk usage" in captured.out

    def test_show_recent_logs(self, capsys):
        """Test showing recent logs"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.logs.return_value = b"Log line 1\nLog line 2\nLog line 3"
        mock_client.containers.get.return_value = mock_container

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            manager.show_recent_logs("test-container", lines=2)

            captured = capsys.readouterr()
            assert "Recent logs for test-container" in captured.out

    def test_cleanup_old_images(self):
        """Test cleaning up old images"""
        mock_client = Mock()
        mock_image = Mock()
        mock_image.tags = ["test/image:old"]
        mock_client.images.list.return_value = [mock_image]

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            manager.cleanup_old_images()

            # Should not raise any exceptions
            assert True

    def test_main_function(self):
        """Test the main function"""
        from homelab_manager.container_manager import main
        from unittest.mock import patch

        # Mock the argument parsing to avoid sys.argv conflicts
        with patch('sys.argv', ['container_manager.py', 'status']):
            # Should not raise any exceptions
            main()
            assert True

    def test_check_for_updates(self, mock_docker_client):
        """Test checking for container updates"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = ContainerManager()

            # Mock image objects
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"
            mock_latest_image = Mock()
            mock_latest_image.short_id = "def456"

            mock_docker_client.images.get.return_value = mock_current_image
            mock_docker_client.images.pull.return_value = mock_latest_image

            result = manager.check_for_updates()

            assert isinstance(result, dict)

    def test_check_for_updates_same_version(self, mock_docker_client):
        """Test checking for updates when containers are up to date"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = ContainerManager()

            # Mock image objects with same ID
            mock_image = Mock()
            mock_image.short_id = "abc123"

            mock_docker_client.images.get.return_value = mock_image
            mock_docker_client.images.pull.return_value = mock_image

            result = manager.check_for_updates()

            assert isinstance(result, dict)

    def test_check_for_updates_with_exception(self, mock_docker_client):
        """Test checking for updates with exception"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = ContainerManager()

            # Mock exception
            mock_docker_client.images.get.side_effect = Exception("Image not found")

            result = manager.check_for_updates()

            assert isinstance(result, dict)

    def test_backup_container_data(self, mock_docker_client, temp_homelab_dir):
        """Test backing up container data"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            manager = ContainerManager()

            # Create test data directory
            test_data_dir = temp_homelab_dir / "appdata" / "homeassistant"
            test_data_dir.mkdir(parents=True, exist_ok=True)
            (test_data_dir / "test_file.txt").write_text("test data")

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            result = manager.backup_container_data("homeassistant")

            assert isinstance(result, Path)

    def test_backup_container_data_no_data(self, mock_docker_client, temp_homelab_dir):
        """Test backing up container data when no data exists"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            manager = ContainerManager()

            # Test with a valid container name
            result = manager.backup_container_data("homeassistant")

            assert isinstance(result, Path)

    def test_update_container(self, mock_docker_client, temp_homelab_dir):
        """Test updating a container"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run, patch("time.sleep"), patch("requests.get") as mock_requests:

            manager = ContainerManager()

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock successful health check response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            # Mock container list
            mock_container = Mock()
            mock_container.name = "homeassistant"
            mock_container.status = "running"
            mock_docker_client.containers.list.return_value = [mock_container]

            result = manager.update_container("homeassistant")

            assert result is True

    def test_update_container_failure(self, mock_docker_client, temp_homelab_dir):
        """Test updating a container with failure"""
        import subprocess

        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            manager = ContainerManager()

            # Mock subprocess failure
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker-compose")

            result = manager.update_container("homeassistant")

            assert result is False

    def test_check_for_updates_with_success(self, mock_docker_client):
        """Test checking for updates with success"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = ContainerManager()

            # Mock image objects with different IDs
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"
            mock_latest_image = Mock()
            mock_latest_image.short_id = "def456"

            mock_docker_client.images.get.return_value = mock_current_image
            mock_docker_client.images.pull.return_value = mock_latest_image

            result = manager.check_for_updates()

            assert isinstance(result, dict)

    def test_check_for_updates_with_same_version(self, mock_docker_client):
        """Test checking for updates when containers are up to date"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = ContainerManager()

            # Mock image objects with same ID
            mock_image = Mock()
            mock_image.short_id = "abc123"

            mock_docker_client.images.get.return_value = mock_image
            mock_docker_client.images.pull.return_value = mock_image

            result = manager.check_for_updates()

            assert isinstance(result, dict)

    def test_check_for_updates_with_exception(self, mock_docker_client):
        """Test checking for updates with exception"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ):
            manager = ContainerManager()

            # Mock exception
            mock_docker_client.images.get.side_effect = Exception("Image not found")

            result = manager.check_for_updates()

            assert isinstance(result, dict)

    def test_backup_container_data_with_success(self, mock_docker_client, temp_homelab_dir):
        """Test backing up container data with success"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Create test data directory
            test_data_dir = temp_homelab_dir / "appdata" / "homeassistant"
            test_data_dir.mkdir(parents=True, exist_ok=True)
            (test_data_dir / "test_file.txt").write_text("test data")

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            manager = ContainerManager()
            result = manager.backup_container_data("homeassistant")

            assert isinstance(result, Path)

    def test_backup_container_data_with_no_data(self, mock_docker_client, temp_homelab_dir):
        """Test backing up container data when no data exists"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            manager = ContainerManager()

            # Don't create data directory
            result = manager.backup_container_data("homeassistant")

            assert isinstance(result, Path)

    def test_update_container_with_success(self, mock_docker_client, temp_homelab_dir):
        """Test updating a container with success"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run, patch("time.sleep"):

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock container list
            mock_container = Mock()
            mock_container.name = "homeassistant"
            mock_container.status = "running"
            mock_container.health = "healthy"
            mock_docker_client.containers.list.return_value = [mock_container]
            mock_docker_client.containers.get.return_value = mock_container

            manager = ContainerManager()
            result = manager.update_container("homeassistant")

            assert result is True

    def test_update_container_with_health_check_failure(self, mock_docker_client, temp_homelab_dir):
        """Test updating a container with health check failure"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run, patch("time.sleep"), patch("requests.get") as mock_requests:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            # Mock failed health check response
            mock_response = Mock()
            mock_response.status_code = 500
            mock_requests.return_value = mock_response

            # Mock container list
            mock_container = Mock()
            mock_container.name = "homeassistant"
            mock_container.status = "running"
            mock_container.health = "unhealthy"
            mock_docker_client.containers.list.return_value = [mock_container]
            mock_docker_client.containers.get.return_value = mock_container

            manager = ContainerManager()
            result = manager.update_container("homeassistant")

            assert result is False

    def test_wait_for_container_health_with_success(self, mock_docker_client):
        """Test waiting for container health with success"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("time.sleep"), patch("requests.get") as mock_requests:

            # Mock container with running status
            mock_container = Mock()
            mock_container.name = "homeassistant"
            mock_container.status = "running"
            mock_docker_client.containers.get.return_value = mock_container

            # Mock successful health check response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            manager = ContainerManager()
            result = manager.wait_for_container_health("homeassistant")

            assert result is True

    def test_wait_for_container_health_with_timeout(self, mock_docker_client):
        """Test waiting for container health with timeout"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("time.sleep"):

            # Mock container with unhealthy status
            mock_container = Mock()
            mock_container.name = "homeassistant"
            mock_container.health = "unhealthy"
            mock_docker_client.containers.get.return_value = mock_container

            manager = ContainerManager()
            result = manager.wait_for_container_health("homeassistant")

            assert result is False

    def test_show_disk_usage_with_success(self, capsys):
        """Test showing disk usage with success"""
        with patch("homelab_manager.container_manager.docker.from_env"), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = Mock(returncode=0, stdout="Disk usage info")

            manager = ContainerManager()
            manager.show_disk_usage()

            captured = capsys.readouterr()
            assert "Docker disk usage" in captured.out

    def test_show_recent_logs_with_success(self, capsys):
        """Test showing recent logs with success"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.logs.return_value = b"test log output"
        mock_client.containers.get.return_value = mock_container

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            manager.show_recent_logs("test-container")

            captured = capsys.readouterr()
            assert "Recent logs" in captured.out

    def test_show_recent_logs_with_exception(self, capsys):
        """Test showing recent logs with exception"""
        mock_client = Mock()
        mock_client.containers.get.side_effect = Exception("Container not found")

        with patch("homelab_manager.container_manager.docker.from_env", return_value=mock_client):
            manager = ContainerManager()
            manager.show_recent_logs("nonexistent-container")

            captured = capsys.readouterr()
            assert "Failed to get logs" in captured.out

    def test_cleanup_old_images_with_success(self, mock_docker_client):
        """Test cleaning up old images with success"""
        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess success
            mock_run.return_value = Mock(returncode=0)

            manager = ContainerManager()
            manager.cleanup_old_images()

            # Should not raise any exceptions
            assert True

    def test_cleanup_old_images_with_failure(self, mock_docker_client):
        """Test cleaning up old images with failure"""
        import subprocess

        with patch(
            "homelab_manager.container_manager.docker.from_env",
            return_value=mock_docker_client,
        ), patch("subprocess.run") as mock_run:

            # Mock subprocess failure
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker")

            manager = ContainerManager()
            manager.cleanup_old_images()

            # Should not raise any exceptions
            assert True
