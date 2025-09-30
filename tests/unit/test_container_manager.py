"""
Simple unit tests for container management
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager.container_manager import ContainerManager


class TestContainerManagerSimple:
    """Simple test cases for ContainerManager class"""

    def test_init(self):
        """Test ContainerManager initialization"""
        with patch("homelab_manager.container_manager.docker.from_env"):
            manager = ContainerManager()
            assert manager is not None
            assert hasattr(manager, 'containers')
            assert len(manager.containers) == 4  # homeassistant, homepage, grafana, filebrowser

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

    def test_containers_config(self):
        """Test that containers configuration is correct"""
        with patch("homelab_manager.container_manager.docker.from_env"):
            manager = ContainerManager()
            
            # Check that all expected containers are present
            expected_containers = ["homeassistant", "homepage", "grafana", "filebrowser"]
            for container in expected_containers:
                assert container in manager.containers
                assert "image" in manager.containers[container]
                assert "port" in manager.containers[container]
                assert "health_check_url" in manager.containers[container]

    def test_show_disk_usage(self, capsys):
        """Test showing disk usage"""
        with patch("homelab_manager.container_manager.docker.from_env"), \
             patch("subprocess.run") as mock_run:
            
            mock_run.return_value = Mock(returncode=0, stdout="Disk usage info")
            
            manager = ContainerManager()
            manager.show_disk_usage()
            
            captured = capsys.readouterr()
            assert "Docker disk usage" in captured.out

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
