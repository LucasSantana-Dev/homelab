"""Unit tests for homelab_manager HTTP server."""

import json
from unittest.mock import MagicMock

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
