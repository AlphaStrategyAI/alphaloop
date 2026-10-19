"""P0-5: V1 says it only runs mean reversion when the thesis is not one."""

from __future__ import annotations

import json
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from engine.export import build_research_record_pack, build_strategy_pack
from engine.main import ResearchCommandService
from engine.research.a1_copy import MOMENTUM_UNSUPPORTED_NOTICE
from engine.research.models import ResearchStatus, Slot, new_research
from engine.research.runtime import EnginePaths
from engine.research.specify import build_logic_statement
from engine.research.store import SQLiteStore
from engine.strategy import MarketPanel
from tests.test_export_pack import completed_research, reference_strategy
from tests.test_state_machine import locked_brief

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
NOTICE = "V1 只支持截面均值回归（反转）；你的论点会被记录但不会改变策略。要按均值回归继续吗？"
CARD = "策略族：均值回归（V1 唯一）· 论点文字仅作记录，不改变策略"


def _service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "d.db")
    return ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))


def test_momentum_thesis_is_not_locked_until_the_user_confirms(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.store.create(new_research("r-draft", NOW))
    service.handle(
        {
            "type": "send_dialogue",
            "research_id": "r-draft",
            "message": "美股动量策略",
        }
    )
    loaded = service.store.load("r-draft")
    assert loaded.brief.thesis.value is None
    assert NOTICE in loaded.dialogue[-1].text

    service.handle(
        {"type": "send_dialogue", "research_id": "r-draft", "message": "按均值回归继续"}
    )
    locked = service.store.load("r-draft")
    assert locked.brief.thesis.value == "美股动量策略"
    assert NOTICE not in locked.dialogue[-1].text


def test_mean_reversion_thesis_locks_without_the_notice(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.store.create(new_research("r-draft", NOW))
    service.handle(
        {
            "type": "send_dialogue",
            "research_id": "r-draft",
            "message": "美股股票的均值回归",
        }
    )
    loaded = service.store.load("r-draft")
    assert loaded.brief.thesis.value == "美股股票的均值回归"
    assert all(NOTICE not in turn.text for turn in loaded.dialogue)
    assert all(CARD not in turn.text for turn in loaded.dialogue)


def test_low_vol_reversion_is_not_treated_as_a_foreign_family(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.store.create(new_research("r-draft", NOW))
    service.handle(
        {
            "type": "send_dialogue",
            "research_id": "r-draft",
            "message": "美股低波动量价回归",
        }
    )
    loaded = service.store.load("r-draft")
    assert loaded.brief.thesis.value == "美股低波动量价回归"
    assert all(NOTICE not in turn.text for turn in loaded.dialogue)


def test_confirm_and_completed_views_show_notice_only_for_non_mean_reversion(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    momentum = replace(
        new_research("r-mom", NOW),
        brief=replace(locked_brief(), thesis=Slot("美股动量策略", True)),
        data_window_start=date(2014, 10, 17),
        data_window_end=date(2026, 10, 17),
        symbol_list_version="us_equity_large_cap_v1",
    )
    reversion = replace(
        new_research("r-rev", NOW),
        brief=locked_brief(),
        data_window_start=date(2014, 10, 17),
        data_window_end=date(2026, 10, 17),
        symbol_list_version="us_equity_large_cap_v1",
    )
    service.store.create(momentum)
    service.store.create(reversion)
    mom = service.view_for("#/research/r-mom")
    rev = service.view_for("#/research/r-rev")
    assert mom["kind"] == "confirm_run"
    assert mom["meanReversionOnlyNotice"] == MOMENTUM_UNSUPPORTED_NOTICE
    assert "策略族：均值回归" not in mom["meanReversionOnlyNotice"]
    assert "meanReversionOnlyNotice" not in rev or rev["meanReversionOnlyNotice"] in (None, "")
    raw_before = service.store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id=?",
        ("r-mom",),
    ).fetchone()[0]
    assert service.view_for("#/research/r-mom")["meanReversionOnlyNotice"] == MOMENTUM_UNSUPPORTED_NOTICE
    raw_after = service.store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id=?",
        ("r-mom",),
    ).fetchone()[0]
    assert raw_after == raw_before


def test_logic_statement_names_the_executed_family() -> None:
    spec = reference_strategy().spec
    statement = build_logic_statement(
        "美股动量策略",
        spec,
        version_number=1,
        had_prior_round=False,
    )
    assert statement.statement.startswith("论点：美股动量策略；")
    assert "实际执行：截面均值回归，回看" in statement.statement
    assert "回看天数=" not in statement.statement
    plain = build_logic_statement(
        "美股股票的均值回归",
        spec,
        version_number=1,
        had_prior_round=False,
    )
    assert "论点：美股股票的均值回归；" in plain.statement
    assert CARD not in plain.statement
    assert NOTICE not in plain.statement


def test_export_marks_family_and_warns_only_for_non_mean_reversion(tmp_path: Path) -> None:
    prices = pd.DataFrame(
        {"AAA": [10.0, 11.0, 9.5], "BBB": [8.0, 7.5, 8.5]},
        index=pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"], name="date"),
    )
    panel = MarketPanel(prices, prices.mean(axis=1).rename("SPX"))
    momentum = replace(reference_strategy().spec, thesis_locked="美股动量策略")
    strategy = replace(reference_strategy(), spec=momentum)
    pack = build_strategy_pack(
        completed_research(),
        strategy,
        panel,
        tmp_path / "pack.zip",
    )
    with zipfile.ZipFile(pack) as archive:
        spec = json.loads(archive.read("spec.json"))
        history = json.loads(archive.read("history/research.json"))
    assert spec["thesis_driven"] is False
    assert spec["strategy_family"] == "mean_reversion"
    assert spec["mean_reversion_only_notice"] == MOMENTUM_UNSUPPORTED_NOTICE
    assert "策略族：均值回归" not in spec["mean_reversion_only_notice"]
    assert history["thesis_driven"] is False
    assert history["mean_reversion_only_notice"] == MOMENTUM_UNSUPPORTED_NOTICE

    plain = replace(reference_strategy().spec, thesis_locked="美股股票的均值回归")
    plain_pack = build_strategy_pack(
        completed_research(),
        replace(reference_strategy(), spec=plain),
        panel,
        tmp_path / "plain.zip",
    )
    with zipfile.ZipFile(plain_pack) as archive:
        plain_spec = json.loads(archive.read("spec.json"))
    assert plain_spec["thesis_driven"] is False
    assert plain_spec["strategy_family"] == "mean_reversion"
    assert "mean_reversion_only_notice" not in plain_spec
    record = build_research_record_pack(
        replace(completed_research(), status=ResearchStatus.ENDED, export_eligible=False),
        tmp_path / "record.zip",
    )
    with zipfile.ZipFile(record) as archive:
        recorded = json.loads(archive.read("history/research.json"))
    assert recorded["strategy_family"] == "mean_reversion"
    assert recorded["thesis_driven"] is False


def test_old_state_json_without_pending_field_still_loads(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "old.db")
    store.create(new_research("r-old", NOW))
    raw = store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id = ?",
        ("r-old",),
    ).fetchone()[0]
    payload = json.loads(raw)
    payload.pop("pending_non_mr_thesis", None)
    store.connection.execute(
        "UPDATE researches SET state_json = ? WHERE research_id = ?",
        (json.dumps(payload), "r-old"),
    )
    store.connection.commit()
    loaded = SQLiteStore(tmp_path / "old.db").load("r-old")
    assert loaded.research_id == "r-old"
    assert loaded.pending_non_mr_thesis is None
