from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.main import ResearchCommandService
from engine.research.data_availability import TRANSIENT_DATA_CODE, TRANSIENT_DATA_MESSAGE
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    ResearchBrief,
    ResearchStatus,
    Slot,
    Universe,
    new_research,
)
from engine.research.pool_data_shrink import set_pool_data_loader, shrink_pool_to_available_data
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.symbol_pool import pool_for_market
from engine.research.universe_validation import ensure_runnable_universe
from engine.research.user_errors import UserFacingError
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
START = date(2016, 1, 1)
END = date(2026, 10, 17)


class _EmptyFrameLoader:
    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame()


class _FlakyLoader:
    def __init__(self) -> None:
        self.calls = 0

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        self.calls += 1
        if self.calls == 1:
            return pd.DataFrame()
        index = pd.to_datetime([start, end])
        return pd.DataFrame(
            {symbol: pd.Series([1.0, 2.0], index=index) for symbol in symbols}
        )


def _confirm_ready_research() -> object:
    pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    brief = locked_brief()
    universe = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        pool.symbols,
        symbol_list_version=pool.version_id,
        user_symbols_override=False,
    )
    brief = replace(brief, universe=Slot(universe, True))
    return replace(new_research("r-transient", NOW), brief=brief)


def test_empty_provider_frame_is_transient_not_shrink() -> None:
    set_pool_data_loader(_EmptyFrameLoader())
    pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    with pytest.raises(UserFacingError) as exc:
        shrink_pool_to_available_data(pool.symbols[:10], START, END, min_assets=5)
    assert exc.value.code == TRANSIENT_DATA_CODE
    assert exc.value.message == TRANSIENT_DATA_MESSAGE


def test_confirm_run_transient_keeps_pool_and_slots(tmp_path: Path) -> None:
    set_pool_data_loader(_EmptyFrameLoader())
    store = SQLiteStore(tmp_path / "t.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    research = _confirm_ready_research()
    store.create(research)
    before_symbols = research.brief.universe.value.symbols
    with pytest.raises(UserFacingError) as exc:
        service.handle({"type": "confirm_run", "research_id": research.research_id})
    assert exc.value.code == TRANSIENT_DATA_CODE
    loaded = store.load(research.research_id)
    assert loaded.status is ResearchStatus.DRAFT
    assert loaded.brief.universe.value.symbols == before_symbols
    assert loaded.brief.universe.locked is True
    assert loaded.symbol_list_version is None
    assert loaded.versions == ()
    assert any(TRANSIENT_DATA_MESSAGE in turn.text for turn in loaded.dialogue)
    view = service.view_for(f"#/research/{research.research_id}")
    notice = next(turn for turn in view["dialogue"] if turn.get("errorCode") == TRANSIENT_DATA_CODE)
    assert notice["text"] == ""
    assert TRANSIENT_DATA_MESSAGE not in notice["text"]
    assert "empty price frame" in notice["errorDetail"]
    assert TRANSIENT_DATA_MESSAGE not in notice["errorDetail"]
    assert notice["errorParams"]["symbols"] > 0


def test_confirm_run_retries_after_source_recovers(tmp_path: Path) -> None:
    flaky = _FlakyLoader()
    set_pool_data_loader(flaky)
    store = SQLiteStore(tmp_path / "retry.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    research = _confirm_ready_research()
    store.create(research)
    with pytest.raises(UserFacingError):
        service.handle({"type": "confirm_run", "research_id": research.research_id})
    service.handle({"type": "confirm_run", "research_id": research.research_id})
    loaded = store.load(research.research_id)
    assert loaded.status is ResearchStatus.RUNNING
    assert loaded.symbol_list_version == "us_equity_large_cap_v1"
    assert len(loaded.brief.universe.value.symbols) >= 25


def test_genuine_missing_symbols_still_shrink_and_too_few(tmp_path: Path) -> None:
    symbols = tuple(f"S{i}" for i in range(10))

    class _PartialLoader:
        def load_daily(self, syms: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
            index = pd.to_datetime([start, end])
            return pd.DataFrame(
                {
                    syms[0]: pd.Series([1.0, 2.0], index=index),
                }
            )

    set_pool_data_loader(_PartialLoader())
    brief = ResearchBrief(
        thesis=Slot("测试", True),
        universe=Slot(
            Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, symbols, user_symbols_override=True),
            True,
        ),
        max_effective_hours=Slot(8.0, True),
        round1_methods=Slot((), True),
        coverage_floor=Slot(CoverageFloor(3, 10, 5.0), True),
    )
    research = replace(new_research("r-genuine", NOW), brief=brief)
    with pytest.raises(UserFacingError) as exc:
        ensure_runnable_universe(research)
    assert exc.value.code == "POOL_DATA_SHRINK_TOO_FEW"
    assert "剔除 9 只" in exc.value.message
