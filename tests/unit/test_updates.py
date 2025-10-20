#!/usr/bin/env python3
"""
Tests for homelab_manager.updates module
"""

import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from homelab_manager.updates import HomelabUpdateManager


class TestHomelabUpdateManager:
    """Test cases for HomelabUpdateManager class"""

    def test_init(self):
        """Test initialization"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_docker.return_value = Mock()

            manager = HomelabUpdateManager()

            assert (
                manager.homelab_dir == Path(__file__).parent.parent.parent.parent.parent
            )
            assert manager.log_dir == manager.homelab_dir / "logs"
            assert manager.docker_client is not None

    def test_init_docker_not_available(self):
        """Test initialization when Docker is not available"""
        with patch(
            "homelab_manager.updates.docker.from_env",
            side_effect=Exception("Docker not available"),
        ):
            with patch("rich.console.Console.print") as mock_print:
                with patch("homelab_manager.updates.sys.exit") as mock_exit:
                    HomelabUpdateManager()

                    mock_print.assert_called_with(
                        "❌ Docker is not running or not accessible", style="red"
                    )
                    mock_exit.assert_called_with(1)

    def test_services_defined(self):
        """Test that services are properly defined"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_docker.return_value = Mock()

            manager = HomelabUpdateManager()

            expected_services = [
                "ghcr.io/home-assistant/home-assistant:stable",
                "ghcr.io/gethomepage/homepage:latest",
                "grafana/grafana-oss:latest",
                "portainer/portainer-ce:latest",
                "pihole/pihole:latest",
                "prom/prometheus:latest",
                "prom/node-exporter:latest",
                "louislam/uptime-kuma:1",
                "fmartinou/whats-up-docker:latest",
            ]

            assert manager.services == expected_services

    def test_check_image_updates_no_update(self):
        """Test checking for image updates when no update is available"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock current and latest images with same ID
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"

            mock_latest_image = Mock()
            mock_latest_image.short_id = "abc123"

            mock_client.images.get.return_value = mock_current_image
            mock_client.images.pull.return_value = mock_latest_image

            with patch("rich.console.Console.print") as mock_print:
                manager = HomelabUpdateManager()
                has_update, current_id, latest_id = manager.check_image_updates(
                    "test/image", "latest"
                )

                assert has_update is False
                assert current_id == "abc123"
                assert latest_id == "abc123"
                mock_print.assert_called_with(
                    "📥 Pulling latest image for test/image...", style="blue"
                )

    def test_check_image_updates_update_available(self):
        """Test checking for image updates when update is available"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock current and latest images with different IDs
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"

            mock_latest_image = Mock()
            mock_latest_image.short_id = "def456"

            mock_client.images.get.return_value = mock_current_image
            mock_client.images.pull.return_value = mock_latest_image

            with patch("rich.console.Console.print") as mock_print:
                manager = HomelabUpdateManager()
                has_update, current_id, latest_id = manager.check_image_updates(
                    "test/image", "latest"
                )

                assert has_update is True
                assert current_id == "abc123"
                assert latest_id == "def456"

    def test_check_image_updates_image_not_found(self):
        """Test checking for image updates when image is not found"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            mock_client.images.get.side_effect = Exception("Image not found")

            manager = HomelabUpdateManager()
            has_update, current_id, latest_id = manager.check_image_updates(
                "test/image", "latest"
            )

            assert has_update is False
            assert current_id == "Not found"
            assert latest_id == "Not found"

    def test_check_image_updates_error(self):
        """Test checking for image updates with error"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            mock_client.images.get.side_effect = Exception("Docker error")

            with patch("rich.console.Console.print") as mock_print:
                manager = HomelabUpdateManager()
                has_update, current_id, latest_id = manager.check_image_updates(
                    "test/image", "latest"
                )

                assert has_update is False
                assert current_id == "Error"
                assert latest_id == "Error"
                mock_print.assert_called_with(
                    "⚠️ Error checking test/image: Docker error", style="yellow"
                )

    def test_check_all_updates(self):
        """Test checking all services for updates"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock images
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"
            mock_latest_image = Mock()
            mock_latest_image.short_id = "def456"

            mock_client.images.get.return_value = mock_current_image
            mock_client.images.pull.return_value = mock_latest_image

            with patch("rich.console.Console.print") as mock_print:
                manager = HomelabUpdateManager()
                updates = manager.check_all_updates()

                assert len(updates) > 0
                assert updates[0]["image"] == "ghcr.io/home-assistant/home-assistant"
                assert updates[0]["current_id"] == "abc123"
                assert updates[0]["latest_id"] == "def456"

    def test_update_service_success(self):
        """Test successful service update"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock container
            mock_container = Mock()
            mock_container.name = "test-service"
            mock_client.containers.list.return_value = [mock_container]

            with patch("homelab_manager.updates.subprocess.run") as mock_run, patch(
                "homelab_manager.updates.time.sleep"
            ), patch("homelab_manager.updates.os.chdir"), patch(
                "homelab_manager.updates.console.print"
            ) as mock_print:

                mock_run.return_value = Mock(returncode=0)

                manager = HomelabUpdateManager()
                result = manager.update_service("test-service")

                assert result is True
                mock_print.assert_any_call(
                    "✅ test-service updated successfully", style="green"
                )

    def test_update_service_failure(self):
        """Test service update failure"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            mock_client.containers.list.return_value = []

            with patch("homelab_manager.updates.subprocess.run") as mock_run, patch(
                "homelab_manager.updates.time.sleep"
            ), patch("homelab_manager.updates.os.chdir"), patch(
                "homelab_manager.updates.console.print"
            ) as mock_print:

                mock_run.return_value = Mock(returncode=0)

                manager = HomelabUpdateManager()
                result = manager.update_service("test-service")

                assert result is False
                mock_print.assert_any_call("❌ test-service update failed", style="red")

    def test_update_service_subprocess_error(self):
        """Test service update with subprocess error"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            with patch(
                "homelab_manager.updates.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "docker-compose"),
            ), patch("homelab_manager.updates.os.chdir"), patch(
                "homelab_manager.updates.console.print"
            ) as mock_print:

                manager = HomelabUpdateManager()
                result = manager.update_service("test-service")

                assert result is False
                mock_print.assert_any_call(
                    "❌ Update failed: Command 'docker-compose' returned non-zero exit status 1.",
                    style="red",
                )

    def test_update_all_services_success(self):
        """Test successful update of all services"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            with patch("homelab_manager.updates.subprocess.run") as mock_run, patch(
                "homelab_manager.updates.os.chdir"
            ), patch("homelab_manager.updates.console.print") as mock_print, patch(
                "homelab_manager.updates.HomelabAutomation"
            ) as mock_automation_class, patch(
                "homelab_manager.updates.HomelabHealthMonitor"
            ) as mock_health_class:

                # Mock backup
                mock_automation = Mock()
                mock_automation.backup.return_value = "/backup/path"
                mock_automation_class.return_value = mock_automation

                # Mock health check
                mock_health = Mock()
                mock_health_class.return_value = mock_health

                mock_run.return_value = Mock(returncode=0)

                manager = HomelabUpdateManager()
                result = manager.update_all_services()

                assert result is True
                mock_print.assert_any_call("✅ Update complete!", style="green")

    def test_update_all_services_backup_failure(self):
        """Test update all services with backup failure"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            with patch("homelab_manager.updates.console.print") as mock_print, patch(
                "homelab_manager.updates.HomelabAutomation"
            ) as mock_automation_class:

                # Mock backup failure
                mock_automation = Mock()
                mock_automation.backup.return_value = None
                mock_automation_class.return_value = mock_automation

                manager = HomelabUpdateManager()
                result = manager.update_all_services()

                assert result is False
                mock_print.assert_any_call(
                    "❌ Backup failed, aborting update", style="red"
                )

    def test_update_all_services_subprocess_error(self):
        """Test update all services with subprocess error"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            with patch(
                "homelab_manager.updates.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "docker-compose"),
            ), patch("homelab_manager.updates.os.chdir"), patch(
                "homelab_manager.updates.console.print"
            ) as mock_print, patch(
                "homelab_manager.updates.HomelabAutomation"
            ) as mock_automation_class:

                # Mock backup
                mock_automation = Mock()
                mock_automation.backup.return_value = "/backup/path"
                mock_automation_class.return_value = mock_automation

                manager = HomelabUpdateManager()
                result = manager.update_all_services()

                assert result is False
                mock_print.assert_any_call(
                    "❌ Update failed: Command 'docker-compose' returned non-zero exit status 1.",
                    style="red",
                )

    def test_show_versions(self):
        """Test showing service versions"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock container
            mock_container = Mock()
            mock_container.name = "test-container"
            mock_container.status = "running"
            mock_container.image.tags = ["test:latest"]

            mock_client.containers.list.return_value = [mock_container]

            # Mock image
            mock_image = Mock()
            mock_image.attrs = {"Created": "2023-01-01T12:00:00.000Z"}
            mock_client.images.get.return_value = mock_image

            with patch("rich.console.Console.print") as mock_print:
                manager = HomelabUpdateManager()
                manager.show_versions()

                # Should print version information
                assert mock_print.call_count > 0

    def test_show_versions_error(self):
        """Test showing service versions with error"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            mock_client.containers.list.side_effect = Exception("Docker error")

            with patch("rich.console.Console.print") as mock_print:
                manager = HomelabUpdateManager()
                manager.show_versions()

                mock_print.assert_any_call(
                    "⚠️ Error getting versions: Docker error", style="yellow"
                )

    def test_auto_check_with_updates(self):
        """Test automated update check with updates available"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock images
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"
            mock_latest_image = Mock()
            mock_latest_image.short_id = "def456"

            mock_client.images.get.return_value = mock_current_image
            mock_client.images.pull.return_value = mock_latest_image

            with patch("homelab_manager.updates.console.print") as mock_print, patch(
                "builtins.open", mock_open()
            ) as mock_file:

                manager = HomelabUpdateManager()
                manager.auto_check()

                # Should log updates to file
                mock_file.assert_called()
                mock_print.assert_any_call("🔄 9 updates available", style="yellow")

    def test_auto_check_no_updates(self):
        """Test automated update check with no updates"""
        with patch("homelab_manager.updates.docker.from_env") as mock_docker:
            mock_client = Mock()
            mock_docker.return_value = mock_client

            # Mock images with same ID (no updates)
            mock_current_image = Mock()
            mock_current_image.short_id = "abc123"
            mock_latest_image = Mock()
            mock_latest_image.short_id = "abc123"

            mock_client.images.get.return_value = mock_current_image
            mock_client.images.pull.return_value = mock_latest_image

            with patch("rich.console.Console.print") as mock_print:
                manager = HomelabUpdateManager()
                manager.auto_check()

                mock_print.assert_any_call("✅ No updates available", style="green")

    def test_main_function_check(self):
        """Test main function with check action"""
        with patch(
            "homelab_manager.updates.HomelabUpdateManager"
        ) as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "check"
                mock_args.service = None
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.updates import main

                main()

                mock_manager.check_all_updates.assert_called_once()

    def test_main_function_update(self):
        """Test main function with update action"""
        with patch(
            "homelab_manager.updates.HomelabUpdateManager"
        ) as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "update"
                mock_args.service = None
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.updates import main

                main()

                mock_manager.update_all_services.assert_called_once()

    def test_main_function_update_service(self):
        """Test main function with update-service action"""
        with patch(
            "homelab_manager.updates.HomelabUpdateManager"
        ) as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "update-service"
                mock_args.service = "test-service"
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.updates import main

                main()

                mock_manager.update_service.assert_called_once_with("test-service")

    def test_main_function_update_service_no_service(self):
        """Test main function with update-service action but no service specified"""
        with patch(
            "homelab_manager.updates.HomelabUpdateManager"
        ) as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            with patch(
                "homelab_manager.updates.argparse.ArgumentParser"
            ) as mock_parser, patch(
                "homelab_manager.updates.console.print"
            ) as mock_print, patch(
                "homelab_manager.updates.sys.exit"
            ) as mock_exit:

                mock_args = Mock()
                mock_args.action = "update-service"
                mock_args.service = None
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.updates import main

                main()

                mock_print.assert_called_with(
                    "❌ Please specify --service for update-service", style="red"
                )
                mock_exit.assert_called_with(1)

    def test_main_function_versions(self):
        """Test main function with versions action"""
        with patch(
            "homelab_manager.updates.HomelabUpdateManager"
        ) as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "versions"
                mock_args.service = None
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.updates import main

                main()

                mock_manager.show_versions.assert_called_once()

    def test_main_function_auto_check(self):
        """Test main function with auto-check action"""
        with patch(
            "homelab_manager.updates.HomelabUpdateManager"
        ) as mock_manager_class:
            mock_manager = Mock()
            mock_manager_class.return_value = mock_manager

            with patch("argparse.ArgumentParser") as mock_parser:
                mock_args = Mock()
                mock_args.action = "auto-check"
                mock_args.service = None
                mock_parser.return_value.parse_args.return_value = mock_args

                from homelab_manager.updates import main

                main()

                mock_manager.auto_check.assert_called_once()
