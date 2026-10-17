"""Canonical window M for all workbench surfaces."""

from datetime import date
from pathlib import Path

from dataclasses import replace

from engine.main import ResearchCommandService
from engine.research.data_window import anchor_data_window_key, trial_tracking_for_view
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import running_research


def test_disclosure_m_uses_store_window_count(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "disclosure.db")
    research = replace(
        running_research(),
        data_window_start=date(2020, 1, 1),
        data_window_end=date(2024, 1, 1),
        symbol_list_version="us_equity_large_cap_v1",
    )
    store.create(research)
    anchor = anchor_data_window_key(research)
    assert anchor is not None
    store.increment_window_round_count(anchor.serialize())
    store.increment_window_round_count(anchor.serialize())
    store.increment_window_round_count(anchor.serialize())
    tracking = trial_tracking_for_view(store.load("r-loop"), store)
    assert tracking["researchRoundsOnWindow"] == 0
    assert tracking["cumulativeRoundsOnWindow"] == 3
    assert tracking["windowCumulativeLabel"] == "本数据窗口累计 3 轮"
    assert tracking["workbenchHeaderSummary"] == "本数据窗口累计 3 轮"

    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    view = service.view_for("#/research/r-loop")
    assert view["cumulativeRoundsOnWindow"] == 3
    assert view["workbenchHeaderSummary"] == "本数据窗口累计 3 轮"
