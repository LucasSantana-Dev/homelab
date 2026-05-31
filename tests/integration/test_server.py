#!/usr/bin/env python3
"""
Integration tests for homelab_manager HTTP server.

These tests start a real HTTPServer on an ephemeral localhost port and make
live HTTP requests to verify route behavior, status codes, and response JSON.

Run with:
    pytest tests/integration/test_server.py -v

Routes tested: /health, /status, /summary, 404
"""

import json
import socket
import threading
import time
from http.client import HTTPConnection
from typing import Tuple
from unittest.mock import MagicMock, patch

import pytest

from homelab_manager import __version__
from homelab_manager.server.app import _make_handler


def find_free_port() -> int:
    """Find an available localhost port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
    return port


class HTTPServerFixture:
    """Manage HTTP server lifecycle for testing."""

    def __init__(self, health_monitor):
        self.health_monitor = health_monitor
        self.port = find_free_port()
        self.server = None
        self.thread = None

    def start(self):
        """Start the server in a background thread."""
        from http.server import HTTPServer

        handler_class = _make_handler(self.health_monitor)
        self.server = HTTPServer(("127.0.0.1", self.port), handler_class)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        # Give server time to start
        time.sleep(0.1)

    def stop(self):
        """Stop the server and wait for shutdown."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2)

    def request(self, path: str) -> Tuple[int, str]:
        """Make an HTTP GET request and return (status_code, body)."""
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            status = response.status
            body = response.read().decode()
            return status, body
        finally:
            conn.close()


@pytest.fixture
def mock_health_monitor():
    """Create a mock HealthMonitor for testing."""
    monitor = MagicMock()

    # Default response for check_all_services
    monitor.check_all_services.return_value = {
        "service_a": {"status": "healthy"},
        "service_b": {"status": "healthy"},
    }

    # Default response for get_health_summary
    monitor.get_health_summary.return_value = {
        "total_services": 2,
        "healthy_services": 2,
        "unhealthy_services": 0,
        "services": {"service_a": {}, "service_b": {}},
    }

    return monitor


@pytest.fixture
def http_server(mock_health_monitor):
    """Start and stop the HTTP server for each test."""
    server = HTTPServerFixture(mock_health_monitor)
    server.start()
    yield server
    server.stop()


class TestHealthRoute:
    """Test /health endpoint."""

    def test_health_returns_200(self, http_server):
        """Verify /health returns 200 OK."""
        status, _ = http_server.request("/health")
        assert status == 200

    def test_health_response_is_valid_json(self, http_server):
        """Verify /health response is valid JSON."""
        _, body = http_server.request("/health")
        data = json.loads(body)
        assert isinstance(data, dict)

    def test_health_has_required_fields(self, http_server):
        """Verify /health response has status, version, and timestamp."""
        _, body = http_server.request("/health")
        data = json.loads(body)
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_status_is_ok(self, http_server):
        """Verify health status field is 'ok'."""
        _, body = http_server.request("/health")
        data = json.loads(body)
        assert data["status"] == "ok"

    def test_health_version_matches(self, http_server):
        """Verify health version matches __version__."""
        _, body = http_server.request("/health")
        data = json.loads(body)
        assert data["version"] == __version__

    def test_health_timestamp_is_iso_format(self, http_server):
        """Verify timestamp is in ISO 8601 format."""
        _, body = http_server.request("/health")
        data = json.loads(body)
        timestamp = data["timestamp"]
        # ISO format includes T and timezone info
        assert "T" in timestamp
        assert "+" in timestamp or "Z" in timestamp or timestamp.endswith("+00:00")


class TestStatusRoute:
    """Test /status endpoint."""

    def test_status_returns_200(self, http_server):
        """Verify /status returns 200 OK."""
        status, _ = http_server.request("/status")
        assert status == 200

    def test_status_response_is_valid_json(self, http_server):
        """Verify /status response is valid JSON."""
        _, body = http_server.request("/status")
        data = json.loads(body)
        assert isinstance(data, dict)

    def test_status_includes_services(self, http_server, mock_health_monitor):
        """Verify /status includes service status from monitor."""
        _, body = http_server.request("/status")
        data = json.loads(body)
        # The mock returns service_a and service_b
        assert "service_a" in data
        assert "service_b" in data

    def test_status_calls_health_monitor(self, http_server, mock_health_monitor):
        """Verify /status calls health_monitor.check_all_services()."""
        http_server.request("/status")
        mock_health_monitor.check_all_services.assert_called()


