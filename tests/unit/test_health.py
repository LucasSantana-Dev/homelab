#!/usr/bin/env python3
"""Tests for homelab_manager.services.health module"""

from unittest.mock import Mock, patch

import pytest
import requests

from homelab_manager.services.health import HealthMonitor


def make_monitor(registry=None):
    """Create a HealthMonitor with Docker client mocked out"""
    with patch("homelab_manager.services.health.docker") as mock_docker:
        mock_docker.from_env.return_value = Mock()
        monitor = HealthMonitor(registry=registry)
    return monitor


def make_registry(services=None):
    """Create a mock ServiceRegistry"""
    registry = Mock()
    registry.get_services_with_ports.return_value = services or []
    registry.get_service.return_value = None
    return registry


class TestHealthMonitorInit:
    """Tests for HealthMonitor initialization"""

    def test_init_with_injected_registry(self):
        """Verify HealthMonitor uses the provided registry"""
        registry = make_registry()
        with patch("homelab_manager.services.health.docker"):
            monitor = HealthMonitor(registry=registry)
        assert monitor.registry is registry

    def test_init_creates_default_registry(self):
        """Verify HealthMonitor creates ServiceRegistry when none provided"""
        with (
            patch("homelab_manager.services.health.docker"),
            patch("homelab_manager.services.health.ServiceRegistry") as mock_reg_cls,
        ):
            HealthMonitor()
            mock_reg_cls.assert_called_once()

    def test_init_docker_client_set_on_success(self):
        """Verify docker_client is set when Docker is available"""
        mock_client = Mock()
        with patch("homelab_manager.services.health.docker") as mock_docker:
            mock_docker.from_env.return_value = mock_client
            monitor = HealthMonitor(registry=make_registry())
        assert monitor.docker_client is mock_client

    def test_init_docker_client_none_on_failure(self):
        """Verify docker_client is None when Docker is unavailable"""
        with patch("homelab_manager.services.health.docker") as mock_docker:
            mock_docker.from_env.side_effect = Exception("Docker not available")
            monitor = HealthMonitor(registry=make_registry())
        assert monitor.docker_client is None

    def test_init_timeout_default(self):
        """Verify default timeout is 5 seconds"""
        monitor = make_monitor(registry=make_registry())
        assert monitor.timeout == 5


