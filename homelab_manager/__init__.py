"""
Homelab Manager
Modern Python CLI for homelab management
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("homelab-manager")
except PackageNotFoundError:
    __version__ = "2.4.0"  # Fallback for development

__author__ = "Luk Homelab"
__description__ = "Modern homelab management CLI"

from .cli import create_app
from .core import HomelabConfig
from .models import ServiceRegistry
from .services import ContainerManager, HealthMonitor, UpdateManager

__all__ = [
    "create_app",
    "HomelabConfig",
    "ContainerManager",
    "HealthMonitor",
    "UpdateManager",
    "ServiceRegistry",
]
