#!/usr/bin/env python3
"""Tests for homelab_manager.services.updates module"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from homelab_manager.services.updates import UpdateManager


def make_registry(services=None):
    """Create a mock ServiceRegistry"""
    registry = Mock()
    registry.services = services or {}
    registry.get_service.return_value = None
    registry.get_service_by_container.return_value = None
    return registry


class TestUpdateManagerInit:
    """Tests for UpdateManager initialization"""

    def test_init_with_custom_registry(self):
        """Test initialization with injected registry"""
        registry = make_registry()
        manager = UpdateManager(registry=registry)
        assert manager.registry is registry

    def test_init_creates_default_registry(self):
        """Test initialization creates a ServiceRegistry when none provided"""
        with patch("homelab_manager.services.updates.ServiceRegistry") as mock_reg:
            mock_reg.return_value = Mock()
            manager = UpdateManager()
            assert manager.registry is not None


class TestCheckUpdates:
    """Tests for UpdateManager.check_updates()"""

    def test_check_updates_success(self):
        """Test check_updates returns success dict"""
        manager = UpdateManager(registry=make_registry())
        mock_result = Mock()
        mock_result.stdout = "SERVICE   IMAGE   TAG\n"

        with patch("subprocess.run", return_value=mock_result):
            result = manager.check_updates()

        assert result["success"] is True
        assert "message" in result

    def test_check_updates_subprocess_failure(self):
        """Test check_updates returns failure dict on CalledProcessError"""
        manager = UpdateManager(registry=make_registry())

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "docker", stderr="error msg"),
        ):
            result = manager.check_updates()

        assert result["success"] is False
        assert "error" in result

    def test_check_updates_generic_exception(self):
        """Test check_updates returns failure dict on unexpected exception"""
        manager = UpdateManager(registry=make_registry())

        with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
            result = manager.check_updates()

        assert result["success"] is False
        assert "error" in result


class TestUpdateAll:
    """Tests for UpdateManager.update_all()"""

    def test_update_all_success(self):
        """Test update_all returns success dict"""
        manager = UpdateManager(registry=make_registry())
        mock_result = Mock()
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = manager.update_all()

        assert result["success"] is True
        assert "message" in result

    def test_update_all_subprocess_failure(self):
        """Test update_all returns failure dict on CalledProcessError"""
        manager = UpdateManager(registry=make_registry())

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "docker", stderr="pull failed"
            ),
        ):
            result = manager.update_all()

        assert result["success"] is False
        assert "error" in result

    def test_update_all_generic_exception(self):
        """Test update_all returns failure dict on unexpected exception"""
        manager = UpdateManager(registry=make_registry())

        with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
            result = manager.update_all()

        assert result["success"] is False


class TestUpdateService:
    """Tests for UpdateManager.update_service()"""

    def test_update_service_unknown_service(self):
        """Test update_service returns failure for unknown service"""
        registry = make_registry()
        registry.get_service.return_value = None
        registry.get_service_by_container.return_value = None
        manager = UpdateManager(registry=registry)

        result = manager.update_service("nonexistent-service")

        assert result["success"] is False
        assert "Unknown service" in result["error"]

    def test_update_service_success_by_id(self):
        """Test update_service succeeds for known service ID"""
        mock_service = Mock()
        mock_service.name = "test-service"

        registry = make_registry()
        registry.get_service.return_value = mock_service
        manager = UpdateManager(registry=registry)

        mock_result = Mock()
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = manager.update_service("test-service")

        assert result["success"] is True
        assert "message" in result

    def test_update_service_falls_back_to_container_name(self):
        """Test update_service falls back to container name lookup"""
        mock_service = Mock()
        mock_service.name = "test-service"

        registry = make_registry()
        registry.get_service.return_value = None
        registry.get_service_by_container.return_value = mock_service
        manager = UpdateManager(registry=registry)

        mock_result = Mock()
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = manager.update_service("test-container")

        assert result["success"] is True

    def test_update_service_subprocess_failure(self):
        """Test update_service returns failure on subprocess error"""
        mock_service = Mock()
        mock_service.name = "test-service"

        registry = make_registry()
        registry.get_service.return_value = mock_service
        manager = UpdateManager(registry=registry)

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "docker", stderr="pull failed"
            ),
        ):
            result = manager.update_service("test-service")

        assert result["success"] is False
        assert "error" in result

    def test_update_service_generic_exception(self):
        """Test update_service returns failure on unexpected exception"""
        mock_service = Mock()
        mock_service.name = "test-service"

        registry = make_registry()
        registry.get_service.return_value = mock_service
        manager = UpdateManager(registry=registry)

        with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
            result = manager.update_service("test-service")

        assert result["success"] is False


class TestGetUpdateStatus:
    """Tests for UpdateManager.get_update_status()"""

    def test_get_update_status_success(self):
        """Test get_update_status returns success dict with services list"""
        registry = make_registry()
        registry.get_service_by_container.return_value = None
        manager = UpdateManager(registry=registry)

        mock_result = Mock()
        mock_result.stdout = "CONTAINER   IMAGE   TAG\napp   nginx   latest"

        with patch("subprocess.run", return_value=mock_result):
            result = manager.get_update_status()

        assert result["success"] is True
        assert "services" in result
        assert "total_services" in result
        assert isinstance(result["services"], list)

    def test_get_update_status_empty_output(self):
        """Test get_update_status handles empty docker output"""
        registry = make_registry()
        manager = UpdateManager(registry=registry)

        mock_result = Mock()
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = manager.get_update_status()

        assert result["success"] is True
        assert result["total_services"] == 0

    def test_get_update_status_subprocess_failure(self):
        """Test get_update_status returns failure on subprocess error"""
        manager = UpdateManager(registry=make_registry())

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "docker", stderr="error"),
        ):
            result = manager.get_update_status()

        assert result["success"] is False
        assert "error" in result

    def test_get_update_status_resolves_service_name(self):
        """Test get_update_status uses registry to resolve container names"""
        mock_service = Mock()
        mock_service.name = "Resolved Service"

        registry = make_registry()
        registry.get_service_by_container.return_value = mock_service
        manager = UpdateManager(registry=registry)

        mock_result = Mock()
        mock_result.stdout = "CONTAINER   IMAGE   TAG\nmycontainer   nginx   latest"

        with patch("subprocess.run", return_value=mock_result):
            result = manager.get_update_status()

        assert result["success"] is True
        # The resolved service name should appear
        assert any(s["name"] == "Resolved Service" for s in result["services"])


class TestGetAllServiceNames:
    """Tests for UpdateManager.get_all_service_names()"""

    def test_get_all_service_names_returns_list(self):
        """Test get_all_service_names returns a list"""
        registry = make_registry()
        manager = UpdateManager(registry=registry)

        names = manager.get_all_service_names()
        assert isinstance(names, list)

    def test_get_all_service_names_returns_ids(self):
        """Test get_all_service_names returns service IDs"""
        mock_svc1 = Mock()
        mock_svc1.id = "service-a"
        mock_svc2 = Mock()
        mock_svc2.id = "service-b"

        registry = Mock()
        registry.services = {"service-a": mock_svc1, "service-b": mock_svc2}
        manager = UpdateManager(registry=registry)

        names = manager.get_all_service_names()

        assert "service-a" in names
        assert "service-b" in names
        assert len(names) == 2

    def test_get_all_service_names_empty_registry(self):
        """Test get_all_service_names returns empty list when no services"""
        registry = Mock()
        registry.services = {}
        manager = UpdateManager(registry=registry)

        names = manager.get_all_service_names()
        assert names == []
