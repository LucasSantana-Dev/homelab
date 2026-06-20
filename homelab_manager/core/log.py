#!/usr/bin/env python3
"""Concurrency-aware logging.

The health sweep checks services in parallel (``ThreadPoolExecutor`` with up to
20 workers in :mod:`homelab_manager.services.health`), so log lines from
different services interleave with no way to tell them apart. This module adds a
``contextvars``-based **trace id** that is stamped onto every log record and
printed in the log line, so you can follow one logical operation (one service
check, one HTTP request) through the interleaved output, e.g.::

    journalctl -u homelab-manager | grep '[grafana]'

The trace id defaults to ``"-"`` and is set per concurrent unit via
:func:`trace_context`. The text format is preserved (greppable); nothing about
existing call sites changes.
"""

import logging
import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

# Active trace id for the current context (thread/task). Each ThreadPoolExecutor
# worker has its own context, so setting this inside a worker never bleeds into
# the main thread or a sibling worker.
_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")

# asctime  LEVEL  [trace_id]  [threadName]  logger.name: message
LOG_FORMAT = (
    "%(asctime)s %(levelname)-7s [%(trace_id)s] [%(threadName)s] %(name)s: %(message)s"
)

_configured = False
_old_factory = logging.getLogRecordFactory()


def get_trace_id() -> str:
    """Return the trace id active in the current context."""
    return _trace_id.get()


def new_trace_id(prefix: str = "") -> str:
    """Generate a short, human-greppable trace id (optionally prefixed)."""
    short = uuid.uuid4().hex[:8]
    return f"{prefix}-{short}" if prefix else short


@contextmanager
def trace_context(trace_id: str) -> Iterator[str]:
    """Bind ``trace_id`` to the current context for the duration of the block.

    Restores the previous value on exit, so reused thread-pool workers never
    leak a previous task's id. Safe to nest.
    """
    token: Token = _trace_id.set(trace_id)
    try:
        yield trace_id
    finally:
        _trace_id.reset(token)


def _record_factory(*args, **kwargs) -> logging.LogRecord:
    """Stamp every LogRecord with the current trace id at creation time.

    Reading the contextvar here (rather than in a handler filter) guarantees
    ``record.trace_id`` exists for every record regardless of which handler
    formats it, so ``%(trace_id)s`` in the format string can never KeyError.
    """
    record = _old_factory(*args, **kwargs)
    record.trace_id = _trace_id.get()
    return record


def setup_logging(level: Optional[str] = None, force: bool = False) -> None:
    """Install the trace-aware formatter on the root logger. Idempotent.

    Level resolves from the ``level`` arg, then ``HOMELAB_LOG_LEVEL``, then
    ``LOG_LEVEL``, defaulting to ``INFO``. Call once at process entry (the CLI
    and the HTTP server both call it).
    """
    global _configured
    if _configured and not force:
        return

    lvl_name = (
        level
        or os.environ.get("HOMELAB_LOG_LEVEL")
        or os.environ.get("LOG_LEVEL")
        or "INFO"
    ).upper()
    lvl = getattr(logging, lvl_name, logging.INFO)

    logging.setLogRecordFactory(_record_factory)

    root = logging.getLogger()
    # Drop any handler we previously installed so re-config doesn't duplicate.
    root.handlers = [
        h for h in root.handlers if not getattr(h, "_homelab_trace", False)
    ]
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler._homelab_trace = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(lvl)

    _configured = True
