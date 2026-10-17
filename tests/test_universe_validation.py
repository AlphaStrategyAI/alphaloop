from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engine.research.default_universe import US_EQUITY_DEFAULT
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    Research,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.universe_validation import ensure_runnable_universe
from engine.research.user_errors import UserFacingError

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _locked_us_equity_no_symbols() -> Research:
    research = new_research("r-1", NOW)
    brief = ResearchBrief(
        thesis=Slot("低波动回归", True),
        universe=Slot(
            Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ()),
            True,
        ),
        max_effective_hours=Slot(8.0, True),
        round1_methods=Slot((), True),
        coverage_floor=Slot(CoverageFloor(8, 10, 5.0), True),
    )
    return replace(research, brief=brief)


def test_default_universe_applied_when_symbols_empty() -> None:
    updated = ensure_runnable_universe(_locked_us_equity_no_symbols())
    symbols = updated.brief.universe.value.symbols
    assert symbols == US_EQUITY_DEFAULT
    assert len(symbols) >= 8


def test_empty_symbols_without_default_pool_rejected() -> None:
    research = _locked_us_equity_no_symbols()
    brief = replace(
        research.brief,
        universe=Slot(
            Universe(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY, ()),
            True,
        ),
    )
    research = replace(research, brief=brief)
    with pytest.raises(UserFacingError) as exc:
        ensure_runnable_universe(research)
    assert exc.value.code == "UNIVERSE_SYMBOLS_EMPTY"
