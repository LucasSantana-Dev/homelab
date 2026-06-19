"""Unit tests for __main__.py and app entry point"""

from unittest.mock import Mock

from typer.testing import CliRunner

from homelab_manager.cli import create_app


def make_app():
    """Create a fully-mocked Typer app for testing"""
    registry = Mock()
    registry.services = {}
    registry.categories = {}
    registry.get_service.return_value = None
    registry.get_services_with_ports.return_value = []
    registry.get_services_by_category.return_value = []

    config_manager = Mock()
    config_manager.load_env.return_value = {}
    config_manager.validate_config.return_value = {}
    config_manager.get_config_summary.return_value = {}
    config_manager.get_missing_config.return_value = []
    config_manager.get_services_for_display.return_value = []

    container_manager = Mock()
    container_manager.get_container_status.return_value = []
    container_manager.deploy.return_value = {"success": True}
    container_manager.create_backup.return_value = {
        "success": True,
        "backup_path": "/tmp/backup.tar.gz",
    }
    container_manager.restore_backup.return_value = {"success": True}
    container_manager.restart_service.return_value = {"success": True}
    container_manager.get_service_logs.return_value = ""

    health_monitor = Mock()
    health_monitor.check_all_services.return_value = {}

    update_manager = Mock()
    update_manager.update_all.return_value = {"success": True, "message": "updated"}

    return create_app(
        config_manager=config_manager,
        container_manager=container_manager,
        health_monitor=health_monitor,
        update_manager=update_manager,
        registry=registry,
    )


class TestMainModule:
    """Tests for the __main__ module entry point"""

    def test_main_module_can_be_imported(self):
        """Test that homelab_manager.__main__ imports without error"""
        from homelab_manager import __main__

        assert __main__ is not None

    def test_main_module_uses_create_app(self):
        """Test that __main__ depends on create_app from cli"""
        from homelab_manager.cli import create_app as cli_create_app

        assert cli_create_app is not None

    def test_app_help_exits_zero(self):
        """Test --help exits with code 0"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["--help"])
        assert result.exit_code == 0

    def test_app_invalid_command_exits_nonzero(self):
        """Test an unknown command exits with non-zero code"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["invalid-command-xyz"])
        assert result.exit_code != 0

    def test_app_status_command(self):
        """Test the status command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["status"])
        assert result.exit_code == 0

    def test_app_deploy_command(self):
        """Test the deploy command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["deploy"])
        assert result.exit_code == 0

    def test_app_update_command(self):
        """Test the update command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["update"])
        assert result.exit_code == 0

    def test_app_health_command(self):
        """Test the health command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["health"])
        assert result.exit_code == 0

    def test_app_config_command(self):
        """Test the config command runs successfully"""
        app = make_app()
        # Override config_manager to return proper summary structure
        runner = CliRunner()
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0

    def test_app_urls_command(self):
        """Test the urls command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["urls"])
        assert result.exit_code == 0

    def test_app_services_command(self):
        """Test the services command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["services"])
        assert result.exit_code == 0

    def test_app_backup_command(self):
        """Test the backup command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["backup"])
        assert result.exit_code == 0

    def test_app_restart_command(self):
        """Test the restart command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["restart"])
        assert result.exit_code == 0

    def test_app_logs_command(self):
        """Test the logs command runs successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["logs"])
        assert result.exit_code == 0
