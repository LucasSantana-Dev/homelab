"""Low-level external-resource clients (Docker SDK, docker-compose CLI, …).

Services consume these so each external dependency has exactly one owner and
one mock seam. See `.claude/plans/refactor-r1-homelab-manager-2026-05-14.md`.
"""

from . import docker_client  # noqa: F401  (re-export so old patches still resolve)
from .docker_client import DockerClientFactory, get_docker_client

__all__ = ["DockerClientFactory", "get_docker_client", "docker_client"]
