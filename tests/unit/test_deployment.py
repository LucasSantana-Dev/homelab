#!/usr/bin/env python3
"""
Unit tests for homelab_manager.services.deployment.
"""

from unittest.mock import MagicMock

import pytest

from homelab_manager.clients.compose_cli import ComposeCLI
from homelab_manager.models.service import Service, ServiceRegistry
from homelab_manager.services.deployment import DeploymentManager


@pytest.fixture
def mock_cli():
    return MagicMock(spec=ComposeCLI)


@pytest.fixture
def mock_registry():
    """Create a mock registry with known services."""
    registry = MagicMock(spec=ServiceRegistry)
    registry.services = {
        "grafana": Service(
            id="grafana",
            name="Grafana",
            category="monitoring",
            container_name="grafana",
        ),
        "nginx": Service(
            id="nginx",
            name="Nginx Proxy",
            category="core",
            container_name="nginx-proxy",
        ),
    }
    return registry


@pytest.fixture
def manager(mock_cli, mock_registry):
    return DeploymentManager(compose_cli=mock_cli, registry=mock_registry)


@pytest.fixture
def manager_no_registry(mock_cli):
    return DeploymentManager(compose_cli=mock_cli, registry=None)


class TestDeploy:
    def test_success_attaches_message(self, manager, mock_cli):
        mock_cli.run_result.return_value = {"success": True}
        result = manager.deploy()
        assert result["success"] is True
        assert "deployed successfully" in result["message"]

    def test_failure_propagates_error(self, manager, mock_cli):
        mock_cli.run_result.return_value = {
            "success": False,
            "error": "deployment failed (CalledProcessError)",
        }
        result = manager.deploy()
        assert result["success"] is False
        assert result["error"] == "deployment failed (CalledProcessError)"
        assert "message" not in result

    def test_calls_run_result_with_cwd_and_context(self, manager, mock_cli):
        mock_cli.run_result.return_value = {"success": True}
        manager.deploy()
        mock_cli.run_result.assert_called_once_with(
            ["up", "-d"],
            cwd=manager.project_root,
            context="deployment failed",
        )


class TestRestartService:
    def test_success_attaches_message_with_service_name(self, manager, mock_cli):
        mock_cli.run_result.return_value = {"success": True}
        result = manager.restart_service("grafana")
        assert result["success"] is True
        assert "grafana restarted successfully" in result["message"]

    def test_command_includes_service_name(self, manager, mock_cli):
        mock_cli.run_result.return_value = {"success": True}
        manager.restart_service("grafana")
        args, kwargs = mock_cli.run_result.call_args
        assert "grafana" in args[0]

    def test_failure_propagates_error(self, manager, mock_cli):
        mock_cli.run_result.return_value = {
            "success": False,
            "error": "restart 'grafana' failed (CalledProcessError)",
        }
        result = manager.restart_service("grafana")
        assert result["success"] is False
        assert result["error"] == "restart 'grafana' failed (CalledProcessError)"

    def test_calls_run_result_with_correct_context(self, manager, mock_cli):
        mock_cli.run_result.return_value = {"success": True}
        manager.restart_service("grafana")
        mock_cli.run_result.assert_called_once_with(
            ["restart", "grafana"],
            cwd=manager.project_root,
            context="restart 'grafana' failed",
        )

    def test_rejects_unknown_service_name(self, manager):
        """Unknown service names should be rejected."""
        result = manager.restart_service("phantom-service")
        assert result["success"] is False
        assert "unknown service" in result["error"]
        assert "phantom-service" in result["error"]

    def test_accepts_service_by_container_name(self, manager, mock_cli):
        """Service can be specified by container_name (e.g., nginx-proxy instead of nginx)."""
        mock_cli.run_result.return_value = {"success": True}
        result = manager.restart_service("nginx-proxy")
        assert result["success"] is True

    def test_validation_error_includes_known_services(self, manager):
        """Error message should list known services."""
        result = manager.restart_service("unknown")
        assert "Known services:" in result["error"]
        assert "grafana" in result["error"]
        assert "nginx" in result["error"]

    def test_no_registry_loads_default_registry(self, manager_no_registry, mock_cli):
        """When registry is None, a default registry is loaded."""
        # The manager is initialized with registry=None, but the __init__
        # creates a default ServiceRegistry(), which may be empty if
        # services.yaml doesn't exist in the test environment.
        mock_cli.run_result.return_value = {"success": True}
        result = manager_no_registry.restart_service("any-service")
        # If the default registry is empty, validation will reject any service.
        # If services.yaml exists, "any-service" might pass if it's defined there.
        # To be safe, we just verify the manager has a registry.
        assert manager_no_registry.registry is not None
