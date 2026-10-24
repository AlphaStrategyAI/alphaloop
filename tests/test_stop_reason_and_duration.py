"""A short run must not look like a normal 0.00-hour result.

The 12-hour budget and the 5-round implementation cap are separate.
This run hits the round cap while the time budget is still unused.
The cap and the time-budget check stay as they are; the defect is that
the UI cannot tell those apart, and a few seconds render as 0.00 hours.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from engine.research.clock import TimeBudget
from engine.research.honest_stop import run_stop_reason
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus, Slot
from engine.research.store import SQLiteStore
from engine.research.time_display import format_effective_display, format_remaining_display
from tests.test_loop_runtime import (
    NOW,
    FailedMethodsParamBuilder,
    FakeMonotonic,
    PassReviewer,
    running_research,
)


def _twelve_hour(research):
    return replace(
        research,
        brief=replace(research.brief, max_effective_hours=Slot(12.0, True)),
    )


def test_sub_hour_effective_time_is_not_shown_as_zero_hours() -> None:
    research = replace(running_research(), effective_seconds=7.0)
    label = format_effective_display(research)
    assert label != "0.00 小时"
    assert "0.00" not in label
    assert "7" in label
    assert "秒" in label


def test_zero_seconds_is_not_labeled_as_a_normal_hour_result() -> None:
    research = replace(running_research(), effective_seconds=0.0)
    label = format_effective_display(research)
    assert label != "0.00 小时"
    assert "小时" not in label


def test_round_cap_stops_before_the_time_budget_and_names_that_reason(tmp_path: Path) -> None:
    """Five failed rounds advance the clock by 7 seconds against a 12-hour budget.

    The round cap is what stops the run. The time budget is not exhausted,
    and the seconds are stored rather than dropped.
    """
    mono = FakeMonotonic()
    store = SQLiteStore(tmp_path / "stop.db")
    research = _twelve_hour(running_research())
    store.create(research)

    class _Ticking(FailedMethodsParamBuilder):
        def build(self, research, attempt_number: int):
            mono.value += 1.4
            return super().build(research, attempt_number)

    loop = ResearchLoop(store, _Ticking(), PassReviewer(), TimeBudget(mono), lambda: NOW)
    result = research
    for _ in range(5):
        result = loop.run_once("r-loop")
        if result.status is not ResearchStatus.RUNNING:
            break

    assert result.status is ResearchStatus.COMPLETED
    assert len(result.versions[0].rounds) == 5
    assert result.effective_seconds == pytest.approx(7.0)
    assert result.brief.max_effective_hours.value == 12.0
    assert result.effective_seconds < 12.0 * 3600
    assert run_stop_reason(result) == "round_cap"
    shown = format_effective_display(result)
    assert shown != "0.00 小时"
    assert "7" in shown
    remaining = format_remaining_display(result)
    assert remaining != "0.00 小时"
    assert "12" in remaining or "11" in remaining
