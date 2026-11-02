"""Test-only pauses and crash barriers. Every hook defaults off."""

from __future__ import annotations

import os
import sqlite3
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


def crash_barrier(name: str) -> None:
    """Block after a durable step so a parent test can kill this process.

    Unset ``ALPHALOOP_CRASH_BARRIER`` returns immediately. The ready line is
    flushed before the wait. ``process.kill`` is SIGKILL here and
    TerminateProcess on Windows.
    """
    wanted = os.environ.get("ALPHALOOP_CRASH_BARRIER", "").strip()
    if not wanted or wanted != name:
        return
    print(f"ALPHALOOP_BARRIER_READY {name}", flush=True)
    while True:
        time.sleep(0.2)


def export_recheck_failures() -> tuple[str, ...] | None:
    """Fail the post-staging eligibility recheck. Unset means use the real result."""
    raw = os.environ.get("ALPHALOOP_EXPORT_RECHECK_FAIL", "").strip()
    if not raw:
        return None
    return tuple(item for item in raw.split(",") if item)


def export_crash_after_authorize() -> bool:
    """Raise after the authorization row commits and before the visible rename."""
    return os.environ.get("ALPHALOOP_EXPORT_CRASH_AFTER_AUTHORIZE", "").strip() == "1"


def maybe_raise_busy() -> None:
    """One-shot or sticky ``database is locked`` for the round commit retry."""
    mode = os.environ.get("ALPHALOOP_INJECT_DB_BUSY", "").strip()
    if mode == "once":
        os.environ["ALPHALOOP_INJECT_DB_BUSY"] = ""
    elif mode != "always":
        return
    raise sqlite3.OperationalError("database is locked")
