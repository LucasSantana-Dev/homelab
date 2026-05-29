#!/usr/bin/env python3
"""
CommandSequence — atomic multi-step subprocess execution.

Each Step is a labeled subprocess command. CommandSequence.run() executes
them in order and returns on the first failure, so callers never see a
partial-success state with no error attached.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..core.errors import scrub_subprocess_error

logger = logging.getLogger(__name__)


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
                logger.debug("command sequence step failed", exc_info=True)
                return {
                    "success": False,
                    "error": scrub_subprocess_error(e, context=f"{step.label} failed"),
                }
            except Exception as e:
                logger.debug("command sequence step failed", exc_info=True)
                return {
                    "success": False,
                    "error": scrub_subprocess_error(e, context=f"{step.label} failed"),
                }
        return {"success": True}
