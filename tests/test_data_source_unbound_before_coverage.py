"""F1: a missing price source is N3 even when the named list is also too small."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.a1_copy import DATA_SOURCE_UNBOUND
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.run_gate import evaluate_run_gate
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.test_state_machine import NOW, locked_brief


def _one_name_above_floor() -> ResearchBrief:
    universe = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        ("AAPL",),
        user_symbols_override=True,
    )
    floor = CoverageFloor(min_assets=25, min_years=10, max_missing_pct=5)
    return replace(
        locked_brief(),
        thesis=Slot("Mean reversion on AAPL, a US stock, using daily prices.", True),
        universe=Slot(universe, True),
        coverage_floor=Slot(floor, True),
    )


def test_missing_source_is_reported_before_the_coverage_floor(tmp_path: Path) -> None:
    research = replace(new_research("r-f1", NOW), brief=_one_name_above_floor())
    settings = tmp_path / "settings.json"
    missing = evaluate_run_gate(
        research,
        data_source_id="",
        unlicensed_acknowledged=False,
        settings_path=settings,
    )
    assert missing.runnable is False
    assert missing.code == "DATA_SOURCE_UNBOUND"
    assert missing.message == DATA_SOURCE_UNBOUND
    covered = evaluate_run_gate(
        research,
        data_source_id="yahoo_daily",
        unlicensed_acknowledged=True,
        settings_path=settings,
    )
    assert covered.code == "UNIVERSE_TOO_FEW_SYMBOLS"


def test_confirm_run_raises_the_same_unbound_code(tmp_path: Path) -> None:
    service = ResearchCommandService(
        SQLiteStore(tmp_path / "gate.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )
    service.store.create(replace(new_research("r-f1", NOW), brief=_one_name_above_floor()))
    with pytest.raises(UserFacingError) as exc:
        service.handle({"type": "confirm_run", "research_id": "r-f1"})
    assert exc.value.code == "DATA_SOURCE_UNBOUND"
    assert exc.value.message == DATA_SOURCE_UNBOUND
    assert service.store.load("r-f1").status.value == "draft"
