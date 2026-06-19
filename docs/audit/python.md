# Python Audit — homelab_manager

> **Historical snapshot (2026-04-14)** — This is part of the homelab audit series. Refer to the audit README for current status and follow-up PRs.

## LOC per file
 1672 total
  315 homelab_manager/cli/commands.py
  312 homelab_manager/services/containers.py
  207 homelab_manager/services/health.py
  196 homelab_manager/core/config.py
  191 homelab_manager/services/updates.py
  154 homelab_manager/models/service.py
  144 homelab_manager/utils/display.py
   73 homelab_manager/utils/validators.py
   28 homelab_manager/__init__.py
    9 homelab_manager/services/__init__.py
    9 homelab_manager/__main__.py
    8 homelab_manager/utils/__init__.py
    8 homelab_manager/models/__init__.py
    7 homelab_manager/core/__init__.py
    7 homelab_manager/cli/__init__.py
    4 homelab_manager/data/__init__.py

## Cognitive complexity (radon CC, top 25 worst)

## Maintainability Index (radon MI, worst files)
homelab_manager/cli/__init__.py - A (100.00)
homelab_manager/core/__init__.py - A (100.00)
homelab_manager/data/__init__.py - A (100.00)
homelab_manager/__init__.py - A (100.00)
homelab_manager/__main__.py - A (100.00)
homelab_manager/models/__init__.py - A (100.00)
homelab_manager/services/__init__.py - A (100.00)
homelab_manager/utils/__init__.py - A (100.00)
homelab_manager/services/health.py - A (46.60)
homelab_manager/models/service.py - A (47.04)
homelab_manager/services/containers.py - A (51.48)
homelab_manager/cli/commands.py - A (52.95)
homelab_manager/core/config.py - A (53.38)
homelab_manager/utils/display.py - A (59.10)
homelab_manager/services/updates.py - A (63.30)

## Dead code (vulture, confidence ≥70)

## Files >300 LOC (God-object candidates)
  312 homelab_manager/services/containers.py
  315 homelab_manager/cli/commands.py
 1672 total

## Test coverage (rough — module×test presence)
homelab_manager/cli — py=1 tests-referencing=5
homelab_manager/services — py=3 tests-referencing=4
homelab_manager/core — py=1 tests-referencing=1
homelab_manager/utils — py=2 tests-referencing=0
