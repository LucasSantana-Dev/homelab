"""
Unit tests for CLI management
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager.cli import HomelabCLI


class TestHomelabCLI:
    """Test cases for HomelabCLI class"""

    def test_init(self):
        """Test HomelabCLI initialization"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            cli = HomelabCLI()
            assert cli is not None

    def test_deploy(self):
        """Test deploy command"""
        with patch("homelab_manager.cli.HomelabAutomation") as mock_automation, patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_automation.return_value.deploy.return_value = True

            cli = HomelabCLI()
            result = cli.deploy()

            assert result is True

    def test_update(self):
        """Test update command"""
        with patch("homelab_manager.cli.HomelabAutomation") as mock_automation, patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_automation.return_value.update.return_value = True

            cli = HomelabCLI()
            result = cli.update()

            assert result is True

    def test_backup(self):
        """Test backup command"""
        with patch("homelab_manager.cli.HomelabAutomation") as mock_automation, patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_automation.return_value.backup.return_value = "/path/to/backup"

            cli = HomelabCLI()
            result = cli.backup()

            assert result == "/path/to/backup"

    def test_restore(self):
        """Test restore command"""
        with patch("homelab_manager.cli.HomelabAutomation") as mock_automation, patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_automation.return_value.restore.return_value = True

            cli = HomelabCLI()
            result = cli.restore("/path/to/backup")

            assert result is True

    def test_health_check(self):
        """Test health check command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ) as mock_health, patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_health.return_value.run_health_check.return_value = None

            cli = HomelabCLI()
            result = cli.health_check()

            # Should not raise any exceptions
            assert result is None

    def test_status(self):
        """Test status command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ) as mock_health, patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_health.return_value.quick_status.return_value = None

            cli = HomelabCLI()
            result = cli.status()

            # Should not raise any exceptions
            assert result is None

    def test_monitor(self):
        """Test monitor command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ) as mock_health, patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_health.return_value.monitor_continuous.return_value = None

            cli = HomelabCLI()
            result = cli.monitor(interval=30)

            # Should not raise any exceptions
            assert result is None

    def test_check_updates(self):
        """Test check updates command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager") as mock_updates, patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_updates.return_value.check_all_updates.return_value = []

            cli = HomelabCLI()
            result = cli.check_updates()

            # Should not raise any exceptions
            assert result is None

    def test_update_all(self):
        """Test update all command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager") as mock_updates, patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_updates.return_value.update_all_services.return_value = True

            cli = HomelabCLI()
            result = cli.update_all()

            assert result is True

    def test_update_service(self):
        """Test update service command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager") as mock_updates, patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_updates.return_value.update_service.return_value = True

            cli = HomelabCLI()
            result = cli.update_service("test-service")

            assert result is True

    def test_versions(self):
        """Test versions command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager") as mock_updates, patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_updates.return_value.show_versions.return_value = None

            cli = HomelabCLI()
            result = cli.versions()

            # Should not raise any exceptions
            assert result is None

    def test_cleanup(self):
        """Test cleanup command"""
        with patch("homelab_manager.cli.HomelabAutomation") as mock_automation, patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            mock_automation.return_value.cleanup.return_value = None

            cli = HomelabCLI()
            result = cli.cleanup()

            # Should not raise any exceptions
            assert result is None

    def test_validate_config(self):
        """Test validate config command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ) as mock_config:
            mock_config.return_value.validate_environment.return_value = (True, [])

            cli = HomelabCLI()
            result = cli.validate_config()

            # Should return the validation result
            assert result == (True, [])

    def test_config_summary(self):
        """Test config summary command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ) as mock_config:
            mock_config.return_value.show_config_summary.return_value = None

            cli = HomelabCLI()
            result = cli.config_summary()

            # Should not raise any exceptions
            assert result is None

    def test_setup_cron(self):
        """Test setup cron command"""
        with patch("homelab_manager.cli.HomelabAutomation"), patch(
            "homelab_manager.cli.HomelabHealthMonitor"
        ), patch("homelab_manager.cli.HomelabUpdateManager"), patch(
            "homelab_manager.cli.HomelabConfig"
        ):
            cli = HomelabCLI()
            result = cli.setup_cron()

            # Should not raise any exceptions
            assert result is None

    def test_main_function(self):
        """Test the main function"""
        from unittest.mock import patch

        import pytest

        from homelab_manager.cli import main

        # Mock the argument parsing to avoid sys.argv conflicts
        with patch("sys.argv", ["cli.py", "deploy"]), patch(
            "subprocess.run"
        ) as mock_run:
            # Mock subprocess success
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Success"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            # Should not raise any exceptions
            main()
            assert True

    def test_main_function_with_help(self):
        """Test the main function with help argument"""
        from unittest.mock import patch

        import pytest

        from homelab_manager.cli import main

        # Mock the argument parsing to avoid sys.argv conflicts
        with patch("sys.argv", ["cli.py", "--help"]):
            # Should raise SystemExit for help
            with pytest.raises(SystemExit):
                main()

    def test_main_function_with_invalid_command(self):
        """Test the main function with invalid command"""
        from unittest.mock import patch

        import pytest

        from homelab_manager.cli import main

        # Mock the argument parsing to avoid sys.argv conflicts
        with patch("sys.argv", ["cli.py", "invalid-command"]):
            # Should raise SystemExit for invalid command
            with pytest.raises(SystemExit):
                main()
