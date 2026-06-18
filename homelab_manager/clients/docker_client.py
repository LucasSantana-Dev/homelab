"""Docker SDK client factory — single owner for `docker.from_env()`.

Before R1, `services/status.py` and `services/health.py` each called
`docker.from_env()` directly with subtly different error-handling. This module
centralises both: callers get back either a `DockerClient` or `None`, and tests
have one seam to patch (`homelab_manager.clients.docker_client.docker`).
"""

from __future__ import annotations

import logging
from typing import Optional

import docker  # noqa: F401  (kept top-level so it's the canonical patch seam)
from docker import DockerClient

logger = logging.getLogger(__name__)


class DockerClientFactory:
    """Lazy singleton accessor for the Docker SDK client.

    `health.py` historically wrapped `docker.from_env()` in try/except and
    stored `None` on failure; `status.py` let the exception propagate. This
    factory keeps the safer behaviour (fallback to `None`) and offers an
    `is_available()` helper so callers don't have to repeat the None-check.
    """

    _instance: "Optional[DockerClientFactory]" = None
    _client: Optional[DockerClient] = None
    _probed: bool = False

    @classmethod
    def instance(cls) -> "DockerClientFactory":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_client(self) -> Optional[DockerClient]:
        """Return a cached `DockerClient`, or `None` if the daemon is unreachable.

        The first call probes `docker.from_env()`. Subsequent calls return the
        cached result without re-probing — call `reset()` if you want to retry.
        """
        if not self._probed:
            try:
                self._client = docker.from_env()
                self._probed = True
            except Exception:
                logger.debug("docker.from_env() failed", exc_info=True)
                self._client = None
        return self._client

    def is_available(self) -> bool:
        return self.get_client() is not None

    def reset(self) -> None:
        """Drop the cached client; next `get_client()` will re-probe.

        Intended for tests and for `homelab status --retry` style flows.
        """
        self._client = None
        self._probed = False


def get_docker_client() -> Optional[DockerClient]:
    """Module-level convenience accessor used by service classes."""
    return DockerClientFactory.instance().get_client()
