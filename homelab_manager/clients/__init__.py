"""Low-level external-resource clients (Docker SDK, docker-compose CLI, …).

Services consume these so each external dependency has exactly one owner and
one mock seam. See `.claude/plans/refactor-r1-homelab-manager-2026-05-14.md`.
"""

from .compose_cli import MAX_LOG_LINES, ComposeCLI, clamp_lines
from .docker_client import DockerClientFactory, get_docker_client

__all__ = [
    "ComposeCLI",
    "DockerClientFactory",
    "MAX_LOG_LINES",
    "clamp_lines",
    "get_docker_client",
]
