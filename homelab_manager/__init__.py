"""
Homelab Manager
Modern Python CLI for homelab management
"""

__version__ = "2.0.0"
__author__ = "Luk Homelab"
__description__ = "Modern homelab management CLI"

from .cli import create_app
from .core import HomelabConfig
from .services import ContainerManager, HealthMonitor, UpdateManager

__all__ = [
    "create_app",
    "HomelabConfig",
    "ContainerManager",
    "HealthMonitor",
    "UpdateManager",
]
