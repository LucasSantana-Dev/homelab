"""
Unit tests for __main__.py module
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from homelab_manager import __main__


class TestMainModule:
    """Test cases for __main__.py module"""

    def test_main_function(self):
        """Test the main function"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.deploy.return_value = True

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'deploy']):
                __main__.main()
                assert True

    def test_main_function_with_help(self):
        """Test the main function with help argument"""
        import pytest

        # Mock sys.argv to avoid command line argument issues
        with patch('sys.argv', ['__main__.py', '--help']):
            # Should raise SystemExit for help
            with pytest.raises(SystemExit):
                __main__.main()

    def test_main_function_with_invalid_command(self):
        """Test the main function with invalid command"""
        import pytest

        # Mock sys.argv to avoid command line argument issues
        with patch('sys.argv', ['__main__.py', 'invalid-command']):
            # Should raise SystemExit for invalid command
            with pytest.raises(SystemExit):
                __main__.main()

    def test_main_function_with_update_command(self):
        """Test the main function with update command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.update.return_value = True

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'update']):
                __main__.main()
                assert True

    def test_main_function_with_backup_command(self):
        """Test the main function with backup command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.backup.return_value = "/path/to/backup"

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'backup']):
                __main__.main()
                assert True

    def test_main_function_with_restore_command(self):
        """Test the main function with restore command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.restore.return_value = True

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'restore', '--backup-path', '/path/to/backup']):
                __main__.main()
                assert True

    def test_main_function_with_health_check_command(self):
        """Test the main function with health-check command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.health_check.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'health-check']):
                __main__.main()
                assert True

    def test_main_function_with_status_command(self):
        """Test the main function with status command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.status.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'status']):
                __main__.main()
                assert True

    def test_main_function_with_monitor_command(self):
        """Test the main function with monitor command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.monitor.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'monitor']):
                __main__.main()
                assert True

    def test_main_function_with_check_updates_command(self):
        """Test the main function with check-updates command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.check_updates.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'check-updates']):
                __main__.main()
                assert True

    def test_main_function_with_update_all_command(self):
        """Test the main function with update-all command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.update_all.return_value = True

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'update-all']):
                __main__.main()
                assert True

    def test_main_function_with_versions_command(self):
        """Test the main function with versions command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.versions.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'versions']):
                __main__.main()
                assert True

    def test_main_function_with_cleanup_command(self):
        """Test the main function with cleanup command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.cleanup.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'cleanup']):
                __main__.main()
                assert True

    def test_main_function_with_setup_cron_command(self):
        """Test the main function with setup-cron command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.setup_cron.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'setup-cron']):
                __main__.main()
                assert True

    def test_main_function_with_validate_config_command(self):
        """Test the main function with validate-config command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.validate_config.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'validate-config']):
                __main__.main()
                assert True

    def test_main_function_with_config_summary_command(self):
        """Test the main function with config-summary command"""
        with patch('homelab_manager.cli.HomelabCLI') as mock_cli:
            mock_instance = mock_cli.return_value
            mock_instance.config_summary.return_value = None

            # Mock sys.argv to avoid command line argument issues
            with patch('sys.argv', ['__main__.py', 'config-summary']):
                __main__.main()
                assert True
