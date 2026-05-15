"""Route handlers for homelab_manager HTTP API."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple


def _json_response(data: Any) -> Tuple[int, str]:
    return 200, json.dumps(data, default=str)


def handle_health(version: str) -> Tuple[int, str]:
    return _json_response(
        {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": version,
        }
    )


def handle_status(health_monitor) -> Tuple[int, str]:
    status = health_monitor.check_all_services()
    return _json_response(status)


def handle_summary(health_monitor) -> Tuple[int, str]:
    raw = health_monitor.get_health_summary()
    # Normalise to the shape promised by the spec
    services_dict: Dict[str, Dict] = raw.get("services", {})
    total = raw.get("total_services", len(services_dict))
    healthy = raw.get("healthy_services", 0)
    unhealthy = raw.get("unhealthy_services", 0)
    unknown = total - healthy - unhealthy
    return _json_response(
        {
            "total": total,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unknown": max(unknown, 0),
            "services": list(services_dict.keys()),
        }
    )
