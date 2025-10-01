#!/usr/bin/env python3
"""
Tests for homelab_manager.health module
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from homelab_manager.health import HomelabHealthMonitor


class TestHomelabHealthMonitor:
    """Test cases for HomelabHealthMonitor class"""

    def test_init_with_default_path(self):
        """Test initialization with default path"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor()

            assert monitor.homelab_dir == Path(__file__).parent.parent.parent
            assert monitor.log_dir == monitor.homelab_dir / "logs"
            assert monitor.docker_client is not None

    def test_init_with_custom_path(self):
        """Test initialization with custom path"""
        custom_path = "/custom/homelab"

        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor(custom_path)

            assert monitor.homelab_dir == Path(custom_path)
            assert monitor.log_dir == Path(custom_path) / "logs"

    def test_init_docker_not_available(self):
        """Test initialization when Docker is not available"""
        with patch('homelab_manager.health.docker.from_env', side_effect=Exception("Docker not available")):
            with patch('rich.console.Console.print') as mock_print:
                with patch('homelab_manager.health.sys.exit') as mock_exit:
                    HomelabHealthMonitor()

                    mock_print.assert_called_with("❌ Docker is not running or not accessible", style="red")
                    mock_exit.assert_called_with(1)

    def test_services_defined(self):
        """Test that services are properly defined"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor()

            expected_services = [
                ("Homepage", "http://localhost:3000"),
                ("Home Assistant", "http://localhost:8123"),
                ("Grafana", "http://localhost:3002"),
                ("Portainer", "http://localhost:9000"),
                ("Uptime Kuma", "http://localhost:3001"),
                ("Prometheus", "http://localhost:9091"),
                ("Node Exporter", "http://localhost:9100"),
                ("What's Up Docker", "http://localhost:3003"),
            ]

            assert monitor.services == expected_services

    def test_check_service_health_success(self):
        """Test successful service health check"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor()

            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                is_healthy, details = monitor.check_service_health("Test Service", "http://localhost:3000")

                assert is_healthy is True
                assert details == "Status 200"
                mock_get.assert_called_once_with("http://localhost:3000", timeout=5)

    def test_check_service_health_server_error(self):
        """Test service health check with server error"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor()

            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 500
                mock_get.return_value = mock_response

                is_healthy, details = monitor.check_service_health("Test Service", "http://localhost:3000")

                assert is_healthy is False
                assert details == "Status 500"

    def test_check_service_health_connection_error(self):
        """Test service health check with connection error"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor()

            with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Connection failed")):
                is_healthy, details = monitor.check_service_health("Test Service", "http://localhost:3000")

                assert is_healthy is False
                assert "Connection failed" in details

    def test_check_service_health_timeout(self):
        """Test service health check with timeout"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor()

            with patch('requests.get', side_effect=requests.exceptions.Timeout("Request timeout")):
                is_healthy, details = monitor.check_service_health("Test Service", "http://localhost:3000")

                assert is_healthy is False
                assert "Request timeout" in details

    def test_check_system_resources(self):
        """Test system resource checking"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_docker.return_value = Mock()

            monitor = HomelabHealthMonitor()

            with patch('homelab_manager.health.psutil.cpu_percent', return_value=50.0), \
                 patch('homelab_manager.health.psutil.virtual_memory') as mock_memory, \
                 patch('homelab_manager.health.psutil.disk_usage') as mock_disk:

                mock_memory.return_value.percent = 60.0
                mock_disk.return_value.percent = 70.0

                resources = monitor.check_system_resources()

                assert resources["cpu_percent"] == 50.0
                assert resources["memory_percent"] == 60.0
                assert resources["disk_percent"] == 70.0

    def test_check_docker_containers_success(self):
        """Test successful Docker container checking"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock container
            mock_container = Mock()
            mock_container.name = "test-container"
            mock_container.status = "running"
            mock_container.image.tags = ["test:latest"]
            mock_container.ports = {
                "80/tcp": [{"HostPort": "3000", "PrivatePort": "80"}]
            }

            mock_client.containers.list.return_value = [mock_container]

            monitor = HomelabHealthMonitor()
            containers = monitor.check_docker_containers()

            assert len(containers) == 1
            assert containers[0]["name"] == "test-container"
            assert containers[0]["status"] == "running"
            assert containers[0]["image"] == "test:latest"
            assert "3000:80" in containers[0]["ports"]

    def test_check_docker_containers_no_ports(self):
        """Test Docker container checking with no ports"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock container with no ports
            mock_container = Mock()
            mock_container.name = "test-container"
            mock_container.status = "running"
            mock_container.image.tags = ["test:latest"]
            mock_container.ports = {}

            mock_client.containers.list.return_value = [mock_container]

            monitor = HomelabHealthMonitor()
            containers = monitor.check_docker_containers()

            assert len(containers) == 1
            assert containers[0]["ports"] == []

    def test_check_docker_containers_exception(self):
        """Test Docker container checking with exception"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            mock_client.containers.list.side_effect = Exception("Docker error")

            with patch('rich.console.Console.print') as mock_print:
                monitor = HomelabHealthMonitor()
                containers = monitor.check_docker_containers()

                assert containers == []
                mock_print.assert_called_with("⚠️ Error checking containers: Docker error", style="yellow")

    def test_run_health_check(self):
        """Test comprehensive health check"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock container
            mock_container = Mock()
            mock_container.name = "test-container"
            mock_container.status = "running"
            mock_container.image.tags = ["test:latest"]
            mock_container.ports = {}

            mock_client.containers.list.return_value = [mock_container]

            with patch('homelab_manager.health.psutil.cpu_percent', return_value=50.0), \
                 patch('homelab_manager.health.psutil.virtual_memory') as mock_memory, \
                 patch('homelab_manager.health.psutil.disk_usage') as mock_disk, \
                 patch('homelab_manager.health.requests.get') as mock_get, \
                 patch('homelab_manager.health.console.print') as mock_print, \
                 patch('homelab_manager.health.time.strftime', return_value="2023-01-01 12:00:00"):

                mock_memory.return_value.percent = 60.0
                mock_disk.return_value.percent = 70.0

                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                monitor = HomelabHealthMonitor()
                monitor.run_health_check()

                # Should print various status messages
                assert mock_print.call_count > 0

    def test_quick_status(self):
        """Test quick status overview"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock containers
            mock_container1 = Mock()
            mock_container1.name = "container1"
            mock_container1.status = "running"

            mock_container2 = Mock()
            mock_container2.name = "container2"
            mock_container2.status = "stopped"

            mock_client.containers.list.return_value = [mock_container1, mock_container2]

            with patch('homelab_manager.health.psutil.cpu_percent', return_value=50.0), \
                 patch('homelab_manager.health.psutil.virtual_memory') as mock_memory, \
                 patch('homelab_manager.health.psutil.disk_usage') as mock_disk, \
                 patch('homelab_manager.health.requests.get') as mock_get, \
                 patch('homelab_manager.health.console.print') as mock_print:

                mock_memory.return_value.percent = 60.0
                mock_disk.return_value.percent = 70.0

                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                monitor = HomelabHealthMonitor()
                monitor.quick_status()

                # Should print status information
                assert mock_print.call_count > 0

    def test_quick_status_container_error(self):
        """Test quick status with container error"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            mock_client.containers.list.side_effect = Exception("Container error")

            with patch('homelab_manager.health.psutil.cpu_percent', return_value=50.0), \
                 patch('homelab_manager.health.psutil.virtual_memory') as mock_memory, \
                 patch('homelab_manager.health.psutil.disk_usage') as mock_disk, \
                 patch('homelab_manager.health.requests.get') as mock_get, \
                 patch('homelab_manager.health.console.print') as mock_print:

                mock_memory.return_value.percent = 60.0
                mock_disk.return_value.percent = 70.0

                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                monitor = HomelabHealthMonitor()
                monitor.quick_status()

                # Should handle error gracefully
                assert mock_print.call_count > 0

    def test_monitor_continuous(self):
        """Test continuous monitoring"""
        with patch('homelab_manager.health.docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            mock_client.containers.list.return_value = []

            with patch('homelab_manager.health.psutil.cpu_percent', return_value=50.0), \
                 patch('homelab_manager.health.psutil.virtual_memory') as mock_memory, \
                 patch('homelab_manager.health.psutil.disk_usage') as mock_disk, \
                 patch('homelab_manager.health.requests.get') as mock_get, \
                 patch('homelab_manager.health.console.print') as mock_print, \
                 patch('homelab_manager.health.subprocess.run') as mock_subprocess, \
                 patch('homelab_manager.health.time.sleep') as mock_sleep, \
                 patch('homelab_manager.health.time.strftime', return_value="2023-01-01 12:00:00"):

                mock_memory.return_value.percent = 60.0
                mock_disk.return_value.percent = 70.0

                mock_response = Mock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                # Simulate KeyboardInterrupt after first iteration
                mock_sleep.side_effect = KeyboardInterrupt()

                monitor = HomelabHealthMonitor()
                monitor.monitor_continuous(interval=1)

                # Should handle KeyboardInterrupt gracefully
                mock_print.assert_any_call("\n🛑 Monitoring stopped", style="yellow")

    def test_main_function_check(self):
        """Test main function with check action"""
        with patch('homelab_manager.health.HomelabHealthMonitor') as mock_monitor_class:
            mock_monitor = Mock()
            mock_monitor_class.return_value = mock_monitor

            with patch('argparse.ArgumentParser') as mock_parser:
                mock_args = Mock()
                mock_args.action = "check"
                mock_args.interval = 60
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.health import main
                main()

                mock_monitor.run_health_check.assert_called_once()

    def test_main_function_status(self):
        """Test main function with status action"""
        with patch('homelab_manager.health.HomelabHealthMonitor') as mock_monitor_class:
            mock_monitor = Mock()
            mock_monitor_class.return_value = mock_monitor

            with patch('argparse.ArgumentParser') as mock_parser:
                mock_args = Mock()
                mock_args.action = "status"
                mock_args.interval = 60
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.health import main
                main()

                mock_monitor.quick_status.assert_called_once()

    def test_main_function_monitor(self):
        """Test main function with monitor action"""
        with patch('homelab_manager.health.HomelabHealthMonitor') as mock_monitor_class:
            mock_monitor = Mock()
            mock_monitor_class.return_value = mock_monitor

            with patch('argparse.ArgumentParser') as mock_parser:
                mock_args = Mock()
                mock_args.action = "monitor"
                mock_args.interval = 30
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.health import main
                main()

                mock_monitor.monitor_continuous.assert_called_once_with(30)
