#!/usr/bin/env python3
"""Compatibility wrapper for legacy container status entrypoint."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parents[2]
    os.chdir(project_root)
    result = subprocess.run(["python3", "-m", "homelab_manager", "status"], check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
