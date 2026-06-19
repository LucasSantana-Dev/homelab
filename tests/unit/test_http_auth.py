"""Unit tests for HTTP server authentication."""

from unittest.mock import MagicMock, patch

import pytest

from homelab_manager.server.app import _make_handler


@pytest.fixture
def health_monitor():
    """Mock health monitor."""
    monitor = MagicMock()
    monitor.check_all_services.return_value = {"test": {"status": "healthy"}}
    return monitor


class MockHeaders:
    """Mock HTTP headers dict."""

    def __init__(self, headers=None):
        self._headers = headers or {}

    def get(self, key, default=None):
        return self._headers.get(key, default)


class TestCheckAuthMethod:
    """Test the _check_auth method in isolation."""

    def test_check_auth_passes_with_correct_key(self, health_monitor, monkeypatch):
        """Correct API key should pass authentication."""
        monkeypatch.setenv("HOMELAB_API_KEY", "secret-key-123")
        handler_class = _make_handler(health_monitor)

        # Create a minimal mock handler
        handler = MagicMock(spec=handler_class)
        handler.headers = MockHeaders({"X-API-Key": "secret-key-123"})

        # Call the real _check_auth method
        auth_result = handler_class._check_auth(handler)
        assert auth_result is True

    def test_check_auth_fails_with_wrong_key(self, health_monitor, monkeypatch):
        """Wrong API key should fail authentication."""
        monkeypatch.setenv("HOMELAB_API_KEY", "secret-key-123")
        handler_class = _make_handler(health_monitor)

        handler = MagicMock(spec=handler_class)
        handler.headers = MockHeaders({"X-API-Key": "wrong-key"})

        auth_result = handler_class._check_auth(handler)
        assert auth_result is False

    def test_check_auth_fails_without_key_header(self, health_monitor, monkeypatch):
        """Missing X-API-Key header should fail when key is configured."""
        monkeypatch.setenv("HOMELAB_API_KEY", "secret-key-123")
        handler_class = _make_handler(health_monitor)

        handler = MagicMock(spec=handler_class)
        handler.headers = MockHeaders({})

        auth_result = handler_class._check_auth(handler)
        assert auth_result is False

    def test_check_auth_passes_when_no_key_configured(
        self, health_monitor, monkeypatch
    ):
        """Should pass when HOMELAB_API_KEY is not set."""
        monkeypatch.delenv("HOMELAB_API_KEY", raising=False)
        handler_class = _make_handler(health_monitor)

        handler = MagicMock(spec=handler_class)
        handler.headers = MockHeaders({})

        auth_result = handler_class._check_auth(handler)
        assert auth_result is True

    def test_check_auth_passes_without_key_when_env_not_set(
        self, health_monitor, monkeypatch
    ):
        """Should pass with any key when HOMELAB_API_KEY is not set."""
        monkeypatch.delenv("HOMELAB_API_KEY", raising=False)
        handler_class = _make_handler(health_monitor)

        handler = MagicMock(spec=handler_class)
        handler.headers = MockHeaders({"X-API-Key": "any-key"})

        auth_result = handler_class._check_auth(handler)
        assert auth_result is True


class TestRunServerLogging:
    """Test that run_server logs warning when API key not set."""

    def test_logs_warning_when_api_key_not_set(self, monkeypatch, caplog):
        """Should log WARNING when HOMELAB_API_KEY is not set."""
        monkeypatch.delenv("HOMELAB_API_KEY", raising=False)

        # Mock the HTTPServer to avoid actually binding to a port
        with patch("homelab_manager.server.app.HTTPServer"):
            with patch("homelab_manager.server.app.ServiceRegistry"):
                with patch("homelab_manager.server.app.HealthMonitor"):
                    from homelab_manager.server.app import run_server

                    try:
                        run_server(host="127.0.0.1", port=9999)
                    except Exception:
                        pass

                    # Check that warning was logged
                    assert any(
                        "HOMELAB_API_KEY not set" in record.message
                        for record in caplog.records
                        if record.levelname == "WARNING"
                    )

    def test_no_warning_when_api_key_set(self, monkeypatch, caplog):
        """Should not log WARNING when HOMELAB_API_KEY is set."""
        monkeypatch.setenv("HOMELAB_API_KEY", "test-key")

        with patch("homelab_manager.server.app.HTTPServer"):
            with patch("homelab_manager.server.app.ServiceRegistry"):
                with patch("homelab_manager.server.app.HealthMonitor"):
                    from homelab_manager.server.app import run_server

                    try:
                        run_server(host="127.0.0.1", port=9999)
                    except Exception:
                        pass

                    # Check that no such warning was logged
                    assert not any(
                        "HOMELAB_API_KEY not set" in record.message
                        for record in caplog.records
                        if record.levelname == "WARNING"
                    )
