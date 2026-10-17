from datetime import UTC, date, datetime

import pandas as pd
import pytest

from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.pool_data_shrink import (
    set_pool_data_loader,
    shrink_pool_to_available_data,
    symbols_with_daily_data,
)
from engine.research.universe_validation import ensure_runnable_universe
from engine.research.user_errors import UserFacingError

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
START = date(2016, 1, 1)
END = date(2026, 10, 17)


class _FakeLoader:
    def __init__(self, missing: frozenset[str]) -> None:
        self.missing = missing

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        columns: dict[str, pd.Series] = {}
        for symbol in symbols:
            if symbol in self.missing:
                continue
            columns[symbol] = pd.Series(
                [100.0, 101.0],
                index=pd.to_datetime([start, end]),
                name=symbol,
            )
        return pd.DataFrame(columns)


def _us_equity_brief(symbols: tuple[str, ...]) -> ResearchBrief:
    return ResearchBrief(
        thesis=Slot("测试", True),
        universe=Slot(
            Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, symbols, user_symbols_override=True),
            True,
        ),
        max_effective_hours=Slot(8.0, True),
        round1_methods=Slot((), True),
        coverage_floor=Slot(CoverageFloor(3, 10, 5.0), True),
    )


def test_shrink_only_drops_missing_within_pool() -> None:
    symbols = ("A", "B", "C", "D", "E")
    set_pool_data_loader(_FakeLoader(frozenset({"B", "D"})))
    kept = symbols_with_daily_data(symbols, START, END)
    assert kept == ("A", "C", "E")
    result = shrink_pool_to_available_data(symbols, START, END, min_assets=3)
    assert result.dropped == ("B", "D")
    assert result.remaining_count == 3


def test_shrink_below_min_assets_stops_with_chinese_message() -> None:
    symbols = ("A", "B", "C", "D", "E")
    set_pool_data_loader(_FakeLoader(frozenset({"B", "C", "D", "E"})))
    with pytest.raises(UserFacingError) as exc:
        shrink_pool_to_available_data(symbols, START, END, min_assets=3)
    assert exc.value.code == "POOL_DATA_SHRINK_TOO_FEW"
    assert "剔除 4 只" in exc.value.message
    assert "剩余 1 只" in exc.value.message
    assert "至少 3 只" in exc.value.message


def test_shrink_above_min_assets_continues_at_confirm() -> None:
    from dataclasses import replace

    symbols = tuple(f"S{i}" for i in range(10))
    set_pool_data_loader(_FakeLoader(frozenset({"S0", "S1"})))
    research = replace(new_research("r-shrink", NOW), brief=_us_equity_brief(symbols))
    updated = ensure_runnable_universe(research)
    assert updated.pool_data_dropped_count == 2
    assert len(updated.brief.universe.value.symbols) == 8
