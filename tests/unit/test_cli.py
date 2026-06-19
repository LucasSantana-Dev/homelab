"""Unit tests for CLI commands via create_app()"""

from unittest.mock import Mock

import typer
from typer.testing import CliRunner

from homelab_manager.cli.commands import create_app


def make_mocks():
    """Create injected mock managers for CLI testing"""
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
    container_manager.get_service_logs.return_value = "log output"

    health_monitor = Mock()
    health_monitor.check_all_services.return_value = {}

    update_manager = Mock()
    update_manager.check_updates.return_value = {"success": True, "message": "ok"}
    update_manager.update_all.return_value = {"success": True, "message": "updated"}
    update_manager.update_service.return_value = {"success": True, "message": "updated"}
    update_manager.get_update_status.return_value = {
        "success": True,
        "services": [],
        "total_services": 0,
    }

    return registry, config_manager, container_manager, health_monitor, update_manager


def make_app():
    """Create a fully-mocked app for testing"""
    registry, config_manager, container_manager, health_monitor, update_manager = (
        make_mocks()
    )
    return create_app(
        config_manager=config_manager,
        container_manager=container_manager,
        health_monitor=health_monitor,
        update_manager=update_manager,
        registry=registry,
    )


class TestCreateApp:
    """Tests for create_app() factory"""

    def test_create_app_returns_typer_instance(self):
        """Verify create_app() returns a Typer app"""
        app = make_app()
        assert isinstance(app, typer.Typer)

    def test_create_app_help_exits_zero(self):
        """Verify --help exits successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["--help"])
        assert result.exit_code == 0

    def test_invalid_command_exits_nonzero(self):
        """Verify an unknown command exits with non-zero"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["invalid-command-xyz"])
        assert result.exit_code != 0


class TestStatusCommand:
    """Tests for the status command"""

    def test_status_exits_zero(self):
        """Verify status command exits successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["status"])
        assert result.exit_code == 0

    def test_status_with_containers(self):
        """Verify status displays containers"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        container_manager.get_container_status.return_value = [
            {"name": "grafana", "status": "running", "port": 3000, "health": "healthy"}
        ]

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "grafana" in result.output


class TestHealthCommand:
    """Tests for the health command"""

    def test_health_exits_zero(self):
        """Verify health command exits successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["health"])
        assert result.exit_code == 0

    def test_health_shows_service_status(self):
        """Verify health command displays service status"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        health_monitor.check_all_services.return_value = {
            "grafana": {
                "healthy": True,
                "response_time": 12.5,
                "last_check": "2026-05-07",
            }
        }

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "grafana" in result.output


class TestDeployCommand:
    """Tests for the deploy command"""

    def test_deploy_success_exits_zero(self):
        """Verify deploy exits zero on success"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["deploy"])
        assert result.exit_code == 0

    def test_deploy_failure_exits_nonzero(self):
        """Verify deploy exits non-zero on failure"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        container_manager.deploy.return_value = {
            "success": False,
            "error": "deploy failed",
        }

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["deploy"])
        assert result.exit_code != 0


class TestUpdateCommand:
    """Tests for the update command"""

    def test_update_success_exits_zero(self):
        """Verify update exits zero on success"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["update"])
        assert result.exit_code == 0

    def test_update_failure_exits_nonzero(self):
        """Verify update exits non-zero on failure"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        update_manager.update_all.return_value = {
            "success": False,
            "error": "update failed",
        }

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["update"])
        assert result.exit_code != 0


class TestConfigCommand:
    """Tests for the config command"""

    def test_config_exits_zero(self):
        """Verify config command exits successfully"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        config_manager.get_config_summary.return_value = {
            "DOMAIN": {"value": "example.com", "valid": True, "required": True}
        }

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0


class TestUrlsCommand:
    """Tests for the urls command"""

    def test_urls_exits_zero(self):
        """Verify urls command exits successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["urls"])
        assert result.exit_code == 0


