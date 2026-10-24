"""Cumulative symbol regression corpus.

Every reviewer-found case gets a row in tests/data/symbol_regression_corpus.json.
Do not delete a row, and do not loosen an expected outcome, without product sign-off.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from engine.main import ResearchCommandService
from engine.research.models import AssetClass, Market
from engine.research.pool_data_shrink import set_pool_data_loader
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.symbol_identity import extract_symbol_mentions
from engine.research.symbol_pool import pool_for_market

CORPUS_PATH = Path(__file__).resolve().parent / "data" / "symbol_regression_corpus.json"
HOURS = "12 小时"
METHODS = "走样检验 样本外稳定 拥挤度 换手成本"
FLOOR = "至少 25 个 10 年 缺失不超过 5%"


def _rows() -> list[dict]:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    rows = payload["rows"]
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert payload["comment"]
    return rows


class _Bars:
    """Deterministic prices. Symbols named by the row have no bars; every other symbol does."""

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


def _card(tmp_path: Path, description: str, missing: frozenset[str]) -> tuple[dict, str]:
    set_pool_data_loader(_Bars(missing))
    service = ResearchCommandService(
        SQLiteStore(tmp_path / "corpus.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )
    research_id = service.handle({"type": "create_draft"})["research_id"]
    for message in (description, HOURS, METHODS, FLOOR):
        service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})
    view = service.view_for(f"#/research/{research_id}")
    universe = service.store.load(research_id).brief.universe.value
    assert universe is not None
    return view, universe.market.value


@pytest.mark.parametrize("row", _rows(), ids=lambda row: row["id"])
def test_symbol_regression_corpus(row: dict, tmp_path: Path) -> None:
    mentions = extract_symbol_mentions(row["description"])
    assert [
        {
            "raw": mention.raw,
            "canonical": mention.canonical,
            "kind": mention.kind,
            "inferred": mention.inferred,
        }
        for mention in mentions
    ] == row["extract"]

    view, market = _card(tmp_path, row["description"], frozenset(row.get("no_bars") or ()))
    assert view["kind"] == "confirm_run"
    assert market == row["market"]
    resolution = view.get("symbolResolution")
    selection = view.get("symbolSelection")
    card = row["card"]
    if resolution is None:
        assert card["symbols"] == []
        assert card["recognized"] == []
        assert card["asks"] == []
        assert card["hints"] == []
        assert card["blocked"] is False
        assert card["code"] is None
    else:
        assert resolution["blocked"] is card["blocked"]
        assert resolution["code"] == card["code"]
        assert resolution["symbols"] == card["symbols"]
        assert [item["symbol"] for item in resolution["inferred"]] == card["recognized"]
        assert resolution["asks"] == card["asks"]
        assert resolution["hints"] == card["hints"]
        assert (resolution.get("mismatches") or []) == (card.get("mismatches") or [])
        assert (resolution.get("unrecognized") or []) == (card.get("unrecognized") or [])
    if card["default_pool"]:
        pool = pool_for_market(Market(row["market"]), AssetClass.EQUITY, AssetClass.EQUITY)
        assert pool is not None
        assert selection is not None
        assert selection["source"] == "default_pool"
        assert selection["symbols"] == list(pool.symbols)
    elif card["symbols"]:
        assert selection is not None
        assert selection["symbols"] == card["symbols"]
        assert selection["source"] == "user_override"


def test_corpus_expectation_edits_require_product_approval() -> None:
    """An existing row's expected outcome changes only with a signed-off commit."""
    import subprocess

    def show(rev: str) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "show", f"{rev}:tests/data/symbol_regression_corpus.json"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return None

    previous = show("HEAD^")
    current = show("HEAD")
    if previous is None or current is None:
        return
    old_rows = {row["id"]: row for row in json.loads(previous)["rows"]}
    new_rows = {row["id"]: row for row in json.loads(current)["rows"]}
    changed = [
        row_id
        for row_id, row in old_rows.items()
        if row_id not in new_rows
        or row.get("extract") != new_rows[row_id].get("extract")
        or row.get("card") != new_rows[row_id].get("card")
    ]
    if not changed:
        return
    message = subprocess.check_output(["git", "log", "-1", "--format=%B"], text=True)
    assert "corpus-change-approved:" in message, changed
