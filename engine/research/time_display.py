"""User-facing effective-time labels for the workbench header."""

from __future__ import annotations

from engine.research.models import Research


def format_effective_display(research: Research) -> str:
    if research.effective_seconds <= 0:
        return "0.00 小时"
    return f"{research.effective_seconds / 3600:.2f} 小时"


def format_remaining_display(research: Research) -> str:
    max_hours = research.brief.max_effective_hours.value
    if max_hours is None:
        return ""
    if research.effective_seconds <= 0:
        return f"{max_hours:.2f} 小时"
    used = research.effective_seconds / 3600
    remaining = max(0.0, max_hours - used)
    return f"{remaining:.2f} 小时"
