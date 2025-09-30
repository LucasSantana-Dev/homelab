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
