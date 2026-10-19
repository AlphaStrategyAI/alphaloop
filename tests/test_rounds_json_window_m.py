"""P0-7b: rounds.json cumulative M matches the research-window UI count.

Confirm-day window end and the last backtest bar can differ. Both the export
and 「本研究在本窗口累计」must count rounds on the research key. A new confirm
on the next calendar day still opens a new key (D7(a) does not remove that).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

from engine.export import _round_history_with_trials
from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.data_window import (
    cumulative_rounds_on_window,
    data_window_key_from_research,
    window_cumulative_all_researches,
)
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchStatus, new_research
from engine.research.planned_data_window import planned_data_window
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import NOW, FakeBuilder, PassReviewer, running_research

CONFIRM_DAY = date(2026, 10, 17)
LAST_BAR = date(2016, 12, 30)


def _pinned_running():
    return replace(
        running_research(),
        data_window_start=date(2014, 10, 17),
        data_window_end=CONFIRM_DAY,
        symbol_list_version="us_equity_large_cap_v1",
        data_source_id="yahoo_daily",
    )


def test_research_cumulative_matches_export_when_bar_end_differs_from_confirm_day(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "m.db")
    store.create(_pinned_running())
    done = ResearchLoop(
        store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    assert done.status is ResearchStatus.COMPLETED
    sim_end = done.versions[0].rounds[0].accepted_attempt.simulation.end
    assert sim_end == LAST_BAR
    assert done.data_window_end == CONFIRM_DAY
    assert sim_end != done.data_window_end

    assert cumulative_rounds_on_window(done) == 1
    rounds = [round_ for version in done.versions for round_ in version.rounds]
    history = _round_history_with_trials(done, rounds)
    assert history["cumulative_rounds_on_window"] == 1
    assert history["rounds"][0]["cumulative_round_on_window"] == 1

    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    view = service.view_for("#/research/r-loop")
    assert view["researchRoundsOnWindow"] == history["cumulative_rounds_on_window"]
    assert view["researchCumulativeLabel"] == "本研究在本窗口累计 1 轮"
    assert view["windowCumulativeRoundsAllResearches"] == 1
    assert "本研究在本窗口累计 0 轮" not in view["researchCumulativeLabel"]


def test_cross_day_new_confirm_does_not_inherit_yesterdays_m(tmp_path: Path) -> None:
    """Residual risk: the next calendar day's confirm is a new window key.

    An already pinned research keeps the M it earned. A research confirmed
    after "today" moves does not share that key, so its own cumulative starts
    at zero. This test records that behavior; it does not change the end date
    to a data cutoff.
    """
    day1 = datetime(2026, 10, 17, 8, tzinfo=UTC)
    day2 = datetime(2026, 10, 18, 8, tzinfo=UTC)
    start1, end1 = planned_data_window(day1)
    start2, end2 = planned_data_window(day2)
    assert end1 == date(2026, 10, 17)
    assert end2 == date(2026, 10, 18)
    assert (start1, end1) != (start2, end2)

    store = SQLiteStore(tmp_path / "cross-day.db")
    yesterday = replace(
        _pinned_running(),
        data_window_start=start1,
        data_window_end=end1,
    )
    store.create(yesterday)
    done = ResearchLoop(
        store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(lambda: 10.0),
        lambda: NOW,
    ).run_once("r-loop")
    yesterday_key = data_window_key_from_research(done)
    assert yesterday_key is not None
    assert yesterday_key.end == end1
    assert cumulative_rounds_on_window(done) == 1
    assert window_cumulative_all_researches(store, yesterday_key) == 1

    today = replace(
        new_research("r-next", day2),
        status=ResearchStatus.RUNNING,
        data_window_start=start2,
        data_window_end=end2,
        symbol_list_version="us_equity_large_cap_v1",
        data_source_id="yahoo_daily",
    )
    today_key = data_window_key_from_research(today)
    assert today_key is not None
    assert today_key != yesterday_key
    assert cumulative_rounds_on_window(today) == 0
    assert window_cumulative_all_researches(store, today_key) == 0
    assert window_cumulative_all_researches(store, yesterday_key) == 1
