#!/usr/bin/env python3
"""
Unit tests for homelab_manager.services.deployment.
"""

import subprocess
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
    def test_success_attaches_message(self, manager):
        result = manager.deploy()
        assert result["success"] is True
        assert "deployed successfully" in result["message"]

    def test_failure_propagates_error(self, manager, mock_cli):
        mock_cli.run.side_effect = subprocess.CalledProcessError(
            1, "docker compose up", stderr="network unavailable"
        )
        mock_cli.scrub_error.return_value = "deployment failed (CalledProcessError)"
        result = manager.deploy()
        assert result["success"] is False
        assert result["error"] == "deployment failed (CalledProcessError)"
        assert "message" not in result
        mock_cli.scrub_error.assert_called_once()

    def test_uses_project_root_as_cwd(self, manager, mock_cli):
        manager.deploy()
        mock_cli.run.assert_called_once_with(["up", "-d"], cwd=manager.project_root)


class TestRestartService:
    def test_success_attaches_message_with_service_name(self, manager):
        result = manager.restart_service("grafana")
        assert result["success"] is True
        assert "grafana restarted successfully" in result["message"]

    def test_command_includes_service_name(self, manager, mock_cli):
        manager.restart_service("caddy")
        args, _ = mock_cli.run.call_args
        assert "caddy" in args[0]

    def test_failure_propagates_error(self, manager, mock_cli):
        mock_cli.run.side_effect = subprocess.CalledProcessError(
            1, "docker compose restart", stderr="no such service"
        )
        mock_cli.scrub_error.return_value = "restart 'phantom' failed (CalledProcessError)"
        result = manager.restart_service("phantom")
        assert result["success"] is False
        assert result["error"] == "restart 'phantom' failed (CalledProcessError)"
        mock_cli.scrub_error.assert_called_once()

    @pytest.mark.parametrize(
        "service_name",
        ["grafana", "homepage", "n8n", "homeassistant", "service-with-dashes"],
    )
    def test_various_service_names_pass_through(self, manager, mock_cli, service_name):
        manager.restart_service(service_name)
        args, _ = mock_cli.run.call_args
        assert service_name in args[0]
