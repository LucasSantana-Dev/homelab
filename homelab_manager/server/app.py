"""Lightweight HTTP server for homelab_manager API endpoints."""

import collections
import json
import logging
import os
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast
from urllib.parse import parse_qs, urlparse

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

# Security headers to add to all responses
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Content-Security-Policy": "default-src 'self'",
}


class RateLimiter:
    """Per-IP rate limiter using sliding window (60 requests per 60 seconds)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: collections.defaultdict[str, list[float]] = (
            collections.defaultdict(list)
        )

    def is_allowed(self, client_ip: str) -> bool:
        """Check if client is within rate limit; return True if allowed."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Remove old timestamps outside the window
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] if ts > cutoff
        ]

        # Check if under limit
        if len(self.requests[client_ip]) < self.max_requests:
            self.requests[client_ip].append(now)
            return True
        return False


_rate_limiter = RateLimiter()


def _make_handler(
    health_monitor: HealthMonitor, rate_limiter: "RateLimiter | None" = None
) -> type[BaseHTTPRequestHandler]:
    _actual_rate_limiter: RateLimiter = rate_limiter or _rate_limiter

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default access log
            logger.debug(fmt, *args)

        def _send_secure_response(self, status_code: int, body: str) -> None:
            """Send response with security headers and proper encoding."""
            encoded = body.encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            # Add security headers to all responses
            for header, value in _SECURITY_HEADERS.items():
                self.send_header(header, value)
            self.end_headers()
            self.wfile.write(encoded)

        def _check_auth(self) -> bool:
            """Check X-API-Key header if API key is configured."""
            api_key = os.environ.get("HOMELAB_API_KEY")
            if not api_key:
                return True
            provided_key = self.headers.get("X-API-Key")
            if not secrets.compare_digest(provided_key or "", api_key):
                return False
            return True

        def _check_rate_limit(self) -> bool:
            """Check if client IP is within rate limit."""
            client_ip = self.client_address[0]
            return _actual_rate_limiter.is_allowed(client_ip)

        def _validate_query_param_lines(self) -> tuple[bool, str | None]:
            """
            Validate 'lines' query parameter if present.
            Returns (is_valid, error_message).
            """
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if "lines" not in params:
                return True, None

            lines_values = params["lines"]
            if not lines_values:
                return False, "lines parameter is empty"

            lines_str = lines_values[0]
            try:
                lines = int(lines_str)
                if lines < 1 or lines > 10000:
                    return (
                        False,
                        "lines must be an integer between 1 and 10000",
                    )
                return True, None
            except ValueError:
                return False, "lines must be an integer between 1 and 10000"

        def do_GET(self):
            # Check auth first
            if not self._check_auth():
                self._send_secure_response(401, json.dumps({"error": "Unauthorized"}))
                return

            # Check rate limit after auth but before route dispatch
            if not self._check_rate_limit():
                self._send_secure_response(
                    429, json.dumps({"error": "Too many requests"})
                )
                return

            # Validate query parameters
            is_valid, error_msg = self._validate_query_param_lines()
            if not is_valid:
                self._send_secure_response(400, json.dumps({"error": error_msg}))
                return

            # Route dispatch
            route = _ROUTES.get(self.path.split("?")[0])
            if route == "health":
                code, body = handle_health(__version__)
            elif route == "status":
                code, body = handle_status(health_monitor)
            elif route == "summary":
                code, body = handle_summary(health_monitor)
            else:
                code = 404
                body = json.dumps({"error": "not found"})
            self._send_secure_response(code, body)

    return _Handler


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    port = int(os.environ.get("HOMELAB_MANAGER_HTTP_PORT", port))
    api_key = os.environ.get("HOMELAB_API_KEY")
    if not api_key:
        logger.warning("HOMELAB_API_KEY not set — all HTTP endpoints are unprotected")
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
