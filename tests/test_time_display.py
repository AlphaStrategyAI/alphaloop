from dataclasses import replace

from engine.research.models import Slot
from engine.research.time_display import format_remaining_display
from tests.test_loop_runtime import running_research


def test_remaining_shows_full_budget_before_effective_time_starts() -> None:
    research = replace(
        running_research(),
        effective_seconds=0.0,
        brief=replace(
            running_research().brief,
            max_effective_hours=Slot(3.0, True),
        ),
    )
    assert format_remaining_display(research) == "3 小时"


def test_remaining_subtracts_elapsed_effective_time() -> None:
    research = replace(
        running_research(),
        effective_seconds=72.0,
        brief=replace(
            running_research().brief,
            max_effective_hours=Slot(3.0, True),
        ),
    )
    assert format_remaining_display(research) == "2.98 小时"
