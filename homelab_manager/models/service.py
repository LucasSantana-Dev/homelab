#!/usr/bin/env python3
"""
Service Model
Data classes for service definitions loaded from services.yaml
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class ServiceCategory:
    """Category definition for grouping services"""

    name: str
    description: str
    compose_file: str


@dataclass
class Service:
    """Service definition with all configuration"""

    id: str
    name: str
    category: str
    container_name: str
    description: str = ""
    port: Optional[int] = None
    internal_port: Optional[int] = None
    health_endpoint: Optional[str] = None
    sensitive: bool = False
    localhost_only: bool = False
    has_port: bool = True
    url_path: Optional[str] = None

    @property
    def health_url(self) -> Optional[str]:
        """Generate health check URL"""
        if not self.has_port or not self.port:
            return None
        host = "127.0.0.1" if self.localhost_only else "localhost"
        endpoint = self.health_endpoint or "/"
        return f"http://{host}:{self.port}{endpoint}"

    def get_public_url(self, domain: str) -> Optional[str]:
        """Generate public URL for the service"""
        if not self.has_port:
            return None
        path = self.url_path if self.url_path else self.id
        if path == "":
            return f"https://{domain}"
        return f"https://{path}.{domain}"

    def get_tailscale_url(self, tailscale_ip: str) -> Optional[str]:
        """Generate Tailscale URL for the service"""
        if not self.has_port or not self.port:
            return None
        return f"http://{tailscale_ip}:{self.port}"


class ServiceRegistry:
    """Registry for managing service definitions from YAML"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "data" / "services.yaml"
        self.config_path = config_path
        self._categories: Dict[str, ServiceCategory] = {}
        self._services: Dict[str, Service] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load service configuration from YAML file"""
        if not self.config_path.exists():
            return

        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f)

        # Load categories
        for cat_id, cat_data in data.get("categories", {}).items():
            self._categories[cat_id] = ServiceCategory(
                name=cat_id,
                description=cat_data.get("description", ""),
                compose_file=cat_data.get("compose_file", ""),
            )

        # Load services
        for svc_id, svc_data in data.get("services", {}).items():
            self._services[svc_id] = Service(
                id=svc_id,
                name=svc_data.get("name", svc_id),
                category=svc_data.get("category", ""),
                container_name=svc_data.get("container_name", svc_id),
                description=svc_data.get("description", ""),
                port=svc_data.get("port"),
                internal_port=svc_data.get("internal_port"),
                health_endpoint=svc_data.get("health_endpoint"),
                sensitive=svc_data.get("sensitive", False),
                localhost_only=svc_data.get("localhost_only", False),
                has_port=svc_data.get("has_port", True),
                url_path=svc_data.get("url_path"),
            )

    @property
    def categories(self) -> Dict[str, ServiceCategory]:
        """Get all categories"""
        return self._categories

    @property
    def services(self) -> Dict[str, Service]:
        """Get all services"""
        return self._services

    def get_service(self, service_id: str) -> Optional[Service]:
        """Get a service by ID"""
        return self._services.get(service_id)

    def get_services_by_category(self, category: str) -> List[Service]:
        """Get all services in a category"""
        return [s for s in self._services.values() if s.category == category]

    def get_services_with_ports(self) -> List[Service]:
        """Get all services that have exposed ports"""
        return [s for s in self._services.values() if s.has_port and s.port]

    def get_sensitive_services(self) -> List[Service]:
        """Get all sensitive services"""
        return [s for s in self._services.values() if s.sensitive]

    def get_public_services(self) -> List[Service]:
        """Get all non-sensitive services suitable for public access"""
        return [
            s
            for s in self._services.values()
            if not s.sensitive and s.has_port and not s.localhost_only
        ]

    def get_service_by_container(self, container_name: str) -> Optional[Service]:
        """Get a service by container name"""
        for service in self._services.values():
            if service.container_name == container_name:
                return service
        return None
