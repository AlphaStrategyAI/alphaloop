"""Test-only pauses. Every hook defaults off."""

from __future__ import annotations

import os
import time

HOLD_RUNNING_ENV = "ALPHALOOP_E2E_HOLD_RUNNING_SEC"
_MAX_HOLD_SEC = 120.0


def e2e_hold_running_seconds() -> float:
    """Seconds to stay in ``running`` before a round starts. Unset or invalid is zero."""
    raw = os.environ.get(HOLD_RUNNING_ENV, "").strip()
    if not raw:
        return 0.0
    try:
        value = float(raw)
    except ValueError:
        return 0.0
    if value <= 0:
        return 0.0
    return min(value, _MAX_HOLD_SEC)


def hold_running_for_e2e() -> None:
    """Block the research loop so a GUI test can observe a running research.

    The HTTP API stays on another thread, so delete and view polls still work.
    A missing or zero ``ALPHALOOP_E2E_HOLD_RUNNING_SEC`` returns immediately.
    """
    seconds = e2e_hold_running_seconds()
    if seconds <= 0:
        return
    time.sleep(seconds)
