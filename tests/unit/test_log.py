#!/usr/bin/env python3
"""Unit tests for homelab_manager.core.log — the concurrency-aware trace id.

Covers the contextvar set/reset semantics, the LogRecord factory stamping,
idempotent setup, and the headline guarantee: parallel ThreadPoolExecutor
workers each carry their own trace id in their log records (no cross-bleed).
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import pytest

from homelab_manager.core.log import (
    LOG_FORMAT,
    get_trace_id,
    new_trace_id,
    setup_logging,
    trace_context,
)


@pytest.fixture(autouse=True)
def _ensure_factory():
    """Install the trace factory once; restore the previous factory after."""
    prev = logging.getLogRecordFactory()
    setup_logging(force=True)
    yield
    logging.setLogRecordFactory(prev)


def _capture():
    """Attach a list-collecting handler to root; return (records, detach)."""
    records: list[logging.LogRecord] = []

    class _Collect(logging.Handler):
        def emit(self, record):
            records.append(record)

    h = _Collect(level=logging.DEBUG)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.DEBUG)
    return records, lambda: root.removeHandler(h)


class TestTraceContext:
    def test_default_is_dash(self):
        assert get_trace_id() == "-"

    def test_sets_and_resets(self):
        assert get_trace_id() == "-"
        with trace_context("grafana"):
            assert get_trace_id() == "grafana"
        assert get_trace_id() == "-"

    def test_nesting_restores_outer(self):
        with trace_context("outer"):
            with trace_context("inner"):
                assert get_trace_id() == "inner"
            assert get_trace_id() == "outer"
        assert get_trace_id() == "-"

    def test_reset_even_on_exception(self):
        with pytest.raises(ValueError):
            with trace_context("boom"):
                raise ValueError("x")
        assert get_trace_id() == "-"


class TestNewTraceId:
    def test_unprefixed(self):
        tid = new_trace_id()
        assert len(tid) == 8 and "-" not in tid

    def test_prefixed_and_unique(self):
        a, b = new_trace_id("req"), new_trace_id("req")
        assert a.startswith("req-") and b.startswith("req-")
        assert a != b


class TestRecordFactory:
    def test_record_carries_trace_id(self):
        records, detach = _capture()
        try:
            logging.getLogger("t").info("no ctx")
            with trace_context("paperless"):
                logging.getLogger("t").info("with ctx")
        finally:
            detach()
        by_msg = {r.getMessage(): r.trace_id for r in records}
        assert by_msg["no ctx"] == "-"
        assert by_msg["with ctx"] == "paperless"

    def test_format_includes_trace_id(self):
        records, detach = _capture()
        try:
            with trace_context("kopia"):
                logging.getLogger("t").warning("hi")
        finally:
            detach()
        rendered = logging.Formatter(LOG_FORMAT).format(records[-1])
        assert "[kopia]" in rendered and "hi" in rendered


class TestSetupIdempotent:
    def test_no_duplicate_handlers(self):
        root = logging.getLogger()
        setup_logging(force=True)
        before = sum(1 for h in root.handlers if getattr(h, "_homelab_trace", False))
        setup_logging()  # no force → no-op
        setup_logging(force=True)  # force → replace, not add
        after = sum(1 for h in root.handlers if getattr(h, "_homelab_trace", False))
        assert before == 1 and after == 1


class TestConcurrentTraceIsolation:
    """The headline guarantee: each parallel worker's records carry its own id."""

    def test_threadpool_workers_do_not_cross_bleed(self):
        records, detach = _capture()
        n = 20

        def work(i):
            # Mirrors health.py _check: bind the id, then log inside the block.
            with trace_context(f"svc-{i}"):
                logging.getLogger("sweep").info("checked %s", i)
                return i, get_trace_id()

        try:
            with ThreadPoolExecutor(max_workers=8) as ex:
                results = dict(ex.map(work, range(n)))
        finally:
            detach()

        # Each worker saw its own id...
        assert all(results[i] == f"svc-{i}" for i in range(n))
        # ...and each emitted record is tagged with the matching worker id.
        emitted = {
            int(r.getMessage().split()[-1]): r.trace_id
            for r in records
            if r.name == "sweep"
        }
        assert len(emitted) == n
        assert all(emitted[i] == f"svc-{i}" for i in range(n))
        # Main thread's context is untouched after the sweep.
        assert get_trace_id() == "-"
