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

    def __init__(self, health_monitor, rate_limiter=None):
        self.health_monitor = health_monitor
        self.rate_limiter = rate_limiter
        self.port = find_free_port()
        self.server = None
        self.thread = None

    def start(self):
        """Start the server in a background thread."""
        from http.server import HTTPServer

        handler_class = _make_handler(self.health_monitor, self.rate_limiter)
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

    def request(self, path: str, headers: dict = None) -> Tuple[int, str]:
        """Make an HTTP GET request and return (status_code, body)."""
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", path, headers=headers or {})
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


class TestAuthenticationWithAPIKey:
    """Test X-API-Key authentication on protected endpoints."""

    @pytest.fixture
    def protected_http_server(self, mock_health_monitor, monkeypatch):
        """Start HTTP server with HOMELAB_API_KEY set."""
        monkeypatch.setenv("HOMELAB_API_KEY", "test-secret-key-123")
        server = HTTPServerFixture(mock_health_monitor)
        server.start()
        yield server
        server.stop()

    def test_request_with_missing_key_returns_401(self, protected_http_server):
        """Missing X-API-Key header returns 401 Unauthorized."""
        status, body = protected_http_server.request("/health")
        assert status == 401

    def test_request_with_missing_key_returns_error_json(self, protected_http_server):
        """Missing X-API-Key returns valid error JSON."""
        _, body = protected_http_server.request("/health")
        data = json.loads(body)
        assert data == {"error": "Unauthorized"}

    def test_request_with_wrong_key_returns_401(self, protected_http_server):
        """Wrong X-API-Key value returns 401 Unauthorized."""
        status, body = protected_http_server.request(
            "/health", headers={"X-API-Key": "wrong-key"}
        )
        assert status == 401

    def test_request_with_wrong_key_returns_error_json(self, protected_http_server):
        """Wrong X-API-Key returns valid error JSON."""
        _, body = protected_http_server.request(
            "/health", headers={"X-API-Key": "wrong-key"}
        )
        data = json.loads(body)
        assert data == {"error": "Unauthorized"}

    def test_request_with_correct_key_returns_200(self, protected_http_server):
        """Correct X-API-Key header returns 200 OK."""
        status, _ = protected_http_server.request(
            "/health", headers={"X-API-Key": "test-secret-key-123"}
        )
        assert status == 200

    def test_request_with_correct_key_returns_health_json(self, protected_http_server):
        """Correct X-API-Key returns valid health response."""
        _, body = protected_http_server.request(
            "/health", headers={"X-API-Key": "test-secret-key-123"}
        )
        data = json.loads(body)
        assert "status" in data
        assert data["status"] == "ok"

    def test_status_endpoint_requires_auth(self, protected_http_server):
        """Status endpoint returns 401 without correct X-API-Key."""
        status, body = protected_http_server.request("/status")
        assert status == 401
        data = json.loads(body)
        assert data == {"error": "Unauthorized"}

    def test_summary_endpoint_requires_auth(self, protected_http_server):
        """Summary endpoint returns 401 without correct X-API-Key."""
        status, body = protected_http_server.request("/summary")
        assert status == 401
        data = json.loads(body)
        assert data == {"error": "Unauthorized"}


class TestSecurityHeaders:
    """Test security headers are present on all responses."""

    def test_health_response_has_security_headers(self, http_server):
        """Verify 200 response includes all security headers."""
        from http.client import HTTPConnection

        conn = HTTPConnection("127.0.0.1", http_server.port, timeout=5)
        try:
            conn.request("GET", "/health")
            response = conn.getresponse()
            response.read()
            headers = response.headers

            assert headers.get("X-Content-Type-Options") == "nosniff"
            assert headers.get("X-Frame-Options") == "DENY"
            assert headers.get("X-XSS-Protection") == "1; mode=block"
            assert headers.get("Content-Security-Policy") == "default-src 'self'"
        finally:
            conn.close()

    def test_404_response_has_security_headers(self, http_server):
        """Verify 404 response includes all security headers."""
        from http.client import HTTPConnection

        conn = HTTPConnection("127.0.0.1", http_server.port, timeout=5)
        try:
            conn.request("GET", "/nonexistent")
            response = conn.getresponse()
            response.read()
            headers = response.headers

            assert headers.get("X-Content-Type-Options") == "nosniff"
            assert headers.get("X-Frame-Options") == "DENY"
            assert headers.get("X-XSS-Protection") == "1; mode=block"
            assert headers.get("Content-Security-Policy") == "default-src 'self'"
        finally:
            conn.close()

    def test_401_response_has_security_headers(self, mock_health_monitor, monkeypatch):
        """Verify 401 response includes all security headers."""
        from http.client import HTTPConnection

        monkeypatch.setenv("HOMELAB_API_KEY", "test-secret-key-123")
        server = HTTPServerFixture(mock_health_monitor)
        server.start()
        try:
            conn = HTTPConnection("127.0.0.1", server.port, timeout=5)
            try:
                conn.request("GET", "/health")
                response = conn.getresponse()
                response.read()
                headers = response.headers

                assert headers.get("X-Content-Type-Options") == "nosniff"
                assert headers.get("X-Frame-Options") == "DENY"
                assert headers.get("X-XSS-Protection") == "1; mode=block"
                assert headers.get("Content-Security-Policy") == "default-src 'self'"
            finally:
                conn.close()
        finally:
            server.stop()


