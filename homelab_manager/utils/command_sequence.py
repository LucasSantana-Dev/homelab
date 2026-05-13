#!/usr/bin/env python3
"""
CommandSequence — atomic multi-step subprocess execution.

Each Step is a labeled subprocess command. CommandSequence.run() executes
them in order and returns on the first failure, so callers never see a
partial-success state with no error attached.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Step:
    cmd: List[str]
    label: str
    check: bool = True
    cwd: Optional[Path] = None


class CommandSequence:
    def __init__(self, steps: List[Step], cwd: Optional[Path] = None):
        self._steps = steps
        self._cwd = cwd

    def run(self) -> Dict:
        """Execute all steps in order. Returns {"success": True} or {"success": False, "error": ...}."""
        for step in self._steps:
            effective_cwd = step.cwd or self._cwd
            try:
                subprocess.run(
                    step.cmd,
                    capture_output=True,
                    text=True,
                    check=step.check,
                    cwd=effective_cwd,
                )
            except subprocess.CalledProcessError as e:
                return {
                    "success": False,
                    "error": f"{step.label} failed: {e.stderr.strip()}",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"{step.label} error: {str(e)}",
                }
        return {"success": True}
