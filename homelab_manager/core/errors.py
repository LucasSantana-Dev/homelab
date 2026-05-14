"""Shared error helpers — exception scrubbing for safe-to-echo messages.

Background: audit-deep M1 hardening showed that subprocess stderr can leak
env values, auth tokens, or socket paths. `scrub_subprocess_error` produces a
caller-safe one-liner (type-only + context) while full detail is logged at
DEBUG by the caller via `logger.debug(..., exc_info=True)`.
"""

from __future__ import annotations


def scrub_subprocess_error(exc: BaseException, *, context: str = "") -> str:
    """Return a safe-to-echo description of a subprocess failure.

    Never includes `str(exc)` (might carry stderr). Includes the exception
    type and an optional caller-supplied context string.
    """
    type_name = type(exc).__name__
    if context:
        return f"{context} ({type_name})"
    return f"Subprocess failed ({type_name})"
