"""Product copy for cumulative trial counters (single source)."""

from __future__ import annotations


def version_trial_label(used: int, budget: int) -> str:
    return f"本版本 {used}/{budget} 轮"


def research_on_window_label(rounds: int) -> str:
    return f"本研究在本窗口累计 {rounds} 轮"


def all_researches_on_window_label(rounds: int) -> str:
    return f"本窗口所有研究累计 {rounds} 轮"
