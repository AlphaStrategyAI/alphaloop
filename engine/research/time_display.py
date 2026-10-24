"""User-facing effective-time labels for the workbench header.

Sub-hour durations are minutes and seconds. ``0.00 小时`` is never used for a
duration under one hour, including zero: that string reads as a normal hour
result when the run only lasted a few seconds.
"""

from __future__ import annotations

from engine.research.models import Research


def format_seconds(seconds: float) -> str:
    whole = int(round(max(0.0, seconds)))
    if whole < 3600:
        minutes, secs = divmod(whole, 60)
        if minutes == 0:
            return f"{secs} 秒"
        return f"{minutes} 分 {secs} 秒"
    return f"{seconds / 3600:.2f} 小时"


def format_effective_display(research: Research) -> str:
    return format_seconds(research.effective_seconds)


def remaining_seconds(research: Research) -> float | None:
    max_hours = research.brief.max_effective_hours.value
    if max_hours is None:
        return None
    return max(0.0, max_hours * 3600 - max(0.0, research.effective_seconds))


def format_remaining_display(research: Research) -> str:
    remaining = remaining_seconds(research)
    if remaining is None:
        return ""
    return format_seconds(remaining)
