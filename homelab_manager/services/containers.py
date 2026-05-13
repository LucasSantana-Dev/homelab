#!/usr/bin/env python3
"""
Container Management Service (Aggregate)
Delegates to specialized manager classes for focused responsibilities
"""

from typing import Dict, List, Optional

from ..models.service import ServiceRegistry
from .backup_manager import BackupManager
from .deployment import DeploymentManager
from .status import StatusManager


class ContainerManager:
    """Aggregate manager that delegates to specialized managers"""

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        self.registry = registry or ServiceRegistry()
        self.deployment = DeploymentManager()
        self.backup = BackupManager()
        self.status = StatusManager(registry=self.registry)

    # Delegation to DeploymentManager
    def deploy(self) -> Dict:
        """Deploy homelab services"""
        return self.deployment.deploy()

    def restart_service(self, service_name: str) -> Dict:
        """Restart a specific service"""
        return self.deployment.restart_service(service_name)

    # Delegation to BackupManager
    def create_backup(self) -> Dict:
        """Create backup of homelab data"""
        return self.backup.create_backup()

    def restore_backup(self, backup_path: str) -> Dict:
        """Restore homelab from backup"""
        return self.backup.restore_backup(backup_path)

    # Delegation to StatusManager
    def get_container_status(self) -> List[Dict]:
        """Get status of all homelab containers"""
        return self.status.get_container_status()

    def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """Get logs for a specific service"""
        return self.status.get_service_logs(service_name, lines)

    # Registry delegation
    def get_service_info(self, service_id: str) -> Optional[Dict]:
        """Get detailed information about a service from the registry"""
        service = self.registry.get_service(service_id)
        if not service:
            return None

        return {
            "id": service.id,
            "name": service.name,
            "category": service.category,
            "container_name": service.container_name,
            "port": service.port,
            "health_url": service.health_url,
            "health_mode": service.health_mode,
            "health_host": service.health_host,
            "expected_statuses": service.expected_statuses,
            "sensitive": service.sensitive,
            "description": service.description,
        }

    def get_services_by_category(self, category: str) -> List[Dict]:
        """Get all services in a category"""
        services = self.registry.get_services_by_category(category)
        return [
            {
                "id": s.id,
                "name": s.name,
                "container_name": s.container_name,
                "port": s.port,
                "sensitive": s.sensitive,
            }
            for s in services
        ]
