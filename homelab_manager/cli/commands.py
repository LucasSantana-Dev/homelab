#!/usr/bin/env python3
"""
CLI Commands — Shim module that delegates to specialized command modules
Command definitions for homelab management
"""

from typing import Optional

import typer

from ..core.config import HomelabConfig
from ..models.service import ServiceRegistry
from ..services.containers import ContainerManager
from ..services.health import HealthMonitor
from ..services.updates import UpdateManager
from .status_commands import register_status_commands
from .management_commands import register_management_commands


def create_app(
    config_manager: Optional[HomelabConfig] = None,
    container_manager: Optional[ContainerManager] = None,
    health_monitor: Optional[HealthMonitor] = None,
    update_manager: Optional[UpdateManager] = None,
    registry: Optional[ServiceRegistry] = None,
) -> typer.Typer:
    """Create the main CLI app with all commands

    Args:
        config_manager: Optional HomelabConfig instance for testing
        container_manager: Optional ContainerManager instance for testing
        health_monitor: Optional HealthMonitor instance for testing
        update_manager: Optional UpdateManager instance for testing
        registry: Optional ServiceRegistry instance for testing
    """

    app = typer.Typer(
        name="homelab",
        help="Modern homelab management CLI",
        add_completion=False,
        rich_markup_mode="rich",
    )

    # Initialize managers with dependency injection
    _registry = registry or ServiceRegistry()
    _config_manager = config_manager or HomelabConfig()
    _container_manager = container_manager or ContainerManager()
    _health_monitor = health_monitor or HealthMonitor(registry=_registry)
    _update_manager = update_manager or UpdateManager(registry=_registry)

    # Register command groups
    register_status_commands(
        app, _config_manager, _container_manager, _health_monitor, _registry
    )
    register_management_commands(
        app, _config_manager, _container_manager, _update_manager, _registry
    )

    return app
