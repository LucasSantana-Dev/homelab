#!/usr/bin/env python3
"""
Unit tests for homelab_manager.services.status (audit-deep H7).

StatusManager touches the Docker SDK + subprocess; tests inject a mocked
docker client and patch subprocess for log retrieval.
"""

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from homelab_manager.services.status import StatusManager


def make_container(name, status="running", image_tags=None, health_status=None):
    container = MagicMock()
    container.name = name
    container.status = status
    container.image.tags = image_tags if image_tags is not None else [f"{name}:latest"]
    if health_status is not None:
        container.attrs = {"State": {"Health": {"Status": health_status}}}
    else:
        container.attrs = {"State": {}}
    return container


@pytest.fixture
def manager_with_mocked_docker():
    with patch("homelab_manager.services.status.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        m = StatusManager()
        m.docker_client = mock_client
        yield m, mock_client


class TestGetContainerStatus:
    def test_returns_empty_when_no_containers(self, manager_with_mocked_docker):
        m, client = manager_with_mocked_docker
        client.containers.list.return_value = []
        assert m.get_container_status() == []

    def test_known_service_populates_metadata(self, manager_with_mocked_docker):
        m, client = manager_with_mocked_docker
        fake_service = SimpleNamespace(
            name="Grafana", category="monitoring", port=3000, sensitive=False
        )
        m.registry = MagicMock()
        m.registry.get_service_by_container.return_value = fake_service

        container = make_container("grafana", health_status="healthy")
        client.containers.list.return_value = [container]
        client.containers.get.return_value = container

        result = m.get_container_status()
        assert len(result) == 1
        item = result[0]
        assert item["name"] == "grafana"
        assert item["service_name"] == "Grafana"
        assert item["category"] == "monitoring"
        assert item["port"] == 3000
        assert item["status"] == "running"
        assert item["health"] == "healthy"

    def test_unknown_homelab_container_falls_back(self, manager_with_mocked_docker):
        m, client = manager_with_mocked_docker
        m.registry = MagicMock()
        # Service lookup returns None (unknown)
        m.registry.get_service_by_container.return_value = None

        container = make_container("rogue-svc")
        client.containers.list.return_value = [container]
        # _is_homelab_container uses the registry too — returns None -> not a
        # homelab container, so it should be filtered out.
        result = m.get_container_status()
        assert result == []

    def test_docker_exception_is_caught(self, manager_with_mocked_docker, capsys):
        m, client = manager_with_mocked_docker
        client.containers.list.side_effect = RuntimeError("docker daemon down")
        result = m.get_container_status()
        assert result == []
        out = capsys.readouterr().out
        assert "Error getting container status" in out


class TestCheckContainerHealth:
    def test_stopped_container_returns_stopped(self, manager_with_mocked_docker):
        m, client = manager_with_mocked_docker
        container = make_container("c", status="exited")
        client.containers.get.return_value = container
        assert m._check_container_health("c") == "stopped"

    def test_healthcheck_status_propagates(self, manager_with_mocked_docker):
        m, client = manager_with_mocked_docker
        container = make_container("c", status="running", health_status="healthy")
        client.containers.get.return_value = container
        assert m._check_container_health("c") == "healthy"

    def test_running_without_healthcheck_returns_running(
        self, manager_with_mocked_docker
    ):
        m, client = manager_with_mocked_docker
        container = make_container("c", status="running", health_status=None)
        client.containers.get.return_value = container
        assert m._check_container_health("c") == "running"

    def test_missing_container_returns_unknown(self, manager_with_mocked_docker):
        m, client = manager_with_mocked_docker
        client.containers.get.side_effect = Exception("not found")
        assert m._check_container_health("c") == "unknown"


class TestGetServiceLogs:
    def test_success_returns_stdout(self, manager_with_mocked_docker):
        m, _ = manager_with_mocked_docker
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="log line\n", stderr=""
            )
            assert m.get_service_logs("grafana") == "log line\n"

    def test_default_tail_is_50(self, manager_with_mocked_docker):
        m, _ = manager_with_mocked_docker
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            m.get_service_logs("grafana")
            cmd = mock_run.call_args.args[0]
            assert "--tail" in cmd
            tail_idx = cmd.index("--tail")
            assert cmd[tail_idx + 1] == "50"

    def test_custom_tail_propagates(self, manager_with_mocked_docker):
        m, _ = manager_with_mocked_docker
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            m.get_service_logs("grafana", lines=200)
            cmd = mock_run.call_args.args[0]
            tail_idx = cmd.index("--tail")
            assert cmd[tail_idx + 1] == "200"

    def test_called_process_error_returns_error_message(
        self, manager_with_mocked_docker
    ):
        m, _ = manager_with_mocked_docker
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                returncode=1, cmd=[], stderr="no such service"
            ),
        ):
            result = m.get_service_logs("ghost")
            assert "Error getting logs" in result
            assert "no such service" in result

    def test_generic_exception_returns_logs_error(self, manager_with_mocked_docker):
        m, _ = manager_with_mocked_docker
        with patch("subprocess.run", side_effect=FileNotFoundError("missing docker")):
            result = m.get_service_logs("any")
            assert "Logs error" in result
            assert "missing docker" in result
