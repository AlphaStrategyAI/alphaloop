"""A named symbol never silently becomes the default pool."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from engine.dialogue.intent import interpret
from engine.dialogue.prompts import SlotName
from engine.main import ResearchCommandService
from engine.research.models import AssetClass, Market, new_research
from engine.research.pool_data_shrink import set_pool_data_loader
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.symbol_pool import pool_for_market
from engine.research.user_errors import UserFacingError

NOW_HOURS = "12 小时"
METHODS = "走样检验 样本外稳定 拥挤度 换手成本"
FLOOR_ONE = "至少 1 个 10 年 缺失不超过 5%"
FLOOR_MANY = "至少 25 个 10 年 缺失不超过 5%"


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "named.db")
    return ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))


def _fill(service: ResearchCommandService, research_id: str, thesis: str, floor: str) -> dict:
    for message in (thesis, NOW_HOURS, METHODS, floor):
        service.handle(
            {"type": "send_dialogue", "research_id": research_id, "message": message}
        )
    return service.view_for(f"#/research/{research_id}")


def _draft(service: ResearchCommandService) -> str:
    return service.handle({"type": "create_draft"})["research_id"]


class _NoBars:
    def __init__(self, missing: frozenset[str]) -> None:
        self.missing = missing

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        index = pd.to_datetime([start, end])
        columns = {}
        for symbol in symbols:
            if symbol in self.missing:
                columns[symbol] = pd.Series([float("nan"), float("nan")], index=index, name=symbol)
            else:
                columns[symbol] = pd.Series([100.0, 101.0], index=index, name=symbol)
        return pd.DataFrame(columns)


def test_interpret_keeps_an_inferred_code_off_the_default_pool() -> None:
    research = new_research("r-draft", datetime(2026, 8, 28, 12, tzinfo=UTC))
    intent = interpret("A股股票 600519 均值回归", research, SlotName.THESIS)
    universe = next(value for key, value in intent.updates if key == "universe")
    assert universe.symbols == ("600519.SH",)
    assert universe.user_symbols_override is True
    assert universe.unresolved_tokens == ()
    assert universe.inferred_symbols == (("600519", "600519.SH"),)


def test_interpret_blocks_an_uncertain_code_instead_of_dropping_it() -> None:
    research = new_research("r-draft", datetime(2026, 8, 28, 12, tzinfo=UTC))
    intent = interpret("A股股票 900901 均值回归", research, SlotName.THESIS)
    universe = next(value for key, value in intent.updates if key == "universe")
    assert universe.symbols == ()
    assert universe.user_symbols_override is True
    assert universe.unresolved_tokens == ("900901",)


def test_interpret_ignores_ordinary_words_around_a_real_market() -> None:
    research = new_research("r-draft", datetime(2026, 8, 28, 12, tzinfo=UTC))
    intent = interpret(
        "A股股票的均值回归 mean reversion daily ETF",
        research,
        SlotName.THESIS,
    )
    universe = next(value for key, value in intent.updates if key == "universe")
    assert universe.symbols == ()
    assert universe.unresolved_tokens == ()
    assert universe.user_symbols_override is False


def test_bare_code_confirm_card_shows_the_inference_and_not_the_pool(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    view = _fill(service, research_id, "A股股票 600519 均值回归", FLOOR_ONE)
    assert view["kind"] == "confirm_run"
    selection = view["symbolSelection"]
    assert selection["symbols"] == ["600519.SH"]
    assert selection["count"] == 1
    resolution = view["symbolResolution"]
    assert resolution["blocked"] is False
    assert resolution["inferred"] == [{"raw": "600519", "symbol": "600519.SH"}]
    assert resolution["editable"] is True
    pool = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    assert selection["count"] != len(pool.symbols)

    service.handle({"type": "confirm_run", "research_id": research_id})
    loaded = service.store.load(research_id)
    assert loaded.brief.universe.value.symbols == ("600519.SH",)


@pytest.mark.parametrize(
    ("thesis", "symbol"),
    [
        ("A股股票 000001 均值回归", "000001.SZ"),
        ("A股基金 510300 的均值回归", "510300.SH"),
        ("A股股票 600519.SH 均值回归", "600519.SH"),
    ],
)
def test_prefix_and_explicit_codes_reach_confirm_as_themselves(
    tmp_path: Path, thesis: str, symbol: str
) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    view = _fill(service, research_id, thesis, FLOOR_ONE)
    assert view["symbolSelection"]["symbols"] == [symbol]
    if thesis.endswith("600519.SH 均值回归") or "600519.SH" in thesis:
        assert view["symbolResolution"]["inferred"] == []
    else:
        raw = symbol.split(".")[0]
        assert view["symbolResolution"]["inferred"] == [{"raw": raw, "symbol": symbol}]


def test_uncertain_code_names_the_token_and_confirm_run_rejects_it(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    view = _fill(service, research_id, "A股股票 900901 均值回归", FLOOR_ONE)
    assert view["kind"] == "confirm_run"
    assert view["chatEnabled"] is False
    resolution = view["symbolResolution"]
    assert resolution["blocked"] is True
    assert resolution["code"] == "SYMBOL_UNRESOLVED"
    assert resolution["token"] == "900901"
    selection = view.get("symbolSelection")
    assert selection is None or selection["symbols"] == []
    pool = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    stored = service.store.load(research_id)
    assert stored.brief.universe.value.symbols != pool.symbols

    with pytest.raises(UserFacingError) as exc:
        service.handle({"type": "confirm_run", "research_id": research_id})
    assert exc.value.code == "SYMBOL_UNRESOLVED"
    assert exc.value.params["token"] == "900901"
    assert service.store.load(research_id).brief.universe.value.symbols == ()


def test_resolved_symbol_with_no_bars_blocks_confirm_run(tmp_path: Path) -> None:
    set_pool_data_loader(_NoBars(frozenset({"609999.SH"})))
    service = _service(tmp_path)
    research_id = _draft(service)
    view = _fill(service, research_id, "A股股票 609999 均值回归", FLOOR_ONE)
    resolution = view["symbolResolution"]
    assert resolution["blocked"] is True
    assert resolution["code"] == "SYMBOL_NO_DATA"
    assert resolution["symbol"] == "609999.SH"
    assert view["symbolSelection"]["symbols"] == ["609999.SH"]
    pool = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    assert service.store.load(research_id).brief.universe.value.symbols != pool.symbols

    with pytest.raises(UserFacingError) as exc:
        service.handle({"type": "confirm_run", "research_id": research_id})
    assert exc.value.code == "SYMBOL_NO_DATA"
    assert exc.value.params["symbol"] == "609999.SH"
    assert service.store.load(research_id).brief.universe.value.symbols == ("609999.SH",)


def test_description_with_no_symbol_still_uses_the_default_pool(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    view = _fill(service, research_id, "A股股票的均值回归", FLOOR_MANY)
    pool = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    assert view["symbolSelection"]["symbols"] == list(pool.symbols)
    assert view["symbolSelection"]["count"] == len(pool.symbols)
    assert view.get("symbolResolution") in (None, {"editable": False, "blocked": False})
    service.handle({"type": "confirm_run", "research_id": research_id})
    assert service.store.load(research_id).brief.universe.value.symbols == pool.symbols


def test_ordinary_english_and_chinese_do_not_block_the_default_pool(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    view = _fill(
        service,
        research_id,
        "A股股票的均值回归 mean reversion daily THE LOW CAP",
        FLOOR_MANY,
    )
    pool = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None
    assert view["symbolSelection"]["count"] == len(pool.symbols)
    resolution = view.get("symbolResolution")
    assert resolution is None or resolution["blocked"] is False


def test_editing_the_symbol_on_the_card_replaces_the_unresolved_token(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    _fill(service, research_id, "A股股票 900901 均值回归", FLOOR_ONE)
    service.handle(
        {
            "type": "set_research_symbol",
            "research_id": research_id,
            "symbol": "900901.SH",
        }
    )
    view = service.view_for(f"#/research/{research_id}")
    assert view["symbolResolution"]["blocked"] is False
    assert view["symbolSelection"]["symbols"] == ["900901.SH"]
    service.handle({"type": "confirm_run", "research_id": research_id})
    assert service.store.load(research_id).brief.universe.value.symbols == ("900901.SH",)


def test_named_symbol_below_the_floor_does_not_expand_to_the_pool(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    _fill(service, research_id, "A股股票 600519 均值回归", FLOOR_MANY)
    with pytest.raises(UserFacingError) as exc:
        service.handle({"type": "confirm_run", "research_id": research_id})
    assert exc.value.code == "UNIVERSE_TOO_FEW_SYMBOLS"
    assert service.store.load(research_id).brief.universe.value.symbols == ("600519.SH",)


def test_saved_research_without_resolution_fields_still_loads(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _draft(service)
    _fill(service, research_id, "美股股票的均值回归", FLOOR_MANY)
    raw = json.loads(SQLiteStore._encode(service.store.load(research_id)))
    universe = raw["brief"]["universe"]["value"]
    universe.pop("unresolved_tokens", None)
    universe.pop("inferred_symbols", None)
    for key in ("symbol_probe_symbols", "symbol_probe_missing", "symbol_probe_unavailable"):
        raw.pop(key, None)
    loaded = SQLiteStore._decode(json.dumps(raw))
    assert loaded.brief.universe.value.unresolved_tokens == ()
    assert loaded.brief.universe.value.inferred_symbols == ()
    assert loaded.symbol_probe_symbols == ()
