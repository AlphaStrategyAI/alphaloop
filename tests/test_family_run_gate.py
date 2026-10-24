"""Family detection, the shared run gate, and literature filtered by family."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.a1_copy import MOMENTUM_UNSUPPORTED_NOTICE, STRATEGY_FAMILY_NOT_RUNNABLE
from engine.research.family_intent import classify_thesis
from engine.research.gather import Material, gather_materials
from engine.research.material_relevance import strategy_key_terms
from engine.research.models import new_research
from engine.research.run_gate import evaluate_run_gate
from engine.research.runtime import EnginePaths
from engine.research.source_acknowledgement import record_acknowledgement
from engine.research.store import SQLiteStore
from engine.research.thesis_scope import CONFIRM_CARD_NOTICE
from engine.research.user_errors import UserFacingError

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
HOURS = "12 小时"
METHODS = "走样检验 样本外稳定 换手成本"
FLOOR = "至少 1 个 10 年 缺失不超过 5%"
FETCHED = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)


def _service(tmp_path: Path) -> ResearchCommandService:
    return ResearchCommandService(
        SQLiteStore(tmp_path / "family.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )


def _say(service: ResearchCommandService, research_id: str, message: str) -> None:
    service.handle({"type": "send_dialogue", "research_id": research_id, "message": message})


def _fill(service: ResearchCommandService, thesis: str, *, ack: bool = False) -> str:
    research_id = service.handle({"type": "create_draft"})["research_id"]
    _say(service, research_id, thesis)
    if ack:
        _say(service, research_id, "按均值回归继续")
    for message in (HOURS, METHODS, FLOOR):
        _say(service, research_id, message)
    return research_id


def _paper(material_id: str, title: str, abstract: str) -> Material:
    return Material(
        material_id=material_id,
        source="papers",
        title=title,
        url=f"https://doi.org/{material_id}",
        text=abstract,
        fetched_at=FETCHED,
        published_at=None,
    )


class _Papers:
    def __init__(self, materials: tuple[Material, ...]) -> None:
        self._materials = materials

    def fetch(self, query: str) -> tuple[Material, ...]:
        return self._materials


def test_keyword_table_covers_zh_and_en_for_every_family() -> None:
    cases = {
        "买低市盈率的基本面因子": "fundamental_factor",
        "fundamental valuation factor": "fundamental_factor",
        "股债再平衡 60/40": "stock_bond_rebalance",
        "stock-bond rebalance": "stock_bond_rebalance",
        "全天候配置": "all_weather",
        "all weather portfolio": "all_weather",
        "美股低波策略": "low_volatility",
        "low volatility stocks": "low_volatility",
        "美股动量突破": "momentum",
        "momentum breakout": "momentum",
        "美股股票的均值回归": "mean_reversion",
        "cross-sectional mean reversion": "mean_reversion",
        "美股低波动量价回归": "mean_reversion",
    }
    for text, family_id in cases.items():
        assert classify_thesis(text).family_id == family_id, text


def test_fundamental_is_disclosed_instead_of_running_silently(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _fill(service, "A股基本面因子，买低市盈率高ROE的股票", ack=True)
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "confirm_run"
    assert view["meanReversionOnlyNotice"] == CONFIRM_CARD_NOTICE
    assert view["runGate"]["code"] != "STRATEGY_FAMILY_NOT_RUNNABLE"
    assert all("没能理解你的意思" not in turn["text"] for turn in view["dialogue"])


def test_stock_bond_and_all_weather_reach_a_card(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for thesis in ("股债再平衡", "全天候", "all weather", "60/40 rebalance"):
        research_id = service.handle({"type": "create_draft"})["research_id"]
        _say(service, research_id, thesis)
        loaded = service.store.load(research_id)
        assert loaded.pending_non_mr_thesis == thesis
        assert all("没能理解你的意思" not in turn.text for turn in loaded.dialogue)
        assert CONFIRM_CARD_NOTICE not in loaded.dialogue[-1].text or thesis
        _say(service, research_id, "按均值回归继续")
        adopted = service.store.load(research_id)
        assert adopted.brief.thesis.value == thesis
        assert adopted.pending_non_mr_thesis is None


def test_momentum_card_and_confirm_run_agree(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _fill(service, "美股动量策略")
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "confirm_run"
    assert view["meanReversionOnlyNotice"] == MOMENTUM_UNSUPPORTED_NOTICE
    assert view["runGate"] == {"runnable": False, "code": "STRATEGY_FAMILY_NOT_RUNNABLE"}
    with pytest.raises(UserFacingError) as exc:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
            }
        )
    assert exc.value.code == "STRATEGY_FAMILY_NOT_RUNNABLE"
    assert exc.value.message == STRATEGY_FAMILY_NOT_RUNNABLE


def test_adopting_mean_reversion_clears_the_momentum_block(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _fill(service, "美股动量策略")
    _say(service, research_id, "按均值回归继续")
    view = service.view_for(f"#/research/{research_id}")
    assert view["meanReversionOnlyNotice"] == CONFIRM_CARD_NOTICE
    assert view["runGate"]["code"] != "STRATEGY_FAMILY_NOT_RUNNABLE"
    started = service.handle(
        {
            "type": "confirm_run",
            "research_id": research_id,
            "data_source_id": "yahoo_daily",
            "unlicensed_acknowledged": True,
        }
    )
    assert started.get("status") == "running"


def test_removing_a_share_side_uses_the_stored_yahoo_acknowledgement(tmp_path: Path) -> None:
    service = _service(tmp_path)
    record_acknowledgement("yahoo_daily", NOW, service.paths.data.settings_file)
    research_id = _fill(service, "600519 和 SPY 的均值回归")
    service.handle({"type": "remove_market_side", "research_id": research_id, "side": "cn"})
    view = service.view_for(f"#/research/{research_id}")
    yahoo = next(
        item for item in view["symbolSelection"]["priceSources"] if item["id"] == "yahoo_daily"
    )
    assert yahoo["acknowledgedAt"]
    assert view["symbolSelection"]["dataSourcePending"] is True
    research = service.store.load(research_id)
    pending = evaluate_run_gate(
        research,
        data_source_id="",
        unlicensed_acknowledged=False,
        settings_path=service.paths.data.settings_file,
    )
    assert pending.runnable is False
    assert pending.code == "DATA_SOURCE_UNBOUND"
    ready = evaluate_run_gate(
        research,
        data_source_id="yahoo_daily",
        unlicensed_acknowledged=False,
        settings_path=service.paths.data.settings_file,
    )
    assert ready.runnable is True
    started = service.handle(
        {
            "type": "confirm_run",
            "research_id": research_id,
            "data_source_id": "yahoo_daily",
        }
    )
    assert started.get("status") == "running"
    assert service.store.load(research_id).data_source_id == "yahoo_daily"


def test_family_papers_drop_when_nothing_matches_that_family() -> None:
    query = "A股基本面因子，买低估值"
    assert "基本面" in strategy_key_terms(query)
    assert "均值回归" not in strategy_key_terms(query)
    unrelated = _paper("doi:mr", "Short-term reversal and mean reversion", "mean reversion")
    relevant = _paper("doi:val", "Fundamental valuation", "value")
    batch = gather_materials(query, (_Papers((unrelated, relevant)),))
    assert {item.material_id for item in batch.materials} == {"doi:val"}

    empty = gather_materials(query, (_Papers((unrelated,)),))
    assert empty.materials == ()
    assert empty.no_relevant_materials is True


def test_old_state_without_the_adoption_flag_still_loads(tmp_path: Path) -> None:
    import json

    store = SQLiteStore(tmp_path / "old.db")
    store.create(new_research("r-old", NOW))
    raw = store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id = ?",
        ("r-old",),
    ).fetchone()[0]
    payload = json.loads(raw)
    payload.pop("mean_reversion_adopted", None)
    store.connection.execute(
        "UPDATE researches SET state_json = ? WHERE research_id = ?",
        (json.dumps(payload), "r-old"),
    )
    store.connection.commit()
    loaded = SQLiteStore(tmp_path / "old.db").load("r-old")
    assert loaded.mean_reversion_adopted is False
    assert loaded.research_id == "r-old"
