#!/usr/bin/env python3
"""
Unit tests for homelab_manager.services.deployment.
"""

from unittest.mock import MagicMock

import pytest

from homelab_manager.clients.compose_cli import ComposeCLI
from homelab_manager.services.deployment import DeploymentManager


@pytest.fixture
def mock_cli():
    return MagicMock(spec=ComposeCLI)


@pytest.fixture
def manager(mock_cli):
    return DeploymentManager(compose_cli=mock_cli)


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
        manager.restart_service("caddy")
        args, kwargs = mock_cli.run_result.call_args
        assert "caddy" in args[0]

    def test_failure_propagates_error(self, manager, mock_cli):
        mock_cli.run_result.return_value = {
            "success": False,
            "error": "restart 'phantom' failed (CalledProcessError)",
        }
        result = manager.restart_service("phantom")
        assert result["success"] is False
        assert result["error"] == "restart 'phantom' failed (CalledProcessError)"

    def test_calls_run_result_with_correct_context(self, manager, mock_cli):
        mock_cli.run_result.return_value = {"success": True}
        manager.restart_service("grafana")
        mock_cli.run_result.assert_called_once_with(
            ["restart", "grafana"],
            cwd=manager.project_root,
            context="restart 'grafana' failed",
        )

    @pytest.mark.parametrize(
        "service_name",
        ["grafana", "homepage", "n8n", "homeassistant", "service-with-dashes"],
    )
    def test_various_service_names_pass_through(self, manager, mock_cli, service_name):
        mock_cli.run_result.return_value = {"success": True}
        manager.restart_service(service_name)
        args, kwargs = mock_cli.run_result.call_args
        assert service_name in args[0]
