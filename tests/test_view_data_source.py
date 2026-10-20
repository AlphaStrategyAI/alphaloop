"""Confirm and other views name the data source from symbols, without a market probe."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from engine.main import ResearchCommandService
from engine.research.models import AssetClass, Market, Slot, Universe, new_research
from engine.research.planned_data_window import (
    AKSHARE_SINA_DATA_SOURCE_ID,
    data_source_id_for_symbols,
)
from engine.research.pool_data_shrink import set_pool_data_loader
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.universe_validation import ensure_runnable_universe
from tests.test_state_machine import NOW, locked_brief

YAHOO = "雅虎日线"
AKSHARE = "AkShare 日线（新浪优先）"


class _ProbeLoader:
    def __init__(self) -> None:
        self.calls = 0

    def load_daily(
        self,
        symbols: tuple[str, ...],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        self.calls += 1
        raise AssertionError("view_for must not probe market data")


def _confirm_draft(
    research_id: str,
    market: Market,
    symbols: tuple[str, ...],
):
    brief = replace(
        locked_brief(),
        universe=Slot(
            Universe(
                market=market,
                asset_class=AssetClass.EQUITY,
                underlying_asset_class=AssetClass.EQUITY,
                symbols=symbols,
            ),
            True,
        ),
    )
    return replace(new_research(research_id, NOW), brief=brief)


def test_view_source_follows_symbols_and_does_not_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _forbidden_probe(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("view_for must not call ensure_runnable_universe")

    monkeypatch.setattr("engine.main.ensure_runnable_universe", _forbidden_probe)
    loader = _ProbeLoader()
    set_pool_data_loader(loader)
    store = SQLiteStore(tmp_path / "sources.db")
    drafts = {
        "r-cn": _confirm_draft(
            "r-cn",
            Market.CN,
            ("600519.SH", "000858.SZ", "830799.BJ"),
        ),
        "r-us": _confirm_draft("r-us", Market.US, ("AAPL", "MSFT")),
        "r-mix": _confirm_draft("r-mix", Market.US, ("AAPL", "600519.SH")),
    }
    for research in drafts.values():
        store.create(research)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))

    try:
        cn = service.view_for("#/research/r-cn")
        us = service.view_for("#/research/r-us")
        mixed = service.view_for("#/research/r-mix")
    finally:
        set_pool_data_loader(None)

    assert loader.calls == 0
    assert cn["kind"] == "confirm_run"
    assert us["kind"] == "confirm_run"
    assert mixed["kind"] == "confirm_run"
    assert cn["symbolSelection"]["dataSource"] == AKSHARE
    assert us["symbolSelection"]["dataSource"] == YAHOO
    assert mixed["symbolSelection"]["dataSource"] == YAHOO
    assert store.load("r-cn").data_source_id == AKSHARE_SINA_DATA_SOURCE_ID
    assert store.load("r-us").data_source_id == "yahoo_daily"
    assert cn.get("confirmDataNotice") is None


def test_confirm_pin_uses_the_same_symbol_mapping() -> None:
    symbols = ("600519.SH", "000858.SZ")
    research = _confirm_draft("r-pin", Market.US, symbols)
    updated = ensure_runnable_universe(research)
    assert data_source_id_for_symbols(symbols, Market.US) == AKSHARE_SINA_DATA_SOURCE_ID
    assert updated.data_source_id == AKSHARE_SINA_DATA_SOURCE_ID
    assert data_source_id_for_symbols(("AAPL", "MSFT"), Market.US) == "yahoo_daily"
