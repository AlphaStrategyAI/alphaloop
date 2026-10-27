"""Cumulative EN + ZH slot-example corpus.

Every prompt example the English or Chinese UI shows, and every synonym added
for those slots, gets a row in tests/data/dialogue_slot_corpus.json. The #152
ticker corpus stays in tests/data/symbol_regression_corpus.json. Both files are
parametrized in full on every head. Do not delete a row or loosen an expected
outcome without product sign-off.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.models import DialogueRole, ResearchStatus
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError

CORPUS_PATH = Path(__file__).resolve().parent / "data" / "dialogue_slot_corpus.json"
SYMBOL_CORPUS_PATH = Path(__file__).resolve().parent / "data" / "symbol_regression_corpus.json"
APOLOGY = "没能理解你的意思"


def _rows() -> list[dict]:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    rows = payload["rows"]
    ids = [row["id"] for row in rows]
    assert ids, "slot corpus must not be empty"
    assert len(ids) == len(set(ids))
    assert payload["comment"]
    return rows


def _service(tmp_path: Path) -> ResearchCommandService:
    return ResearchCommandService(
        SQLiteStore(tmp_path / "slots.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )


@pytest.mark.parametrize("row", _rows(), ids=lambda row: row["id"])
def test_dialogue_slot_corpus(row: dict, tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    for message in row["messages"]:
        service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})
    loaded = service.store.load(research_id)
    brief = loaded.brief
    assistants = [turn.text for turn in loaded.dialogue if turn.role is DialogueRole.ASSISTANT]

    if row.get("no_apology"):
        assert all(APOLOGY not in text for text in assistants), assistants

    if "hours" in row:
        assert brief.max_effective_hours.value == pytest.approx(row["hours"])
    if row.get("hours_unset"):
        assert brief.max_effective_hours.value is None

    if "methods" in row:
        methods = brief.round1_methods.value or ()
        got = [item.method_id for item in methods]
        assert sorted(got) == sorted(row["methods"])
        assert len(got) == len(set(got)) == len(row["methods"])

    if "coverage" in row:
        floor = brief.coverage_floor.value
        assert floor is not None
        expect = row["coverage"]
        assert floor.min_assets == expect["assets"]
        assert floor.min_years == expect["years"]
        assert floor.max_missing_pct == pytest.approx(expect["missing"])

    if "symbols" in row:
        universe = brief.universe.value
        assert universe is not None
        assert list(universe.symbols) == row["symbols"]
        assert universe.user_symbols_override is True

    if "apology_turns" in row:
        failures = [text for text in assistants if APOLOGY in text]
        assert len(failures) == row["apology_turns"]
        for text in failures:
            assert text.count(APOLOGY) == 1, text

    needs_view = any(key in row for key in ("kind", "run_gate", "run_gate_not", "confirm_blocked"))
    if not needs_view:
        return
    view = service.view_for(f"#/research/{research_id}")
    if "kind" in row:
        assert view["kind"] == row["kind"]
    gate = view.get("runGate") or {}
    if "run_gate" in row:
        # The card's first reason can be the missing source (N3) while confirm_run
        # with an explicit source still reports the coverage floor.
        assert gate["code"] == row.get("view_run_gate", row["run_gate"])
        assert gate["runnable"] is False
    if "run_gate_params" in row and "view_run_gate" not in row:
        assert gate["params"] == row["run_gate_params"]
    if "run_gate_not" in row:
        assert gate.get("code") != row["run_gate_not"]
    if row.get("confirm_blocked"):
        with pytest.raises(UserFacingError) as exc:
            service.handle(
                {
                    "type": "confirm_run",
                    "research_id": research_id,
                    "data_source_id": "yahoo_daily",
                    "unlicensed_acknowledged": True,
                }
            )
        assert exc.value.code == row["run_gate"]
        assert exc.value.params == row.get("run_gate_params", exc.value.params)
        assert service.store.load(research_id).status is ResearchStatus.DRAFT


def test_symbol_regression_corpus_still_gates_every_ticker_row() -> None:
    """#152 ticker rows stay in their own corpus and are not trimmed here."""
    payload = json.loads(SYMBOL_CORPUS_PATH.read_text(encoding="utf-8"))
    ids = [row["id"] for row in payload["rows"]]
    assert "cn-600519" in ids
    assert "us-aapl" in ids or any("AAPL" in json.dumps(row) for row in payload["rows"])
    assert len(ids) == len(set(ids))
    assert len(ids) >= 10
