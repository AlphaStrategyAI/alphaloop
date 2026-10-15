from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime

from engine.research.models import Research, ResearchEvent, ResearchStatus
from engine.research.state_machine import transition


def max_consecutive_run_errors() -> int:
    raw = os.getenv("ALPHALOOP_MAX_CONSECUTIVE_RUN_ERRORS", "3")
    return max(1, int(raw))


def apply_run_failure(research: Research, message: str, now: datetime) -> Research:
    """Count identical run failures; pause after threshold."""
    if research.status is not ResearchStatus.RUNNING:
        return research
    same = research.last_run_error == message
    count = (research.consecutive_identical_run_errors + 1) if same else 1
    updated = replace(
        research,
        last_run_error=message,
        consecutive_identical_run_errors=count,
        updated_at=now,
    )
    if count >= max_consecutive_run_errors():
        return transition(updated, ResearchEvent.PAUSE, now)
    return updated


def clear_run_errors(research: Research) -> Research:
    if research.last_run_error is None and research.consecutive_identical_run_errors == 0:
        return research
    return replace(
        research,
        last_run_error=None,
        consecutive_identical_run_errors=0,
    )
