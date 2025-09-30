"""
Unit tests for health monitoring
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager.health import HomelabHealthMonitor


class TestHomelabHealthMonitor:
    """Test cases for HomelabHealthMonitor class"""

    def test_init(self, temp_homelab_dir, mock_docker_client):
        """Test HomelabHealthMonitor initialization"""
        with patch(
            "homelab_manager.health.docker.from_env", return_value=mock_docker_client
        ):
            monitor = HomelabHealthMonitor()

            assert monitor.homelab_dir == temp_homelab_dir
            assert monitor.log_dir == temp_homelab_dir / "logs"
            assert len(monitor.services) == 4  # Homepage, HA, Grafana, Portainer

    def test_check_service_health_success(self, mock_requests):
        """Test successful service health check"""
        with patch("homelab_manager.health.docker.from_env"):
            monitor = HomelabHealthMonitor()
            is_healthy, details = monitor.check_service_health(
                "Test Service", "http://localhost:3000"
            )

            assert is_healthy is True
            assert "Status 200" in details

    def test_check_service_health_failure(self, temp_homelab_dir):
        """Test failed service health check"""
        with patch("homelab_manager.health.docker.from_env"), patch(
            "requests.get", side_effect=Exception("Connection failed")
        ):

            monitor = HomelabHealthMonitor()
            is_healthy, details = monitor.check_service_health(
                "Test Service", "http://localhost:9999"
            )

            assert is_healthy is False
            assert "Connection failed" in details

    def test_check_system_resources(self, mock_psutil):
        """Test system resource checking"""
        with patch("homelab_manager.health.docker.from_env"):
            monitor = HomelabHealthMonitor()
            resources = monitor.check_system_resources()

            assert "cpu_percent" in resources
            assert "memory_percent" in resources
            assert "disk_percent" in resources
            assert resources["cpu_percent"] == 25.0
            assert resources["memory_percent"] == 50.0
            assert resources["disk_percent"] == 30.0

    def test_check_docker_containers(self, mock_docker_client):
        """Test Docker container checking"""
        with patch(
            "homelab_manager.health.docker.from_env", return_value=mock_docker_client
        ):
            monitor = HomelabHealthMonitor()
            containers = monitor.check_docker_containers()

            assert len(containers) == 1
            assert containers[0]["name"] == "test-container"
            assert containers[0]["status"] == "running"
            assert containers[0]["image"] == "test/image:latest"
            assert "8080:80" in containers[0]["ports"]
            assert "8443:443" in containers[0]["ports"]

    def test_check_docker_containers_no_ports(self, temp_homelab_dir):
        """Test Docker container checking with no ports"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.status = "running"
        mock_container.image.tags = ["test/image:latest"]
        mock_container.ports = {}  # No ports

        mock_client.containers.list.return_value = [mock_container]

        with patch("homelab_manager.health.docker.from_env", return_value=mock_client):
            monitor = HomelabHealthMonitor()
            containers = monitor.check_docker_containers()

            assert len(containers) == 1
            assert containers[0]["ports"] == []

    def test_check_docker_containers_none_ports(self, temp_homelab_dir):
        """Test Docker container checking with None ports"""
        mock_client = Mock()
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_container.status = "running"
        mock_container.image.tags = ["test/image:latest"]
        mock_container.ports = None  # None ports

        mock_client.containers.list.return_value = [mock_container]

        with patch("homelab_manager.health.docker.from_env", return_value=mock_client):
            monitor = HomelabHealthMonitor()
            containers = monitor.check_docker_containers()

            assert len(containers) == 1
            assert containers[0]["ports"] == []

    def test_run_health_check(
        self, mock_docker_client, mock_requests, mock_psutil, capsys
    ):
        """Test full health check execution"""
        with patch(
            "homelab_manager.health.docker.from_env", return_value=mock_docker_client
        ):
            monitor = HomelabHealthMonitor()
            monitor.run_health_check()

            captured = capsys.readouterr()
            assert "Homelab Health Check" in captured.out
            assert "System Resources" in captured.out
            assert "Docker Containers" in captured.out
            assert "Service Health" in captured.out

    def test_quick_status(self, mock_docker_client, mock_requests, mock_psutil, capsys):
        """Test quick status display"""
        with patch(
            "homelab_manager.health.docker.from_env", return_value=mock_docker_client
        ):
            monitor = HomelabHealthMonitor()
            monitor.quick_status()

            captured = capsys.readouterr()
            assert "Homelab Quick Status" in captured.out
            assert "Containers:" in captured.out
            assert "Resources:" in captured.out
            assert "Services:" in captured.out