class TestServicesCommand:
    """Tests for the services command"""

    def test_services_exits_zero(self):
        """Verify services command exits successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["services"])
        assert result.exit_code == 0


class TestLogsCommand:
    """Tests for the logs command"""

    def test_logs_no_service_exits_zero(self):
        """Verify logs with no argument exits successfully"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["logs"])
        assert result.exit_code == 0

    def test_logs_with_service_name(self):
        """Verify logs with a service name fetches logs"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["logs", "grafana"])
        assert result.exit_code == 0


class TestBackupCommand:
    """Tests for the backup command"""

    def test_backup_success_exits_zero(self):
        """Verify backup exits zero on success"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["backup"])
        assert result.exit_code == 0

    def test_backup_failure_exits_nonzero(self):
        """Verify backup exits non-zero on failure"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        container_manager.create_backup.return_value = {
            "success": False,
            "error": "backup failed",
        }

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["backup"])
        assert result.exit_code != 0


class TestRestartCommand:
    """Tests for the restart command"""

    def test_restart_all_exits_zero(self):
        """Verify restart without args exits zero"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["restart"])
        assert result.exit_code == 0

    def test_restart_specific_service_exits_zero(self):
        """Verify restart with service name exits zero"""
        runner = CliRunner()
        result = runner.invoke(make_app(), ["restart", "grafana"])
        assert result.exit_code == 0


class TestManagementCommandExceptionHandling:
    """Tests for exception scrubbing in management commands"""

    def test_deploy_exception_scrubbed(self):
        """Verify deploy command scrubs raw exception messages"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        # Mock deploy to raise an exception
        container_manager.deploy.side_effect = RuntimeError(
            "leaked_token=secret123 socket=/tmp/bad.sock"
        )

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["deploy"])
        assert result.exit_code != 0
        # Verify the raw exception message is NOT in output
        assert "leaked_token=secret123" not in result.output
        assert "socket=/tmp/bad.sock" not in result.output
        # Verify scrubbed message IS in output
        assert "RuntimeError" in result.output
        assert "deploy failed" in result.output

    def test_update_exception_scrubbed(self):
        """Verify update command scrubs raw exception messages"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        update_manager.update_all.side_effect = ValueError(
            "DB_PASSWORD=super_secret port=5432"
        )

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["update"])
        assert result.exit_code != 0
        assert "DB_PASSWORD=super_secret" not in result.output
        assert "port=5432" not in result.output
        assert "ValueError" in result.output
        assert "update failed" in result.output

    def test_backup_exception_scrubbed(self):
        """Verify backup command scrubs raw exception messages"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        container_manager.create_backup.side_effect = IOError(
            "AWS_KEY=AKIAIOSFODNN7EXAMPLE mount=/mnt/sensitive"
        )

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["backup"])
        assert result.exit_code != 0
        assert "AWS_KEY=AKIAIOSFODNN7EXAMPLE" not in result.output
        assert "mount=/mnt/sensitive" not in result.output
        assert "OSError" in result.output
        assert "backup failed" in result.output

    def test_restore_exception_scrubbed(self):
        """Verify restore command scrubs raw exception messages"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        container_manager.restore_backup.side_effect = OSError(
            "API_TOKEN=bearer_xyz_sensitive /etc/secrets/key"
        )

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["restore", "/tmp/backup.tar.gz"])
        assert result.exit_code != 0
        assert "API_TOKEN=bearer_xyz_sensitive" not in result.output
        assert "/etc/secrets/key" not in result.output
        assert "OSError" in result.output
        assert "restore failed" in result.output

    def test_restart_exception_scrubbed(self):
        """Verify restart command scrubs raw exception messages"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        container_manager.deploy.side_effect = RuntimeError(
            "connection_string=postgresql://user:passwd@localhost"
        )

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["restart"])
        assert result.exit_code != 0
        assert (
            "connection_string=postgresql://user:passwd@localhost" not in result.output
        )
        assert "RuntimeError" in result.output
        assert "restart failed" in result.output

    def test_restart_service_exception_scrubbed(self):
        """Verify restart with service name scrubs exceptions"""
        registry, config_manager, container_manager, health_monitor, update_manager = (
            make_mocks()
        )
        container_manager.restart_service.side_effect = RuntimeError(
            "secret_env_value=shhh /private/mount"
        )

        app = create_app(
            config_manager=config_manager,
            container_manager=container_manager,
            health_monitor=health_monitor,
            update_manager=update_manager,
            registry=registry,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["restart", "grafana"])
        assert result.exit_code != 0
        assert "secret_env_value=shhh" not in result.output
        assert "/private/mount" not in result.output
        assert "RuntimeError" in result.output
        assert "restart failed" in result.output
