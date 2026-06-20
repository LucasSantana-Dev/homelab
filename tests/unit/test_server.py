"""Unit tests for homelab_manager HTTP server."""

import json
from unittest.mock import MagicMock, patch

from homelab_manager.server.routes import handle_health, handle_status, handle_summary


class TestHandleHealth:
    def test_returns_ok_status(self):
        code, body = handle_health("1.2.3")
        assert code == 200
        data = json.loads(body)
        assert data["status"] == "ok"
        assert data["version"] == "1.2.3"
        assert "timestamp" in data

    def test_timestamp_is_utc_iso(self):
        _, body = handle_health("0.0.1")
        data = json.loads(body)
        assert (
            data["timestamp"].endswith("+00:00")
            or data["timestamp"].endswith("Z")
            or "T" in data["timestamp"]
        )


class TestHandleStatus:
    def test_delegates_to_check_all_services(self):
        monitor = MagicMock()
        monitor.check_all_services.return_value = {"svc-a": {"status": "healthy"}}
        code, body = handle_status(monitor)
        assert code == 200
        data = json.loads(body)
        assert data == {"svc-a": {"status": "healthy"}}
        monitor.check_all_services.assert_called_once()

    def test_empty_services(self):
        monitor = MagicMock()
        monitor.check_all_services.return_value = {}
        code, body = handle_status(monitor)
        assert code == 200
        assert json.loads(body) == {}


class TestHandleSummary:
    def _monitor(self, total=3, healthy=2, unhealthy=1, services=None):
        m = MagicMock()
        m.get_health_summary.return_value = {
            "total_services": total,
            "healthy_services": healthy,
            "unhealthy_services": unhealthy,
            "services": {k: {} for k in (services or ["a", "b", "c"])},
        }
        return m

    def test_normalises_shape(self):
        monitor = self._monitor()
        code, body = handle_summary(monitor)
        assert code == 200
        data = json.loads(body)
        assert data["total"] == 3
        assert data["healthy"] == 2
        assert data["unhealthy"] == 1
        assert data["unknown"] == 0
        assert set(data["services"]) == {"a", "b", "c"}

    def test_unknown_clamped_to_zero(self):
        monitor = MagicMock()
        monitor.get_health_summary.return_value = {
            "total_services": 2,
            "healthy_services": 2,
            "unhealthy_services": 2,
            "services": {"a": {}, "b": {}},
        }
        _, body = handle_summary(monitor)
        data = json.loads(body)
        assert data["unknown"] == 0

    def test_missing_totals_falls_back_to_services_count(self):
        monitor = MagicMock()
        monitor.get_health_summary.return_value = {
            "services": {"x": {}, "y": {}},
        }
        _, body = handle_summary(monitor)
        data = json.loads(body)
        assert data["total"] == 2
        assert data["healthy"] == 0
        assert data["unhealthy"] == 0


class TestRunServer:
    """#217: run_server port override + graceful shutdown."""

    def _patched(self):
        # Patch everything run_server touches so nothing binds or serves.
        return patch.multiple(
            "homelab_manager.server.app",
            HTTPServer=MagicMock(),
            ServiceRegistry=MagicMock(),
            HealthMonitor=MagicMock(),
            setup_logging=MagicMock(),
        )

    def test_env_overrides_port_argument(self, monkeypatch):
        from homelab_manager.server import app as appmod

        monkeypatch.setenv("HOMELAB_MANAGER_HTTP_PORT", "9999")
        with self._patched():
            appmod.run_server(host="127.0.0.1", port=8765)
            # HTTPServer((host, port), handler) — env port wins over the 8765 arg.
            (bind_addr, _handler), _ = appmod.HTTPServer.call_args
        assert bind_addr == ("127.0.0.1", 9999)

    def test_argument_port_used_when_env_absent(self, monkeypatch):
        from homelab_manager.server import app as appmod

        monkeypatch.delenv("HOMELAB_MANAGER_HTTP_PORT", raising=False)
        with self._patched():
            appmod.run_server(host="0.0.0.0", port=8765)
            (bind_addr, _handler), _ = appmod.HTTPServer.call_args
        assert bind_addr == ("0.0.0.0", 8765)

    def test_keyboardinterrupt_shuts_down_cleanly(self, monkeypatch):
        from homelab_manager.server import app as appmod

        monkeypatch.delenv("HOMELAB_MANAGER_HTTP_PORT", raising=False)
        server = MagicMock()
        server.serve_forever.side_effect = KeyboardInterrupt
        with self._patched():
            appmod.HTTPServer.return_value = server
            appmod.run_server()  # must NOT raise
        server.server_close.assert_called_once()  # always closed in finally


class TestServeCommand:
    """#216: the `serve` CLI command wires through to run_server."""

    def test_serve_invokes_run_server(self):
        from typer.testing import CliRunner

        from homelab_manager.cli import create_app

        with patch("homelab_manager.cli.commands.run_server") as mock_run:
            app = create_app()
            result = CliRunner().invoke(
                app, ["serve", "--host", "0.0.0.0", "--port", "1234"]
            )
        assert result.exit_code == 0
        mock_run.assert_called_once_with(host="0.0.0.0", port=1234)