class TestSummaryRoute:
    """Test /summary endpoint."""

    def test_summary_returns_200(self, http_server):
        """Verify /summary returns 200 OK."""
        status, _ = http_server.request("/summary")
        assert status == 200

    def test_summary_response_is_valid_json(self, http_server):
        """Verify /summary response is valid JSON."""
        _, body = http_server.request("/summary")
        data = json.loads(body)
        assert isinstance(data, dict)

    def test_summary_has_required_fields(self, http_server):
        """Verify /summary response has total, healthy, unhealthy, unknown, services."""
        _, body = http_server.request("/summary")
        data = json.loads(body)
        assert "total" in data
        assert "healthy" in data
        assert "unhealthy" in data
        assert "unknown" in data
        assert "services" in data

    def test_summary_counts_match(self, http_server):
        """Verify summary counts match mock health monitor."""
        _, body = http_server.request("/summary")
        data = json.loads(body)
        assert data["total"] == 2
        assert data["healthy"] == 2
        assert data["unhealthy"] == 0
        assert data["unknown"] == 0

    def test_summary_services_list(self, http_server):
        """Verify summary includes service names."""
        _, body = http_server.request("/summary")
        data = json.loads(body)
        assert isinstance(data["services"], list)
        assert "service_a" in data["services"]
        assert "service_b" in data["services"]

    def test_summary_calls_health_monitor(self, http_server, mock_health_monitor):
        """Verify /summary calls health_monitor.get_health_summary()."""
        http_server.request("/summary")
        mock_health_monitor.get_health_summary.assert_called()


class TestNotFoundRoute:
    """Test 404 handling for invalid routes."""

    def test_invalid_path_returns_404(self, http_server):
        """Verify invalid path returns 404 Not Found."""
        status, _ = http_server.request("/nonexistent")
        assert status == 404

    def test_invalid_path_response_is_json(self, http_server):
        """Verify 404 response is valid JSON."""
        _, body = http_server.request("/invalid/path")
        data = json.loads(body)
        assert isinstance(data, dict)

    def test_invalid_path_has_error_message(self, http_server):
        """Verify 404 response includes error message."""
        _, body = http_server.request("/notfound")
        data = json.loads(body)
        assert "error" in data
        assert data["error"] == "not found"

    def test_root_path_returns_404(self, http_server):
        """Verify root / path returns 404 (no catch-all route)."""
        status, _ = http_server.request("/")
        assert status == 404

    def test_deeply_nested_path_returns_404(self, http_server):
        """Verify deeply nested invalid paths return 404."""
        status, _ = http_server.request("/a/b/c/d/e")
        assert status == 404


class TestHTTPHeaders:
    """Test HTTP response headers."""

    def test_responses_have_json_content_type(self, http_server):
        """Verify all successful responses have application/json Content-Type."""
        for path in ["/health", "/status", "/summary"]:
            conn = HTTPConnection("127.0.0.1", http_server.port, timeout=5)
            try:
                conn.request("GET", path)
                response = conn.getresponse()
                content_type = response.headers.get("Content-Type")
                assert (
                    content_type == "application/json"
                ), f"Path {path} has Content-Type: {content_type}"
            finally:
                conn.close()

    def test_404_response_has_json_content_type(self, http_server):
        """Verify 404 responses have application/json Content-Type."""
        conn = HTTPConnection("127.0.0.1", http_server.port, timeout=5)
        try:
            conn.request("GET", "/invalid")
            response = conn.getresponse()
            content_type = response.headers.get("Content-Type")
            assert content_type == "application/json"
        finally:
            conn.close()

    def test_responses_have_content_length(self, http_server):
        """Verify responses include Content-Length header."""
        conn = HTTPConnection("127.0.0.1", http_server.port, timeout=5)
        try:
            conn.request("GET", "/health")
            response = conn.getresponse()
            content_length = response.headers.get("Content-Length")
            assert content_length is not None
            assert int(content_length) > 0
        finally:
            conn.close()