class TestCheckService:
    """Tests for HealthMonitor.check_service()"""

    def test_check_service_returns_healthy_on_200(self):
        """Verify check_service returns healthy=True for HTTP 200"""
        monitor = make_monitor(registry=make_registry())

        mock_response = Mock()
        mock_response.status_code = 200

        with patch(
            "homelab_manager.services.health.requests.get", return_value=mock_response
        ):
            result = monitor.check_service("grafana", "http://localhost:3000")

        assert result["healthy"] is True
        assert result["status_code"] == 200
        assert result["error"] is None
        assert result["source"] == "http"

    def test_check_service_returns_unhealthy_on_500(self):
        """Verify check_service returns healthy=False for HTTP 500"""
        monitor = make_monitor(registry=make_registry())

        mock_response = Mock()
        mock_response.status_code = 500

        with patch(
            "homelab_manager.services.health.requests.get", return_value=mock_response
        ):
            result = monitor.check_service("grafana", "http://localhost:3000")

        assert result["healthy"] is False
        assert result["status_code"] == 500

    def test_check_service_custom_expected_statuses(self):
        """Verify check_service respects custom expected_statuses"""
        monitor = make_monitor(registry=make_registry())

        mock_response = Mock()
        mock_response.status_code = 302

        with patch(
            "homelab_manager.services.health.requests.get", return_value=mock_response
        ):
            result = monitor.check_service(
                "app", "http://localhost:8080", expected_statuses=[200, 302]
            )

        assert result["healthy"] is True

    def test_check_service_connection_error(self):
        """Verify check_service returns healthy=False on connection error"""
        monitor = make_monitor(registry=make_registry())

        with patch(
            "homelab_manager.services.health.requests.get",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            result = monitor.check_service("grafana", "http://localhost:3000")

        assert result["healthy"] is False
        assert result["error"] is not None
        assert result["source"] == "http"

    def test_check_service_timeout_error(self):
        """Verify check_service returns healthy=False on timeout"""
        monitor = make_monitor(registry=make_registry())

        with patch(
            "homelab_manager.services.health.requests.get",
            side_effect=requests.exceptions.Timeout("timed out"),
        ):
            result = monitor.check_service("grafana", "http://localhost:3000")

        assert result["healthy"] is False
        assert result["error"] is not None

    def test_check_service_result_has_required_keys(self):
        """Verify check_service result contains all required keys"""
        monitor = make_monitor(registry=make_registry())

        mock_response = Mock()
        mock_response.status_code = 200

        with patch(
            "homelab_manager.services.health.requests.get", return_value=mock_response
        ):
            result = monitor.check_service("grafana", "http://localhost:3000")

        for key in (
            "healthy",
            "status_code",
            "response_time",
            "last_check",
            "error",
            "source",
        ):
            assert key in result

    def test_check_service_includes_response_time(self):
        """Verify check_service records a response_time on success"""
        monitor = make_monitor(registry=make_registry())

        mock_response = Mock()
        mock_response.status_code = 200

        with patch(
            "homelab_manager.services.health.requests.get", return_value=mock_response
        ):
            result = monitor.check_service("grafana", "http://localhost:3000")

        assert result["response_time"] is not None
        assert result["response_time"] >= 0


class TestCheckAllServices:
    """Tests for HealthMonitor.check_all_services()"""

    def test_check_all_services_returns_dict(self):
        """Verify check_all_services returns a dict"""
        registry = make_registry()
        monitor = make_monitor(registry=registry)

        result = monitor.check_all_services()

        assert isinstance(result, dict)

    def test_check_all_services_empty_when_no_services(self):
        """Verify check_all_services returns empty dict when registry has no services"""
        registry = make_registry(services=[])
        monitor = make_monitor(registry=registry)

        result = monitor.check_all_services()

        assert result == {}

    def test_check_all_services_skips_none_health_mode(self):
        """Verify check_all_services skips services with health_mode=none"""
        mock_service = Mock()
        mock_service.id = "internal"
        mock_service.health_mode = "none"

        registry = make_registry(services=[mock_service])
        monitor = make_monitor(registry=registry)

        result = monitor.check_all_services()

        assert "internal" not in result

    def test_check_all_services_includes_checked_services(self):
        """Verify check_all_services includes results for checked services"""
        mock_service = Mock()
        mock_service.id = "grafana"
        mock_service.container_name = "grafana"
        mock_service.health_mode = "docker"
        mock_service.health_url = None
        mock_service.expected_statuses = [200]

        registry = make_registry(services=[mock_service])

        with patch("homelab_manager.services.health.docker") as mock_docker:
            mock_client = Mock()
            mock_docker.from_env.return_value = mock_client
            mock_container = Mock()
            mock_container.attrs = {"State": {"Status": "running"}}
            mock_client.containers.get.return_value = mock_container

            monitor = HealthMonitor(registry=registry)
            result = monitor.check_all_services()

        assert "grafana" in result


class TestGetHealthSummary:
    """Tests for HealthMonitor.get_health_summary()"""

    def test_get_health_summary_returns_dict(self):
        """Verify get_health_summary returns a dict"""
        registry = make_registry()
        monitor = make_monitor(registry=registry)

        result = monitor.get_health_summary()

        assert isinstance(result, dict)

    def test_get_health_summary_has_required_keys(self):
        """Verify get_health_summary includes required keys"""
        registry = make_registry()
        monitor = make_monitor(registry=registry)

        result = monitor.get_health_summary()

        for key in (
            "total_services",
            "healthy_services",
            "unhealthy_services",
            "health_percentage",
            "services",
        ):
            assert key in result

    def test_get_health_summary_zero_services(self):
        """Verify get_health_summary handles empty service list"""
        registry = make_registry(services=[])
        monitor = make_monitor(registry=registry)

        result = monitor.get_health_summary()

        assert result["total_services"] == 0
        assert result["health_percentage"] == 0

    def test_get_health_summary_counts_match(self):
        """Verify healthy + unhealthy counts equal total"""
        registry = make_registry(services=[])
        monitor = make_monitor(registry=registry)

        with patch.object(monitor, "check_all_services") as mock_check:
            mock_check.return_value = {
                "grafana": {"healthy": True},
                "broken-svc": {"healthy": False},
            }
            result = monitor.get_health_summary()

        assert result["total_services"] == 2
        assert result["healthy_services"] == 1
        assert result["unhealthy_services"] == 1


class TestGetUnhealthyServices:
    """Tests for HealthMonitor.get_unhealthy_services()"""

    def test_get_unhealthy_services_returns_list(self):
        """Verify get_unhealthy_services returns a list"""
        registry = make_registry()
        monitor = make_monitor(registry=registry)

        result = monitor.get_unhealthy_services()

        assert isinstance(result, list)

    def test_get_unhealthy_services_empty_when_all_healthy(self):
        """Verify get_unhealthy_services returns empty list when all services healthy"""
        registry = make_registry()
        monitor = make_monitor(registry=registry)

        with patch.object(monitor, "check_all_services") as mock_check:
            mock_check.return_value = {
                "grafana": {"healthy": True},
                "prometheus": {"healthy": True},
            }
            result = monitor.get_unhealthy_services()

        assert result == []

    def test_get_unhealthy_services_lists_failing_services(self):
        """Verify get_unhealthy_services returns IDs of unhealthy services"""
        registry = make_registry()
        monitor = make_monitor(registry=registry)

        with patch.object(monitor, "check_all_services") as mock_check:
            mock_check.return_value = {
                "grafana": {"healthy": True},
                "broken-svc": {"healthy": False},
                "also-broken": {"healthy": False},
            }
            result = monitor.get_unhealthy_services()

        assert "broken-svc" in result
        assert "also-broken" in result
        assert "grafana" not in result
        assert len(result) == 2


class TestCheckServiceById:
    """Tests for HealthMonitor.check_service_by_id()"""

    def test_check_service_by_id_returns_none_for_unknown(self):
        """Verify check_service_by_id returns None for unknown service"""
        registry = make_registry()
        registry.get_service.return_value = None

        monitor = make_monitor(registry=registry)
        result = monitor.check_service_by_id("nonexistent")

        assert result is None

    def test_check_service_by_id_returns_dict_for_known_service(self):
        """Verify check_service_by_id returns result dict for known service"""
        mock_service = Mock()
        mock_service.id = "grafana"
        mock_service.container_name = "grafana"
        mock_service.health_mode = "docker"
        mock_service.health_url = None
        mock_service.expected_statuses = [200]

        registry = make_registry()
        registry.get_service.return_value = mock_service

        with patch("homelab_manager.services.health.docker") as mock_docker:
            mock_client = Mock()
            mock_docker.from_env.return_value = mock_client
            mock_container = Mock()
            mock_container.attrs = {"State": {"Status": "running"}}
            mock_client.containers.get.return_value = mock_container

            monitor = HealthMonitor(registry=registry)
            result = monitor.check_service_by_id("grafana")

        assert result is not None
        assert "healthy" in result

    def test_check_service_by_id_calls_registry_get_service(self):
        """Verify check_service_by_id queries the registry"""
        registry = make_registry()
        registry.get_service.return_value = None

        monitor = make_monitor(registry=registry)
        monitor.check_service_by_id("grafana")

        registry.get_service.assert_called_once_with("grafana")
