#!/usr/bin/env python3
"""
Unit tests for homelab_manager.services.deployment (audit-deep H7).
"""

from unittest.mock import patch

import pytest

from homelab_manager.services.deployment import DeploymentManager


@pytest.fixture
def manager():
    return DeploymentManager()


class TestDeploy:
    def test_success_attaches_message(self, manager):
        with patch("homelab_manager.services.deployment.CommandSequence") as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}
            result = manager.deploy()
            assert result["success"] is True
            assert "deployed successfully" in result["message"]

    def test_failure_no_message(self, manager):
        with patch("homelab_manager.services.deployment.CommandSequence") as mock_seq:
            mock_seq.return_value.run.return_value = {
                "success": False,
                "error": "docker compose up failed: network unavailable",
            }
            result = manager.deploy()
            assert result["success"] is False
            assert "network unavailable" in result["error"]
            assert "message" not in result

    def test_uses_project_root_as_cwd(self, manager):
        captured = {}
        with patch("homelab_manager.services.deployment.CommandSequence") as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}

            def remember(steps, cwd=None):
                captured["cwd"] = cwd
                captured["steps"] = steps
                return mock_seq.return_value

            mock_seq.side_effect = remember
            manager.deploy()
            assert captured["cwd"] == manager.project_root
            assert captured["steps"][0].cmd == ["docker", "compose", "up", "-d"]
            assert captured["steps"][0].label == "docker compose up"


class TestRestartService:
    def test_success_attaches_message_with_service_name(self, manager):
        with patch("homelab_manager.services.deployment.CommandSequence") as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}
            result = manager.restart_service("grafana")
            assert result["success"] is True
            assert "grafana restarted successfully" in result["message"]

    def test_command_includes_service_name(self, manager):
        captured = {}
        with patch("homelab_manager.services.deployment.CommandSequence") as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}

            def remember(steps, cwd=None):
                captured["steps"] = steps
                return mock_seq.return_value

            mock_seq.side_effect = remember
            manager.restart_service("caddy")
            step = captured["steps"][0]
            assert step.cmd == ["docker", "compose", "restart", "caddy"]
            assert step.label == "restart caddy"

    def test_failure_propagates_error(self, manager):
        with patch("homelab_manager.services.deployment.CommandSequence") as mock_seq:
            mock_seq.return_value.run.return_value = {
                "success": False,
                "error": "restart phantom failed: no such service",
            }
            result = manager.restart_service("phantom")
            assert result["success"] is False
            assert "no such service" in result["error"]

    @pytest.mark.parametrize(
        "service_name",
        ["grafana", "homepage", "n8n", "homeassistant", "service-with-dashes"],
    )
    def test_various_service_names_pass_through(self, manager, service_name):
        captured = {}
        with patch("homelab_manager.services.deployment.CommandSequence") as mock_seq:
            mock_seq.return_value.run.return_value = {"success": True}

            def remember(steps, cwd=None):
                captured["cmd"] = steps[0].cmd
                return mock_seq.return_value

            mock_seq.side_effect = remember
            manager.restart_service(service_name)
            assert service_name in captured["cmd"]
