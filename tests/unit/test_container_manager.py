"""Unit tests for ContainerManager aggregate"""

from unittest.mock import Mock, patch

import pytest

from homelab_manager.services.containers import ContainerManager


class TestContainerManagerInit:
    """Tests for ContainerManager initialization"""

    def test_init_creates_sub_managers(self):
        """Verify ContainerManager instantiates all sub-managers"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager") as mock_dep,
            patch("homelab_manager.services.containers.BackupManager") as mock_bak,
            patch("homelab_manager.services.containers.StatusManager") as mock_stat,
            patch("homelab_manager.services.containers.ServiceRegistry") as mock_reg,
        ):
            ContainerManager()

            mock_dep.assert_called_once()
            mock_bak.assert_called_once()
            mock_stat.assert_called_once()
            mock_reg.assert_called_once()

    def test_init_assigns_attributes(self):
        """Verify ContainerManager exposes sub-manager attributes"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            manager = ContainerManager()

            assert hasattr(manager, "deployment")
            assert hasattr(manager, "backup")
            assert hasattr(manager, "status")
            assert hasattr(manager, "registry")


class TestDeployCommand:
    """Tests for ContainerManager.deploy()"""

    def test_deploy_delegates_to_deployment_manager(self):
        """Verify deploy() calls deployment.deploy()"""
        with (
            patch(
                "homelab_manager.services.containers.DeploymentManager"
            ) as mock_dep_cls,
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_dep_cls.return_value.deploy.return_value = {"success": True}

            manager = ContainerManager()
            result = manager.deploy()

            manager.deployment.deploy.assert_called_once()
            assert result == {"success": True}

    def test_deploy_propagates_failure(self):
        """Verify deploy() propagates failure from deployment manager"""
        with (
            patch(
                "homelab_manager.services.containers.DeploymentManager"
            ) as mock_dep_cls,
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_dep_cls.return_value.deploy.return_value = {
                "success": False,
                "error": "failed",
            }

            manager = ContainerManager()
            result = manager.deploy()

            assert result["success"] is False
            assert "error" in result


class TestRestartService:
    """Tests for ContainerManager.restart_service()"""

    def test_restart_service_delegates(self):
        """Verify restart_service() calls deployment.restart_service()"""
        with (
            patch(
                "homelab_manager.services.containers.DeploymentManager"
            ) as mock_dep_cls,
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_dep_cls.return_value.restart_service.return_value = {"success": True}

            manager = ContainerManager()
            result = manager.restart_service("grafana")

            manager.deployment.restart_service.assert_called_once_with("grafana")
            assert result == {"success": True}

    def test_restart_service_passes_name(self):
        """Verify restart_service() forwards service name correctly"""
        with (
            patch(
                "homelab_manager.services.containers.DeploymentManager"
            ) as mock_dep_cls,
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_dep_cls.return_value.restart_service.return_value = {"success": True}

            manager = ContainerManager()
            manager.restart_service("homeassistant")

            args, _ = manager.deployment.restart_service.call_args
            assert args[0] == "homeassistant"


class TestCreateBackup:
    """Tests for ContainerManager.create_backup()"""

    def test_create_backup_delegates(self):
        """Verify create_backup() calls backup.create_backup()"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager") as mock_bak_cls,
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_bak_cls.return_value.create_backup.return_value = {
                "success": True,
                "backup_path": "/tmp/backup.tar.gz",
            }

            manager = ContainerManager()
            result = manager.create_backup()

            manager.backup.create_backup.assert_called_once()
            assert result["success"] is True
            assert "backup_path" in result

    def test_create_backup_failure_propagated(self):
        """Verify create_backup() propagates failure result"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager") as mock_bak_cls,
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_bak_cls.return_value.create_backup.return_value = {
                "success": False,
                "error": "disk full",
            }

            manager = ContainerManager()
            result = manager.create_backup()

            assert result["success"] is False


class TestRestoreBackup:
    """Tests for ContainerManager.restore_backup()"""

    def test_restore_backup_delegates(self):
        """Verify restore_backup() calls backup.restore_backup()"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager") as mock_bak_cls,
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_bak_cls.return_value.restore_backup.return_value = {"success": True}

            manager = ContainerManager()
            result = manager.restore_backup("/tmp/backup.tar.gz")

            manager.backup.restore_backup.assert_called_once_with("/tmp/backup.tar.gz")
            assert result == {"success": True}

    def test_restore_backup_passes_path(self):
        """Verify restore_backup() forwards backup_path correctly"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager") as mock_bak_cls,
            patch("homelab_manager.services.containers.StatusManager"),
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_bak_cls.return_value.restore_backup.return_value = {"success": True}

            manager = ContainerManager()
            manager.restore_backup("/backups/2024-01-01.tar.gz")

            args, _ = manager.backup.restore_backup.call_args
            assert args[0] == "/backups/2024-01-01.tar.gz"


class TestGetContainerStatus:
    """Tests for ContainerManager.get_container_status()"""

    def test_get_container_status_delegates(self):
        """Verify get_container_status() calls status.get_container_status()"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager") as mock_stat_cls,
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_stat_cls.return_value.get_container_status.return_value = [
                {"name": "grafana", "status": "running"}
            ]

            manager = ContainerManager()
            result = manager.get_container_status()

            manager.status.get_container_status.assert_called_once()
            assert len(result) == 1
            assert result[0]["name"] == "grafana"

    def test_get_container_status_returns_list(self):
        """Verify get_container_status() returns a list"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager") as mock_stat_cls,
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_stat_cls.return_value.get_container_status.return_value = []

            manager = ContainerManager()
            result = manager.get_container_status()

            assert isinstance(result, list)

    def test_get_container_status_with_multiple_containers(self):
        """Verify get_container_status() returns all container entries"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager") as mock_stat_cls,
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_stat_cls.return_value.get_container_status.return_value = [
                {"name": "grafana", "status": "running"},
                {"name": "prometheus", "status": "running"},
                {"name": "homeassistant", "status": "stopped"},
            ]

            manager = ContainerManager()
            result = manager.get_container_status()

            assert len(result) == 3


class TestGetServiceLogs:
    """Tests for ContainerManager.get_service_logs()"""

    def test_get_service_logs_delegates(self):
        """Verify get_service_logs() calls status.get_service_logs()"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager") as mock_stat_cls,
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_stat_cls.return_value.get_service_logs.return_value = (
                "log line 1\nlog line 2"
            )

            manager = ContainerManager()
            result = manager.get_service_logs("grafana")

            manager.status.get_service_logs.assert_called_once_with("grafana", 50)
            assert "log line" in result

    def test_get_service_logs_passes_lines(self):
        """Verify get_service_logs() forwards lines parameter"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager") as mock_stat_cls,
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_stat_cls.return_value.get_service_logs.return_value = ""

            manager = ContainerManager()
            manager.get_service_logs("grafana", lines=100)

            manager.status.get_service_logs.assert_called_once_with("grafana", 100)

    def test_get_service_logs_default_lines_is_50(self):
        """Verify get_service_logs() uses 50 as default for lines"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager") as mock_stat_cls,
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_stat_cls.return_value.get_service_logs.return_value = ""

            manager = ContainerManager()
            manager.get_service_logs("grafana")

            args, _ = manager.status.get_service_logs.call_args
            assert args[1] == 50

    def test_get_service_logs_returns_string(self):
        """Verify get_service_logs() returns a string"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager") as mock_stat_cls,
            patch("homelab_manager.services.containers.ServiceRegistry"),
        ):
            mock_stat_cls.return_value.get_service_logs.return_value = "some logs"

            manager = ContainerManager()
            result = manager.get_service_logs("grafana")

            assert isinstance(result, str)


class TestGetServiceInfo:
    """Tests for ContainerManager.get_service_info()"""

    def test_get_service_info_returns_none_for_unknown(self):
        """Verify get_service_info() returns None for unknown service ID"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch(
                "homelab_manager.services.containers.ServiceRegistry"
            ) as mock_reg_cls,
        ):
            mock_reg_cls.return_value.get_service.return_value = None

            manager = ContainerManager()
            result = manager.get_service_info("nonexistent")

            assert result is None

    def test_get_service_info_returns_dict_for_known_service(self):
        """Verify get_service_info() returns a dict for a known service"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch(
                "homelab_manager.services.containers.ServiceRegistry"
            ) as mock_reg_cls,
        ):
            mock_service = Mock()
            mock_service.id = "grafana"
            mock_service.name = "Grafana"
            mock_service.category = "monitoring"
            mock_service.container_name = "grafana"
            mock_service.port = 3000
            mock_service.health_url = "http://localhost:3000"
            mock_service.health_mode = "http"
            mock_service.health_host = None
            mock_service.expected_statuses = [200]
            mock_service.sensitive = False
            mock_service.description = "Dashboards"

            mock_reg_cls.return_value.get_service.return_value = mock_service

            manager = ContainerManager()
            result = manager.get_service_info("grafana")

            assert result is not None
            assert result["id"] == "grafana"
            assert result["name"] == "Grafana"
            assert result["port"] == 3000


class TestGetServicesByCategory:
    """Tests for ContainerManager.get_services_by_category()"""

    def test_get_services_by_category_returns_list(self):
        """Verify get_services_by_category() returns a list"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch(
                "homelab_manager.services.containers.ServiceRegistry"
            ) as mock_reg_cls,
        ):
            mock_reg_cls.return_value.get_services_by_category.return_value = []

            manager = ContainerManager()
            result = manager.get_services_by_category("monitoring")

            assert isinstance(result, list)

    def test_get_services_by_category_maps_to_dicts(self):
        """Verify get_services_by_category() maps Service objects to dicts"""
        with (
            patch("homelab_manager.services.containers.DeploymentManager"),
            patch("homelab_manager.services.containers.BackupManager"),
            patch("homelab_manager.services.containers.StatusManager"),
            patch(
                "homelab_manager.services.containers.ServiceRegistry"
            ) as mock_reg_cls,
        ):
            mock_service = Mock()
            mock_service.id = "grafana"
            mock_service.name = "Grafana"
            mock_service.container_name = "grafana"
            mock_service.port = 3000
            mock_service.sensitive = False

            mock_reg_cls.return_value.get_services_by_category.return_value = [
                mock_service
            ]

            manager = ContainerManager()
            result = manager.get_services_by_category("monitoring")

            assert len(result) == 1
            assert result[0]["id"] == "grafana"
            assert result[0]["name"] == "Grafana"
