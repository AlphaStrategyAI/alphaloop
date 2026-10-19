"""M2 A0-pool: new research uses a >=100 name generated-date pool; v1 stays byte-identical."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.research.confirm_view import symbol_selection_payload
from engine.research.models import (
    AssetClass,
    CoverageFloor,
    Market,
    ResearchBrief,
    Slot,
    Universe,
    new_research,
)
from engine.research.planned_data_window import is_cn_listed_symbol
from engine.research.pool_data_shrink import set_pool_data_loader
from engine.research.symbol_pool import (
    EMPTY_POOL_DIALOGUE_PROMPT,
    pool_by_version,
    pool_for_market,
)
from engine.research.universe_pool import materialize_default_pool
from engine.research.universe_validation import ensure_runnable_universe
from tests.test_pool_data_shrink import _FakeLoader

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
POOLS = Path(__file__).resolve().parents[1] / "engine" / "research" / "symbol_pools"

US_V1_SHA256 = "c2acb35a225405a6085834547e0f7e56bda24fd606d37d5f6af9b723cfa7dc08"
CN_V1_SHA256 = "b10b1ba55cd127e4b75a69caad3f44f90c3da3694c0e6365fdd7f5da00f2a45f"
US_V2_ID = "us_equity_large_cap_v2"
CN_V2_ID = "cn_equity_large_cap_v2"
US_TICKER = re.compile(r"^[A-Z]{1,5}(-[A-Z])?$")
CN_TICKER = re.compile(r"^\d{6}\.(SH|SZ)$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw(version_id: str) -> dict:
    return json.loads((POOLS / f"{version_id}.json").read_text(encoding="utf-8"))


def _brief(market: Market, symbols: tuple[str, ...], *, version: str | None, override: bool) -> ResearchBrief:
    return ResearchBrief(
        thesis=Slot("均值回归", True),
        universe=Slot(
            Universe(
                market,
                AssetClass.EQUITY,
                AssetClass.EQUITY,
                symbols,
                symbol_list_version=version,
                user_symbols_override=override,
            ),
            True,
        ),
        max_effective_hours=Slot(8.0, True),
        round1_methods=Slot((), True),
        coverage_floor=Slot(CoverageFloor(25, 10, 5.0), True),
    )


def test_empty_pool_prompt_names_the_current_default_counts() -> None:
    assert EMPTY_POOL_DIALOGUE_PROMPT == (
        "要用哪组标的？默认：美股大市值 503 只或 A股大市值 300 只，也可以说「600519.SH」或「SPY、QQQ」。"
    )


def test_v1_pool_files_are_byte_identical() -> None:
    assert _sha256(POOLS / "us_equity_large_cap_v1.json") == US_V1_SHA256
    assert _sha256(POOLS / "cn_equity_large_cap_v1.json") == CN_V1_SHA256
    us = pool_by_version("us_equity_large_cap_v1")
    cn = pool_by_version("cn_equity_large_cap_v1")
    assert us is not None and cn is not None
    assert len(us.symbols) == 40 and len(cn.symbols) == 40
    assert len(us.symbols) == len(set(us.symbols))
    assert len(cn.symbols) == len(set(cn.symbols))
    assert "600519.SH" in cn.symbols


def test_new_research_defaults_to_single_market_pools_of_at_least_100() -> None:
    us = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    cn = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
    assert us is not None and cn is not None
    assert us.version_id == US_V2_ID
    assert cn.version_id == CN_V2_ID
    assert us.market is Market.US and cn.market is Market.CN
    assert us.display_name == "美股大市值"
    assert cn.display_name == "A股大市值"
    assert len(us.symbols) >= 100 and len(cn.symbols) >= 100
    assert len(us.symbols) == len(set(us.symbols))
    assert len(cn.symbols) == len(set(cn.symbols))
    assert us.symbols == tuple(sorted(us.symbols))
    assert cn.symbols == tuple(sorted(cn.symbols))
    assert all(US_TICKER.fullmatch(symbol) for symbol in us.symbols)
    assert all(CN_TICKER.fullmatch(symbol) for symbol in cn.symbols)
    assert not any(is_cn_listed_symbol(symbol) for symbol in us.symbols)
    assert all(is_cn_listed_symbol(symbol) for symbol in cn.symbols)
    assert "BRK-B" in us.symbols and "AAPL" in us.symbols
    assert "600519.SH" in cn.symbols
    assert set(us.symbols).isdisjoint(cn.symbols)


def test_v2_metadata_records_source_rule_and_as_of_date() -> None:
    us = _raw(US_V2_ID)
    cn = _raw(CN_V2_ID)
    for raw, as_of in ((us, "2026-10-16"), (cn, "2026-10-19")):
        selection = raw["selection"]
        assert selection["kind"] == "generated_date_membership"
        assert selection["rule"]
        assert selection["source_url"].startswith("https://")
        assert selection["source_retrieved_at"] == "2026-10-19"
        assert re.fullmatch(r"[0-9a-f]{64}", selection["source_sha256"])
        assert "幸存者" in selection["survivorship"]
        assert raw["generated_date"] == as_of
        assert "yahoo" not in json.dumps(selection).lower()
        assert "akshare" not in json.dumps(selection).lower()
    assert us["selection"]["source_sha256"] == (
        "78d66dbd7901dfc54347b4072bc47d0999202c78846a01bc2b360021dc143231"
    )
    assert us["selection"]["cross_check_sha256"] == (
        "01ebf197474145023e6761450a542260ec3986117d4e7b6732dfe5efc2b07ccb"
    )
    assert cn["selection"]["source_sha256"] == (
        "25ef515205586babfbc590b1a21671582e75aec4da863cafa0c38e508bc5b8ec"
    )
    assert cn["selection"]["source_etag"] == "C763967B5F9A95F6ABE04B860813013C"


def test_pinned_v1_research_keeps_symbols_and_confirm_line() -> None:
    v1 = pool_by_version("us_equity_large_cap_v1")
    assert v1 is not None
    research = replace(
        new_research("r-old-us", NOW),
        brief=_brief(Market.US, v1.symbols, version=v1.version_id, override=False),
        symbol_list_version=v1.version_id,
    )
    materialized = materialize_default_pool(research)
    assert materialized.brief.universe.value.symbols == v1.symbols
    assert materialized.symbol_list_version == "us_equity_large_cap_v1"
    updated = ensure_runnable_universe(research)
    assert updated.brief.universe.value.symbols == v1.symbols
    assert updated.symbol_list_version == "us_equity_large_cap_v1"
    payload = symbol_selection_payload(research)
    assert payload is not None
    assert payload["count"] == 40
    assert payload["listVersion"] == "1"
    assert payload["symbols"] == list(v1.symbols)
    assert payload["summaryLine"] == "40 只 · 美股大市值 · 版本 1 · 2026-10-17 · 默认标的池"


def test_new_empty_universe_confirm_line_uses_v2() -> None:
    research = replace(
        new_research("r-new-us", NOW),
        brief=_brief(Market.US, (), version=None, override=False),
    )
    payload = symbol_selection_payload(research)
    assert payload is not None
    us = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert us is not None
    assert payload["count"] == len(us.symbols) >= 100
    assert payload["listName"] == "美股大市值"
    assert payload["listVersion"] == "2"
    assert payload["generatedDate"] == "2026-10-16"
    assert payload["summaryLine"] == (
        f"{len(us.symbols)} 只 · 美股大市值 · 版本 2 · 2026-10-16 · 默认标的池"
    )
    assert payload["isDefaultPool"] is True


def test_shrink_before_run_only_drops_names_inside_the_new_default_pool() -> None:
    pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
    assert pool is not None and pool.version_id == US_V2_ID
    missing = frozenset(pool.symbols[:2])
    set_pool_data_loader(_FakeLoader(missing))
    research = replace(
        new_research("r-shrink-v2", NOW),
        brief=_brief(Market.US, (), version=None, override=False),
    )
    updated = ensure_runnable_universe(research)
    kept = updated.brief.universe.value.symbols
    assert updated.symbol_list_version == US_V2_ID
    assert set(kept).isdisjoint(missing)
    assert set(kept) | missing == set(pool.symbols)
    assert len(kept) == len(pool.symbols) - 2
    assert updated.pool_data_dropped_count == 2
    assert tuple(kept) == tuple(symbol for symbol in pool.symbols if symbol not in missing)
