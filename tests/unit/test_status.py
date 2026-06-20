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

from homelab_manager.clients.docker_client import DockerClientFactory
from homelab_manager.services.status import StatusManager


@pytest.fixture(autouse=True)
def _reset_docker_singleton():
    """R1 Phase C: docker client is now a module-singleton; reset per-test."""
    DockerClientFactory._instance = None
    yield
    DockerClientFactory._instance = None


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
    # R1 Phase C: patch the canonical seam in the factory module so
    # `StatusManager.__init__ → get_docker_client()` returns the mock.
    with patch("homelab_manager.clients.docker_client.docker") as mock_docker:
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

    def test_one_bad_container_does_not_truncate_rest(self, manager_with_mocked_docker):
        """#214: a container that fails to process is skipped, not silently
        dropping every container after it (which would make a partial list look
        like a complete result)."""
        m, client = manager_with_mocked_docker
        m.registry = MagicMock()
        m.registry.get_service_by_container.return_value = None

        good1 = make_container("good1")
        good2 = make_container("good2")

        class _BadContainer:
            name = "boom"
            status = "running"

            @property
            def image(self):  # accessed mid-body → raises for this one only
                raise RuntimeError("unreadable")

        client.containers.list.return_value = [good1, _BadContainer(), good2]

        with patch.object(m, "_is_homelab_container", return_value=True):
            result = m.get_container_status()

        names = {c["name"] for c in result}
        assert names == {"good1", "good2"}  # bad skipped, good2 NOT truncated

    def test_none_docker_client_returns_empty_with_error(self, capsys):
        """No daemon → empty + explicit error, never confused with 'no containers'."""
        m = StatusManager()
        m.docker_client = None
        assert m.get_container_status() == []
        assert "Docker daemon is unreachable" in capsys.readouterr().out


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
    """After H6+M1 hardening: registry validation + exception scrubbing."""

    @pytest.fixture
    def manager_with_registry(self):
        """StatusManager with a mocked registry that allow-lists 'grafana'."""
        with patch("homelab_manager.clients.docker_client.docker") as mock_docker:
            mock_client = MagicMock()
            mock_docker.from_env.return_value = mock_client
            m = StatusManager()
            m.docker_client = mock_client
            registry = MagicMock()
            # Pretend 'grafana' is registered; everything else is unknown.
            registry.get_service_by_container.side_effect = lambda n: (
                object() if n == "grafana" else None
            )
            registry.get_service.side_effect = lambda n: (
                object() if n == "grafana" else None
            )
            # Add services dict for validation: grafana is known by id and container_name
            grafana_service = MagicMock()
            grafana_service.id = "grafana"
            grafana_service.container_name = "grafana"
            registry.services = {"grafana": grafana_service}
            m.registry = registry
            yield m

    def test_unknown_service_rejected(self, manager_with_registry):
        result = manager_with_registry.get_service_logs("ghost")
        assert "unknown service 'ghost'" in result

    def test_unknown_service_does_not_invoke_subprocess(self, manager_with_registry):
        with patch("subprocess.run") as mock_run:
            manager_with_registry.get_service_logs("ghost")
            mock_run.assert_not_called()

    def test_negative_lines_rejected(self, manager_with_registry):
        # 'grafana' is allowed; lines=-5 should be rejected by max(1, ...).
        # Actually max(1, ...) clamps to 1, NOT rejects — so this exercises clamp path.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            manager_with_registry.get_service_logs("grafana", lines=-5)
            cmd = mock_run.call_args.args[0]
            assert cmd[cmd.index("--tail") + 1] == "1"  # clamped

    def test_huge_lines_capped(self, manager_with_registry):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            manager_with_registry.get_service_logs("grafana", lines=999_999)
            cmd = mock_run.call_args.args[0]
            assert cmd[cmd.index("--tail") + 1] == "10000"  # capped

    def test_non_integer_lines_rejected(self, manager_with_registry):
        result = manager_with_registry.get_service_logs("grafana", lines="not-a-number")
        assert "must be a positive integer" in result

    def test_success_returns_stdout(self, manager_with_registry):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="log line\n", stderr=""
            )
            assert manager_with_registry.get_service_logs("grafana") == "log line\n"

    def test_default_tail_is_50(self, manager_with_registry):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            manager_with_registry.get_service_logs("grafana")
            cmd = mock_run.call_args.args[0]
            assert cmd[cmd.index("--tail") + 1] == "50"

    def test_custom_tail_propagates(self, manager_with_registry):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            manager_with_registry.get_service_logs("grafana", lines=200)
            cmd = mock_run.call_args.args[0]
            assert cmd[cmd.index("--tail") + 1] == "200"

    def test_called_process_error_does_not_leak_stderr(self, manager_with_registry):
        """M1 hardening: stderr from docker must not be echoed to caller."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                returncode=1, cmd=[], stderr="auth-token=super-secret-leak"
            ),
        ):
            result = manager_with_registry.get_service_logs("grafana")
            assert "super-secret-leak" not in result
            assert "grafana" in result  # service name is fine to echo

    def test_generic_exception_returns_type_only(self, manager_with_registry):
        with patch("subprocess.run", side_effect=FileNotFoundError("missing docker")):
            result = manager_with_registry.get_service_logs("grafana")
            assert "missing docker" not in result  # raw message not echoed
            assert "FileNotFoundError" in result


class TestGetContainerStatusErrorScrubbing:
    """M1: get_container_status should not leak Docker SDK exception detail."""

    def test_docker_failure_message_scrubbed(self, manager_with_mocked_docker, capsys):
        m, client = manager_with_mocked_docker
        client.containers.list.side_effect = RuntimeError(
            "connection refused on /var/run/docker.sock with token=ABC123"
        )
        m.get_container_status()
        out = capsys.readouterr().out
        assert "token=ABC123" not in out
        assert "RuntimeError" in out  # type only
