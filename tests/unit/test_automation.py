"""
Unit tests for automation-stack related code.

Covers: config validation for automation services, deployment restart of
homeassistant, and HTTP health checks for automation endpoints.
"""

from unittest.mock import MagicMock, patch

import pytest

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

    def _run_restart(self, service_name: str, success: bool):
        captured = {}

        def fake_init(steps, cwd=None, **kw):
            captured["cwd"] = cwd
            captured["steps"] = steps
            obj = MagicMock()
            obj.run.return_value = {"success": success, "output": ""}
            return obj

        with patch(
            "homelab_manager.services.deployment.CommandSequence",
            side_effect=fake_init,
        ):
            dm = DeploymentManager()
            result = dm.restart_service(service_name)

        return result, captured

    def test_restart_homeassistant_success(self):
        result, captured = self._run_restart("homeassistant", success=True)
        assert result["success"] is True
        assert "homeassistant" in result["message"]
        step = captured["steps"][0]
        assert "homeassistant" in step.cmd

    def test_restart_homeassistant_failure(self):
        result, captured = self._run_restart("homeassistant", success=False)
        assert result["success"] is False

    def test_restart_n8n_uses_correct_service_name(self):
        result, captured = self._run_restart("n8n", success=True)
        step = captured["steps"][0]
        assert "n8n" in step.cmd


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
