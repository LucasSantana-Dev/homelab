"""Route handlers for homelab_manager HTTP API."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


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


_HERMES_STATE_FILE = os.environ.get(
    "HERMES_STATE_FILE", "/home/luk-server/agent-logs/hermes-state.json"
)
_HERMES_LOG_DIR = os.environ.get("HERMES_LOG_DIR", "/home/luk-server/agent-logs")


def handle_hermes() -> Tuple[int, str]:
    """Return hermes agent job stats from the state file written by hermes scripts."""
    try:
        with open(_HERMES_STATE_FILE) as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read hermes state file: %s", e, exc_info=True)
        return 500, json.dumps({"error": "state file unreadable"})

    now = datetime.now(timezone.utc).isoformat()
    return _json_response({"timestamp": now, "jobs": state})


def handle_hermes_logs(lines: int = 50) -> Tuple[int, str]:
    """Return recent lines from the latest hermes PR review log."""
    import glob

    pattern = os.path.join(_HERMES_LOG_DIR, "hermes-pr-review-*.log")
    log_files = sorted(glob.glob(pattern), reverse=True)
    if not log_files:
        return _json_response({"lines": [], "file": None})

    latest = log_files[0]
    try:
        with open(latest) as f:
            all_lines = f.readlines()
        tail = [line.rstrip() for line in all_lines[-lines:]]
    except OSError as e:
        logger.error("Failed to read hermes log file %s: %s", latest, e, exc_info=True)
        return 500, json.dumps({"error": "log unreadable"})

    return _json_response({"lines": tail, "file": os.path.basename(latest)})


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
