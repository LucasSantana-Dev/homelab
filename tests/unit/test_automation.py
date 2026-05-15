"""
Unit tests for automation-stack related code.

Covers: config validation for automation services, deployment restart of
homeassistant, and HTTP health checks for automation endpoints.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from homelab_manager.clients.compose_cli import ComposeCLI
from homelab_manager.services.deployment import DeploymentManager
from homelab_manager.services.health import HealthMonitor
from homelab_manager.utils.validators import ConfigValidator


class TestConfigValidator:
    """Config validation used by automation service setup."""

    def test_valid_domain(self):
        assert ConfigValidator.validate_domain("home.example.com") is True

    def test_invalid_domain_empty(self):
        assert ConfigValidator.validate_domain("") is False

    def test_valid_ip(self):
        assert ConfigValidator.validate_ip("100.64.0.1") is True

    def test_invalid_ip(self):
        assert ConfigValidator.validate_ip("not-an-ip") is False

    def test_password_min_length_passes(self):
        assert ConfigValidator.validate_password("longpassword") is True

    def test_password_too_short_fails(self):
        assert ConfigValidator.validate_password("short", min_length=8) is False

    def test_is_configured_rejects_empty(self):
        assert ConfigValidator.is_configured("") is False

    def test_is_configured_rejects_known_placeholder(self):
        assert ConfigValidator.is_configured("your_domain.com") is False

    def test_is_configured_accepts_real_value(self):
        assert ConfigValidator.is_configured("real-secret-token") is True


class TestRestartAutomationService:
    """DeploymentManager.restart_service for automation-stack containers."""

    @pytest.fixture
    def mock_cli(self):
        return MagicMock(spec=ComposeCLI)

    @pytest.fixture
    def manager(self, mock_cli):
        return DeploymentManager(compose_cli=mock_cli)

    def test_restart_homeassistant_success(self, manager, mock_cli):
        result = manager.restart_service("homeassistant")
        assert result["success"] is True
        assert "homeassistant" in result["message"]
        args, _ = mock_cli.run.call_args
        assert "homeassistant" in args[0]

    def test_restart_homeassistant_failure(self, manager, mock_cli):
        mock_cli.run.side_effect = subprocess.CalledProcessError(
            1, "docker compose restart", stderr="service error"
        )
        result = manager.restart_service("homeassistant")
        assert result["success"] is False

    def test_restart_n8n_uses_correct_service_name(self, manager, mock_cli):
        manager.restart_service("n8n")
        args, _ = mock_cli.run.call_args
        assert "n8n" in args[0]


class TestHealthMonitorHTTP:
    """HealthMonitor.check_service for automation endpoints."""

    def _make_monitor(self):
        with patch(
            "homelab_manager.services.health.get_docker_client", return_value=None
        ):
            return HealthMonitor()

    def test_healthy_response(self):
        monitor = self._make_monitor()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch(
            "homelab_manager.services.health.requests.get", return_value=mock_resp
        ):
            result = monitor.check_service("homeassistant", "http://homeassistant:8123")
        assert result["healthy"] is True
        assert result["status_code"] == 200
        assert result["error"] is None

    def test_unexpected_status_is_unhealthy(self):
        monitor = self._make_monitor()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch(
            "homelab_manager.services.health.requests.get", return_value=mock_resp
        ):
            result = monitor.check_service("homeassistant", "http://homeassistant:8123")
        assert result["healthy"] is False

    def test_connection_error_returns_unhealthy(self):
        import requests as req_lib

        monitor = self._make_monitor()
        with patch(
            "homelab_manager.services.health.requests.get",
            side_effect=req_lib.exceptions.ConnectionError("refused"),
        ):
            result = monitor.check_service("homeassistant", "http://homeassistant:8123")
        assert result["healthy"] is False
        assert result["status_code"] is None
