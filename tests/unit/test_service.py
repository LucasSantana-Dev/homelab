#!/usr/bin/env python3
"""Unit tests for Service and ServiceCategory dataclasses"""

from homelab_manager.models.service import Service, ServiceCategory, ServiceRegistry


class TestServiceDataclass:
    """Tests for Service dataclass creation and properties"""

    def test_service_dataclass_creation(self):
        """Verify Service() can be instantiated with required fields"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
        )
        assert service.id == "test-service"
        assert service.name == "Test Service"
        assert service.category == "testing"
        assert service.container_name == "test-container"

    def test_service_optional_fields(self):
        """Verify Service handles optional fields correctly"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
            port=8000,
            health_endpoint="/health",
            sensitive=True,
        )
        assert service.port == 8000
        assert service.health_endpoint == "/health"
        assert service.sensitive is True

    def test_service_default_sensitive_flag(self):
        """Verify sensitive defaults to False"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
        )
        assert service.sensitive is False

    def test_service_default_has_port(self):
        """Verify has_port defaults to True"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
        )
        assert service.has_port is True

    def test_service_description_defaults_empty(self):
        """Verify description defaults to empty string"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
        )
        assert service.description == ""


class TestServiceCategory:
    """Tests for ServiceCategory dataclass"""

    def test_service_category_creation(self):
        """Verify ServiceCategory() can be instantiated"""
        category = ServiceCategory(
            name="testing",
            description="Test Services",
            compose_file="test.yml",
        )
        assert category.name == "testing"
        assert category.description == "Test Services"
        assert category.compose_file == "test.yml"

    def test_service_category_fields(self):
        """Verify ServiceCategory has all required fields"""
        category = ServiceCategory(
            name="core",
            description="Core Services",
            compose_file="compose/core.yml",
        )
        assert category.name == "core"
        assert category.compose_file == "compose/core.yml"


class TestServiceRegistry:
    """Tests for ServiceRegistry functionality"""

    def test_service_registry_load_from_yaml(self):
        """Verify ServiceRegistry loads services.yaml"""
        registry = ServiceRegistry()
        assert registry is not None
        assert hasattr(registry, "services")
        assert hasattr(registry, "categories")

    def test_service_registry_services_is_dict(self):
        """Verify registry.services returns a dict"""
        registry = ServiceRegistry()
        assert isinstance(registry.services, dict)

    def test_service_registry_categories_is_dict(self):
        """Verify registry.categories returns a dict"""
        registry = ServiceRegistry()
        assert isinstance(registry.categories, dict)

    def test_service_registry_get_service_unknown_returns_none(self):
        """Test get_service returns None for unknown IDs"""
        registry = ServiceRegistry()
        result = registry.get_service("definitely-nonexistent-service-xyz")
        assert result is None

    def test_service_registry_get_services_by_category(self):
        """Test get_services_by_category returns a list"""
        registry = ServiceRegistry()
        services = registry.get_services_by_category("core")
        assert isinstance(services, list)

    def test_service_registry_values_are_service_instances(self):
        """Verify registry values are Service instances"""
        registry = ServiceRegistry()
        for service in registry.services.values():
            assert isinstance(service, Service)

    def test_service_registry_categories_are_servicecategory_instances(self):
        """Verify registry categories are ServiceCategory instances"""
        registry = ServiceRegistry()
        for category in registry.categories.values():
            assert isinstance(category, ServiceCategory)

    def test_service_registry_get_service_by_container_unknown(self):
        """Test get_service_by_container returns None for unknown containers"""
        registry = ServiceRegistry()
        result = registry.get_service_by_container("nonexistent-container-xyz")
        assert result is None

    def test_service_registry_get_services_with_ports(self):
        """Test get_services_with_ports returns a list"""
        registry = ServiceRegistry()
        result = registry.get_services_with_ports()
        assert isinstance(result, list)

    def test_service_registry_get_sensitive_services(self):
        """Test get_sensitive_services returns a list"""
        registry = ServiceRegistry()
        result = registry.get_sensitive_services()
        assert isinstance(result, list)


class TestServiceHealthUrl:
    """Tests for Service health_url property"""

    def test_health_url_generated_from_port_and_endpoint(self):
        """Test health_url property builds correct URL"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
            port=8000,
            health_endpoint="/health",
        )
        assert service.health_url == "http://localhost:8000/health"

    def test_health_url_with_custom_endpoint(self):
        """Test health_url uses the configured health_endpoint"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
            port=9000,
            health_endpoint="/api/health",
        )
        assert service.health_url == "http://localhost:9000/api/health"

    def test_health_url_with_localhost_only(self):
        """Test health_url uses 127.0.0.1 for localhost_only services"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
            port=8000,
            health_endpoint="/health",
            localhost_only=True,
        )
        assert service.health_url == "http://127.0.0.1:8000/health"

    def test_health_url_none_when_no_port(self):
        """Test health_url is None when port is not set"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
            health_endpoint="/health",
        )
        assert service.health_url is None

    def test_health_url_none_when_no_endpoint(self):
        """Test health_url is None when health_endpoint is not set"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
            port=8000,
        )
        assert service.health_url is None

    def test_health_url_none_when_not_configured(self):
        """Test health_url is None when neither port nor endpoint set"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
        )
        assert service.health_url is None

    def test_health_url_none_when_has_port_false(self):
        """Test health_url is None when has_port is False"""
        service = Service(
            id="test-service",
            name="Test Service",
            category="testing",
            container_name="test-container",
            port=8000,
            health_endpoint="/health",
            has_port=False,
        )
        assert service.health_url is None


class TestServiceSensitiveFlag:
    """Tests for Service sensitive flag"""

    def test_sensitive_services_marked_correctly(self):
        """Verify sensitive services can be marked"""
        sensitive_service = Service(
            id="secret-service",
            name="Secret Service",
            category="security",
            container_name="secret-container",
            sensitive=True,
        )
        non_sensitive_service = Service(
            id="public-service",
            name="Public Service",
            category="core",
            container_name="public-container",
            sensitive=False,
        )
        assert sensitive_service.sensitive is True
        assert non_sensitive_service.sensitive is False

    def test_sensitive_flag_can_be_checked(self):
        """Verify sensitive flag is accessible"""
        service = Service(
            id="secret-service",
            name="Secret Service",
            category="security",
            container_name="secret-container",
            sensitive=True,
        )
        assert service.sensitive is True
        assert service.id == "secret-service"


class TestServicePublicUrl:
    """Tests for Service get_public_url method"""

    def test_get_public_url_with_id(self):
        """Test get_public_url returns subdomain URL"""
        service = Service(
            id="grafana",
            name="Grafana",
            category="monitoring",
            container_name="grafana",
            port=3000,
        )
        assert service.get_public_url("example.com") == "https://grafana.example.com"

    def test_get_public_url_none_when_no_port(self):
        """Test get_public_url returns None when has_port is False"""
        service = Service(
            id="no-port-svc",
            name="No Port Service",
            category="core",
            container_name="no-port",
            has_port=False,
        )
        assert service.get_public_url("example.com") is None

    def test_get_tailscale_url(self):
        """Test get_tailscale_url returns correct URL"""
        service = Service(
            id="grafana",
            name="Grafana",
            category="monitoring",
            container_name="grafana",
            port=3000,
        )
        assert service.get_tailscale_url("100.64.0.1") == "http://100.64.0.1:3000"