class TestRateLimiting:
    """Test rate limiting returns 429 after exceeding threshold."""

    def test_rate_limit_exceeded_returns_429(self, mock_health_monitor):
        """Verify rate limit returns 429 after 60+ requests."""
        from homelab_manager.server.app import RateLimiter

        # Create a fresh rate limiter and server for this test
        limiter = RateLimiter()
        server = HTTPServerFixture(mock_health_monitor, rate_limiter=limiter)
        server.start()
        try:
            # Make 61 requests to the same server
            for i in range(61):
                status, _ = server.request("/health")
                if i < 60:
                    assert status == 200, f"Request {i} should be 200, got {status}"
                else:
                    # 61st request should be rate limited
                    assert (
                        status == 429
                    ), f"Request {i} should be 429 (rate limited), got {status}"
        finally:
            server.stop()

    def test_rate_limit_response_is_json(self, mock_health_monitor):
        """Verify 429 response is valid JSON with error message."""
        from homelab_manager.server.app import RateLimiter

        limiter = RateLimiter()
        server = HTTPServerFixture(mock_health_monitor, rate_limiter=limiter)
        server.start()
        try:
            # Exceed rate limit
            for _ in range(61):
                server.request("/health")

            status, body = server.request("/health")
            assert status == 429
            data = json.loads(body)
            assert data == {"error": "Too many requests"}
        finally:
            server.stop()

    def test_rate_limit_has_security_headers(self, mock_health_monitor):
        """Verify 429 response includes security headers."""
        from http.client import HTTPConnection

        from homelab_manager.server.app import RateLimiter

        limiter = RateLimiter()
        server = HTTPServerFixture(mock_health_monitor, rate_limiter=limiter)
        server.start()
        try:
            # Exceed rate limit
            for _ in range(61):
                server.request("/health")

            conn = HTTPConnection("127.0.0.1", server.port, timeout=5)
            try:
                conn.request("GET", "/health")
                response = conn.getresponse()
                response.read()
                headers = response.headers

                assert headers.get("X-Content-Type-Options") == "nosniff"
                assert headers.get("X-Frame-Options") == "DENY"
                assert headers.get("X-XSS-Protection") == "1; mode=block"
                assert headers.get("Content-Security-Policy") == "default-src 'self'"
            finally:
                conn.close()
        finally:
            server.stop()


class TestQueryParameterValidation:
    """Test query parameter validation for 'lines' parameter."""

    def test_valid_lines_parameter_accepted(self, http_server):
        """Verify valid 'lines' parameter (1-10000) is accepted."""
        status, _ = http_server.request("/health?lines=100")
        assert status == 200

    def test_invalid_lines_parameter_returns_400(self, http_server):
        """Verify invalid 'lines' parameter returns 400."""
        status, body = http_server.request("/health?lines=invalid")
        assert status == 400
        data = json.loads(body)
        assert data == {"error": "lines must be an integer between 1 and 10000"}

    def test_lines_parameter_zero_returns_400(self, http_server):
        """Verify 'lines' parameter value 0 returns 400."""
        status, body = http_server.request("/health?lines=0")
        assert status == 400
        data = json.loads(body)
        assert data == {"error": "lines must be an integer between 1 and 10000"}

    def test_lines_parameter_negative_returns_400(self, http_server):
        """Verify negative 'lines' parameter returns 400."""
        status, body = http_server.request("/health?lines=-5")
        assert status == 400
        data = json.loads(body)
        assert data == {"error": "lines must be an integer between 1 and 10000"}

    def test_lines_parameter_too_large_returns_400(self, http_server):
        """Verify 'lines' parameter > 10000 returns 400."""
        status, body = http_server.request("/health?lines=10001")
        assert status == 400
        data = json.loads(body)
        assert data == {"error": "lines must be an integer between 1 and 10000"}

    def test_lines_parameter_boundary_min(self, http_server):
        """Verify 'lines' parameter value 1 is accepted."""
        status, _ = http_server.request("/health?lines=1")
        assert status == 200

    def test_lines_parameter_boundary_max(self, http_server):
        """Verify 'lines' parameter value 10000 is accepted."""
        status, _ = http_server.request("/health?lines=10000")
        assert status == 200

    def test_lines_parameter_validation_has_security_headers(self, http_server):
        """Verify 400 response for invalid lines includes security headers."""
        from http.client import HTTPConnection

        conn = HTTPConnection("127.0.0.1", http_server.port, timeout=5)
        try:
            conn.request("GET", "/health?lines=invalid")
            response = conn.getresponse()
            response.read()
            headers = response.headers

            assert headers.get("X-Content-Type-Options") == "nosniff"
            assert headers.get("X-Frame-Options") == "DENY"
            assert headers.get("X-XSS-Protection") == "1; mode=block"
            assert headers.get("Content-Security-Policy") == "default-src 'self'"
        finally:
            conn.close()
