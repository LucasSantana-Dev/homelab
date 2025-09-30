"""
Homelab Manager Package
Python-based automation system for homelab management
"""

__version__ = "2.0.0"
__author__ = "Luk"
__email__ = "luk@homelab.example.com"

# Import main classes
from .automation import HomelabAutomation
from .cli import HomelabCLI
from .config import HomelabConfig
from .health import HomelabHealthMonitor
from .updates import HomelabUpdateManager

__all__ = [
    "HomelabAutomation",
    "HomelabHealthMonitor",
    "HomelabUpdateManager",
    "HomelabConfig",
    "HomelabCLI",
]
