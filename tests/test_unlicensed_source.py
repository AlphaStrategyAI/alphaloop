"""Yahoo and AkShare are unlicensed sources. They are never the default."""

from __future__ import annotations

import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from engine.dialogue.intent import interpret
from engine.dialogue.prompts import SlotName
from engine.export import build_research_record_pack, build_strategy_pack
from engine.main import ResearchCommandService
from engine.research.models import Market, ResearchStatus, new_research
from engine.research.planned_data_window import data_source_id_for_symbols
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.universe_pool import pin_draft_data_source
from engine.research.user_errors import UserFacingError
from tests.test_export_pack import completed_research, reference_strategy, snapshot
from tests.test_state_machine import NOW, locked_brief
from tests.test_view_data_source import _confirm_draft


def test_new_research_does_not_default_to_yahoo() -> None:
    research = new_research("r-new", NOW)
    assert research.data_source_id != "yahoo_daily"
    assert research.data_source_id != "akshare_sina_daily"
    assert research.data_source_id == ""


def test_nl_parse_of_a_us_equity_brief_does_not_select_yahoo() -> None:
    research = new_research("r-nl", NOW)
    message = (
        "美股股票 SPY 的均值回归。有效研究时间 12 小时。"
        "分段稳健性检验、样本外稳定、集中度、换手成本。"
        "至少 1 个、1 年、缺失不超过 20%。"
    )
    intent = interpret(message, research, SlotName.THESIS)
    keys = {key for key, _value in intent.updates}
    assert "data_source_id" not in keys
    assert research.data_source_id == ""


def test_draft_pin_and_confirm_card_do_not_preselect_yahoo(tmp_path: Path) -> None:
    research = _confirm_draft("r-us", Market.US, ("SPY",))
    assert pin_draft_data_source(research).data_source_id != "yahoo_daily"
    # The mapping still names the source a user may choose. It is not applied.
    assert data_source_id_for_symbols(("SPY",), Market.US) == "yahoo_daily"

    store = SQLiteStore(tmp_path / "src.db")
    store.create(research)
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    view = service.view_for("#/research/r-us")
    selection = view["symbolSelection"]
    assert selection["dataSource"] != "雅虎日线"
    assert selection["dataSourceId"] in ("", None)
    assert selection["dataSourcePending"] is True
    assert selection["offeredDataSourceId"] == "yahoo_daily"
    assert store.load("r-us").data_source_id != "yahoo_daily"


def test_confirm_run_blocks_until_the_unlicensed_box_is_ticked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStore(tmp_path / "ack.db")
    research = _confirm_draft("r-us", Market.US, ("SPY",))
    store.create(research)
    paths = EnginePaths.for_colocated_root(tmp_path)
    service = ResearchCommandService(store, paths)

    with pytest.raises(UserFacingError) as missing:
        service.handle({"type": "confirm_run", "research_id": "r-us"})
    assert missing.value.code == "DATA_SOURCE_UNBOUND"
    assert store.load("r-us").status is ResearchStatus.DRAFT

    with pytest.raises(UserFacingError) as unacked:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": "r-us",
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": False,
            }
        )
    assert unacked.value.code == "UNLICENSED_SOURCE_UNACKNOWLEDGED"
    assert store.load("r-us").status is ResearchStatus.DRAFT
    assert store.load("r-us").data_source_id != "yahoo_daily"

    # The market probe is not what this test is about. Stop before a live fetch.
    monkeypatch.setattr("engine.main.ensure_runnable_universe", lambda item: item)
    service.handle(
        {
            "type": "confirm_run",
            "research_id": "r-us",
            "data_source_id": "yahoo_daily",
            "unlicensed_acknowledged": True,
        }
    )
    started = store.load("r-us")
    assert started.data_source_id == "yahoo_daily"
    assert started.status is ResearchStatus.RUNNING

    second = _confirm_draft("r-us-2", Market.US, ("AAPL",))
    store.create(second)
    service.handle(
        {
            "type": "confirm_run",
            "research_id": "r-us-2",
            "data_source_id": "yahoo_daily",
        }
    )
    assert store.load("r-us-2").data_source_id == "yahoo_daily"


def test_yahoo_strategy_pack_and_research_record_carry_only_a_fingerprint(tmp_path: Path) -> None:
    prices = snapshot()
    distinctive = 12345.67
    prices = replace_prices(prices, distinctive)
    research = replace(completed_research(), data_source_id="yahoo_daily")
    snapshot_path = tmp_path / "prices.csv"
    frame = prices.prices.copy()
    frame["__benchmark__"] = prices.benchmark_prices
    frame.to_csv(snapshot_path, index_label="date")
    attempt = research.versions[-1].rounds[-1].accepted_attempt
    attempt = replace(attempt, data_snapshot_path=snapshot_path)
    round_ = replace(research.versions[-1].rounds[-1], accepted_attempt=attempt)
    version = replace(research.versions[-1], rounds=(round_,))
    research = replace(research, versions=(version,))

    strategy_zip = tmp_path / "strategy.zip"
    build_strategy_pack(research, reference_strategy(), prices, strategy_zip)
    _assert_fingerprint_only(strategy_zip, distinctive)

    record_zip = tmp_path / "record.zip"
    build_research_record_pack(research, record_zip)
    _assert_fingerprint_only(record_zip, distinctive)


def replace_prices(panel, price: float):
    from dataclasses import replace as dc_replace

    from engine.strategy import MarketPanel

    prices = pd.DataFrame(
        {column: [price] * len(panel.prices) for column in panel.prices.columns},
        index=panel.prices.index,
    )
    benchmark = pd.Series([price] * len(panel.prices), index=panel.prices.index, name="SPX")
    return MarketPanel(prices, panel.observed_at, benchmark)


def _assert_fingerprint_only(archive_path: Path, distinctive: float) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        blob = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in names
            if name.endswith((".csv", ".json", ".py", ".txt", ".md"))
        )
    assert "data/prices.csv" not in names
    assert "data/benchmark.csv" not in names
    assert "data/fingerprint.json" in names
    fingerprint = json.loads(
        zipfile.ZipFile(archive_path).read("data/fingerprint.json")
    )
    assert fingerprint["redistribution"] == "fingerprint_only"
    assert fingerprint["source_id"] == "yahoo_daily"
    assert isinstance(fingerprint["prices_sha256"], str)
    assert len(fingerprint["prices_sha256"]) == 64
    assert str(distinctive) not in blob
    assert "12345.67" not in blob
