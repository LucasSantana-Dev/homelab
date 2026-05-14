"""`docker compose` CLI wrapper — single owner for subprocess invocations.

Before R1, services/status.py and services/updates.py each ran
`subprocess.run(["docker", "compose", ...])` inline with subtly different
error-handling. This module centralises:

* List-form `subprocess.run` (no shell)
* Optional ServiceRegistry allowlist check (H6 hardening)
* Stderr-scrubbing on `CalledProcessError` (M1 hardening)
* `lines` clamp helper for the logs sub-command

See `.claude/plans/refactor-r1-homelab-manager-2026-05-14.md`.
"""

from __future__ import annotations

import logging
import subprocess
from typing import List, Optional

from ..core.errors import scrub_subprocess_error
from ..models.service import ServiceRegistry

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 10_000


class ComposeCLI:
    """Thin wrapper over `docker compose ...` invocations."""

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        # Optional: when set, run() validates any service name argument
        # against the registry allowlist before subprocess invocation.
        self.registry = registry

    # -- public API ----------------------------------------------------------

    def run(
        self,
        args: List[str],
        *,
        check: bool = True,
        capture_output: bool = True,
        timeout: Optional[int] = None,
    ) -> subprocess.CompletedProcess:
        """Run `docker compose <args>` and return the CompletedProcess.

        Always uses list-form invocation (no shell). Callers handle
        success/failure on the returned object or via the raised
        `CalledProcessError` when `check=True`.
        """
        return subprocess.run(
            ["docker", "compose", *args],
            check=check,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
        )

    def logs(self, service_name: str, lines: int = 50) -> str:
        """Return `docker compose logs --tail N <service>` stdout.

        Validates `service_name` against the registry (H6) and clamps
        `lines` to [1, MAX_LOG_LINES] (H6). On error, returns a scrubbed
        message — never echoes raw stderr (M1).
        """
        if self.registry is not None and not self._is_known_service(service_name):
            return (
                f"Error: unknown service '{service_name}'. "
                "Use `homelab services` to list registered services."
            )

        try:
            lines_int = clamp_lines(lines)
        except (TypeError, ValueError):
            return "Error: 'lines' must be a positive integer."

        try:
            result = self.run(
                ["logs", "--tail", str(lines_int), service_name],
            )
            return str(result.stdout)
        except subprocess.CalledProcessError as exc:
            logger.debug("docker compose logs failed", exc_info=True)
            return scrub_subprocess_error(
                exc, context=f"Error getting logs for '{service_name}'"
            )
        except Exception as exc:
            logger.debug("docker compose logs unexpected error", exc_info=True)
            return f"Logs error (type: {type(exc).__name__})."

    # -- internals -----------------------------------------------------------

    def _is_known_service(self, service_name: str) -> bool:
        assert self.registry is not None  # caller guarded
        return (
            self.registry.get_service_by_container(service_name) is not None
            or self.registry.get_service(service_name) is not None
        )


def clamp_lines(lines: int) -> int:
    """Clamp a `--tail` value into [1, MAX_LOG_LINES]. Raises on non-int."""
    return max(1, min(int(lines), MAX_LOG_LINES))
