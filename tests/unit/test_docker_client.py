#!/usr/bin/env python3
"""Unit tests for homelab_manager.clients.docker_client (R1 Phase B).

The factory wraps `docker.from_env()` so services share one mock seam. Tests
exercise the happy path, the failure path, the singleton cache, and `reset()`.
"""

from unittest.mock import MagicMock, patch

import pytest

from homelab_manager.clients import docker_client as dc_module
from homelab_manager.clients.docker_client import DockerClientFactory, get_docker_client


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Each test starts with a fresh factory cache."""
    DockerClientFactory._instance = None
    yield
    DockerClientFactory._instance = None


class TestDockerClientFactory:
    def test_from_env_success_returns_client(self):
        with patch.object(dc_module, "docker") as mock_docker:
            fake_client = MagicMock()
            mock_docker.from_env.return_value = fake_client
            client = DockerClientFactory.instance().get_client()
            assert client is fake_client
            mock_docker.from_env.assert_called_once()

    def test_from_env_failure_returns_none(self):
        with patch.object(dc_module, "docker") as mock_docker:
            mock_docker.from_env.side_effect = RuntimeError("daemon down")
            client = DockerClientFactory.instance().get_client()
            assert client is None

    def test_is_available_true_when_client_obtained(self):
        with patch.object(dc_module, "docker") as mock_docker:
            mock_docker.from_env.return_value = MagicMock()
            assert DockerClientFactory.instance().is_available() is True

    def test_is_available_false_when_daemon_down(self):
        with patch.object(dc_module, "docker") as mock_docker:
            mock_docker.from_env.side_effect = OSError("no socket")
            assert DockerClientFactory.instance().is_available() is False

    def test_subsequent_calls_use_cache(self):
        with patch.object(dc_module, "docker") as mock_docker:
            mock_docker.from_env.return_value = MagicMock()
            f = DockerClientFactory.instance()
            f.get_client()
            f.get_client()
            f.get_client()
            mock_docker.from_env.assert_called_once()

    def test_reset_clears_cache_and_reprobes(self):
        with patch.object(dc_module, "docker") as mock_docker:
            mock_docker.from_env.return_value = MagicMock()
            f = DockerClientFactory.instance()
            f.get_client()
            f.reset()
            f.get_client()
            assert mock_docker.from_env.call_count == 2

    def test_instance_is_singleton(self):
        a = DockerClientFactory.instance()
        b = DockerClientFactory.instance()
        assert a is b


class TestGetDockerClient:
    def test_module_accessor_returns_same_as_factory(self):
        with patch.object(dc_module, "docker") as mock_docker:
            fake_client = MagicMock()
            mock_docker.from_env.return_value = fake_client
            assert get_docker_client() is fake_client
            # And reusing the helper hits the cached value.
            assert get_docker_client() is fake_client
            mock_docker.from_env.assert_called_once()

    def test_module_accessor_returns_none_on_failure(self):
        with patch.object(dc_module, "docker") as mock_docker:
            mock_docker.from_env.side_effect = Exception("boom")
            assert get_docker_client() is None
