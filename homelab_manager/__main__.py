"""
Main entry point for homelab manager
"""

from .cli import create_app

if __name__ == "__main__":
    app = create_app()
    app()
