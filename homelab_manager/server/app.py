"""Lightweight HTTP server for homelab_manager API endpoints."""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from homelab_manager import __version__
from homelab_manager.models.service import ServiceRegistry
from homelab_manager.services.health import HealthMonitor

from .routes import handle_health, handle_status, handle_summary

logger = logging.getLogger(__name__)

_ROUTES = {
    "/health": "health",
    "/status": "status",
    "/summary": "summary",
}


def _make_handler(health_monitor: HealthMonitor):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default access log
            logger.debug(fmt, *args)

        def _send(self, status_code: int, body: str):
            encoded = body.encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            route = _ROUTES.get(self.path)
            if route == "health":
                code, body = handle_health(__version__)
            elif route == "status":
                code, body = handle_status(health_monitor)
            elif route == "summary":
                code, body = handle_summary(health_monitor)
            else:
                code = 404
                body = json.dumps({"error": "not found"})
            self._send(code, body)

    return _Handler


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    port = int(os.environ.get("HOMELAB_MANAGER_HTTP_PORT", port))
    registry = ServiceRegistry()
    monitor = HealthMonitor(registry=registry)
    handler = _make_handler(monitor)
    server = HTTPServer((host, port), handler)
    logger.info("Listening on %s:%d", host, port)
    print(f"Listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
