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
from engine.research.models import ResearchStatus, new_research
from engine.research.run_gate import evaluate_run_gate
from engine.research.runtime import EnginePaths
from engine.research.source_acknowledgement import record_acknowledgement
from engine.research.store import SQLiteStore
from engine.research.families import PRODUCT_FAMILY_IDS
from engine.research.thesis_scope import (
    CONFIRM_CARD_NOTICE,
    FAMILY_FOLLOWUP,
    MEAN_REVERSION_ACK_MESSAGE,
    MEAN_REVERSION_DECLINE_NOTICE,
    MEAN_REVERSION_ONLY_NOTICE,
    family_repick_notice,
)
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


def _source_for(thesis: str) -> str:
    return "akshare_sina_daily" if "A股" in thesis or "A 股" in thesis else "yahoo_daily"


def test_disclosed_families_stay_disabled_until_yes_then_run(tmp_path: Path) -> None:
    theses = (
        "美股低波策略",
        "A股基本面因子，买账面更便宜的公司",
        "美股全天候",
        "美股股票的股债再平衡",
    )
    for thesis in theses:
        service = _service(tmp_path)
        research_id = _fill(service, thesis)
        view = service.view_for(f"#/research/{research_id}")
        assert view["kind"] == "confirm_run", thesis
        assert view["meanReversionOnlyNotice"] == MEAN_REVERSION_ONLY_NOTICE
        assert view["runGate"] == {"runnable": False, "code": "MEAN_REVERSION_ACK_REQUIRED"}, thesis
        with pytest.raises(UserFacingError) as blocked:
            service.handle(
                {
                    "type": "confirm_run",
                    "research_id": research_id,
                    "data_source_id": _source_for(thesis),
                    "unlicensed_acknowledged": True,
                }
            )
        assert blocked.value.code == "MEAN_REVERSION_ACK_REQUIRED"
        assert blocked.value.message == MEAN_REVERSION_ACK_MESSAGE
        assert service.store.load(research_id).status is ResearchStatus.DRAFT
        _say(service, research_id, "按均值回归继续")
        adopted = service.store.load(research_id)
        assert adopted.mean_reversion_adopted is True
        assert adopted.brief.thesis.value == thesis
        after = service.view_for(f"#/research/{research_id}")
        assert after["meanReversionOnlyNotice"] == CONFIRM_CARD_NOTICE
        assert after["runGate"]["code"] != "MEAN_REVERSION_ACK_REQUIRED"
        ready = evaluate_run_gate(
            service.store.load(research_id),
            data_source_id=_source_for(thesis),
            unlicensed_acknowledged=True,
            settings_path=service.paths.data.settings_file,
        )
        assert ready.runnable is True
        started = service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": _source_for(thesis),
                "unlicensed_acknowledged": True,
            }
        )
        assert started.get("status") == "running"


def test_stock_bond_and_all_weather_are_recognized(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for thesis in ("股债再平衡", "全天候", "all weather", "60/40 rebalance"):
        research_id = service.handle({"type": "create_draft"})["research_id"]
        _say(service, research_id, thesis)
        loaded = service.store.load(research_id)
        assert loaded.brief.thesis.value == thesis
        assert loaded.mean_reversion_adopted is False
        assert all("没能理解你的意思" not in turn.text for turn in loaded.dialogue)
        assert MEAN_REVERSION_ONLY_NOTICE not in loaded.dialogue[-1].text


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


def test_momentum_yes_is_not_adoption_and_the_question_is_absent(tmp_path: Path) -> None:
    for answer in ("按均值回归继续", "是", "可以", "yes"):
        service = _service(tmp_path)
        research_id = _fill(service, "美股趋势突破")
        _say(service, research_id, answer)
        loaded = service.store.load(research_id)
        assert loaded.mean_reversion_adopted is False
        assert loaded.repicked_family == ""
        assert loaded.status is ResearchStatus.DRAFT
        assert all(MEAN_REVERSION_ONLY_NOTICE not in turn.text for turn in loaded.dialogue)
        view = service.view_for(f"#/research/{research_id}")
        assert view["meanReversionOnlyNotice"] == MOMENTUM_UNSUPPORTED_NOTICE
        assert view["runGate"]["code"] == "STRATEGY_FAMILY_NOT_RUNNABLE"
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
        assert service.store.load(research_id).status is ResearchStatus.DRAFT


def test_explicit_family_repick_is_the_only_momentum_way_forward(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _fill(service, "美股动量策略")
    _say(service, research_id, "选择均值回归")
    loaded = service.store.load(research_id)
    assert loaded.brief.thesis.value == "美股动量策略"
    assert loaded.repicked_family == "mean_reversion"
    assert loaded.mean_reversion_adopted is True
    view = service.view_for(f"#/research/{research_id}")
    notice = family_repick_notice("mean_reversion")
    assert view["repickedFamily"] == "mean_reversion"
    assert view["meanReversionOnlyNotice"] == notice
    assert notice == "已改用均值回归。你原来的论点没有采纳，这一族的方向和你的原话不同。"
    assert loaded.dialogue[-1].text == notice
    assert MEAN_REVERSION_ONLY_NOTICE not in view["meanReversionOnlyNotice"]
    ready = evaluate_run_gate(
        loaded,
        data_source_id="yahoo_daily",
        unlicensed_acknowledged=True,
        settings_path=service.paths.data.settings_file,
    )
    assert ready.runnable is True
    started = service.handle(
        {
            "type": "confirm_run",
            "research_id": research_id,
            "data_source_id": "yahoo_daily",
            "unlicensed_acknowledged": True,
        }
    )
    assert started.get("status") == "running"


def test_blocked_family_shows_unsupported_notice_not_the_follow_up(tmp_path: Path) -> None:
    """Momentum, trend, and breakout never get the unrecognized-family follow-up."""
    for thesis in ("美股动量策略", "美股趋势策略", "美股突破策略"):
        service = _service(tmp_path)
        research_id = _fill(service, thesis)
        loaded = service.store.load(research_id)
        joined = "\n".join(turn.text for turn in loaded.dialogue)
        assert FAMILY_FOLLOWUP not in joined, thesis
        assert MEAN_REVERSION_ONLY_NOTICE not in joined, thesis
        view = service.view_for(f"#/research/{research_id}")
        assert view["meanReversionOnlyNotice"] == MOMENTUM_UNSUPPORTED_NOTICE, thesis
        assert view.get("repickedFamily") in (None, "")


def _decision(service: ResearchCommandService, research_id: str) -> dict[str, object]:
    loaded = service.store.load(research_id)
    return {
        "thesis": loaded.brief.thesis.value,
        "adopted": loaded.mean_reversion_adopted,
        "declined": loaded.mean_reversion_declined,
        "repick": loaded.repicked_family,
        "status": loaded.status,
        "pending": loaded.pending_non_mr_thesis,
        "dialogue": [turn.text for turn in loaded.dialogue],
    }


def test_ack_button_phrase_and_typed_yes_write_the_same_record(tmp_path: Path) -> None:
    phrase = "按均值回归继续"
    first = _service(tmp_path)
    first_id = _fill(first, "美股低波策略")
    before = first.view_for(f"#/research/{first_id}")
    assert before["chatEnabled"] is True
    assert before["meanReversionChoice"] is True
    _say(first, first_id, phrase)
    second = _service(tmp_path)
    second_id = _fill(second, "美股低波策略")
    _say(second, second_id, phrase)
    assert _decision(first, first_id) == _decision(second, second_id)
    english = _service(tmp_path)
    english_id = _fill(english, "美股低波策略")
    _say(english, english_id, "Continue with mean reversion")
    zh = _decision(first, first_id)
    en = _decision(english, english_id)
    assert en["adopted"] is True and zh["adopted"] is True
    assert en["thesis"] == zh["thesis"] == "美股低波策略"
    assert en["declined"] is False and en["status"] is ResearchStatus.DRAFT
    assert en["repick"] == zh["repick"]
    view = first.view_for(f"#/research/{first_id}")
    assert view["meanReversionChoice"] is False
    assert view["runGate"]["code"] != "MEAN_REVERSION_ACK_REQUIRED"


def test_decline_button_phrase_stays_draft_and_opens_chips(tmp_path: Path) -> None:
    decisions = []
    for phrase in ("不继续", "Don't continue"):
        service = _service(tmp_path)
        research_id = _fill(service, "美股低波策略")
        _say(service, research_id, phrase)
        loaded = service.store.load(research_id)
        assert loaded.status is ResearchStatus.DRAFT
        assert loaded.mean_reversion_adopted is False
        assert loaded.mean_reversion_declined is True
        assert loaded.brief.thesis.value == "美股低波策略"
        assert loaded.dialogue[-1].text == MEAN_REVERSION_DECLINE_NOTICE
        view = service.view_for(f"#/research/{research_id}")
        assert view["chatEnabled"] is True
        assert view["meanReversionChoice"] is False
        assert view["familyChipIds"] == list(PRODUCT_FAMILY_IDS)
        assert view["runGate"]["runnable"] is False
        decisions.append(_decision(service, research_id))
    assert decisions[0]["adopted"] == decisions[1]["adopted"]
    assert decisions[0]["declined"] == decisions[1]["declined"]
    assert decisions[0]["thesis"] == decisions[1]["thesis"]
    assert decisions[0]["status"] == decisions[1]["status"]


def test_family_chips_follow_market_and_a_re_pick_uses_the_same_handler(tmp_path: Path) -> None:
    us = _service(tmp_path)
    us_id = _fill(us, "美股动量策略")
    us_view = us.view_for(f"#/research/{us_id}")
    assert us_view["chatEnabled"] is True
    assert us_view["familyChipIds"] == list(PRODUCT_FAMILY_IDS)
    assert us_view["meanReversionChoice"] is False
    cn = _service(tmp_path)
    cn_id = _fill(cn, "A股动量策略")
    cn_view = cn.view_for(f"#/research/{cn_id}")
    assert cn_view["familyChipIds"] == ["mean_reversion"]
    _say(us, us_id, "均值回归")
    repicked = us.store.load(us_id)
    assert repicked.brief.thesis.value == "美股动量策略"
    assert repicked.repicked_family == "mean_reversion"
    assert repicked.mean_reversion_adopted is True
    view = us.view_for(f"#/research/{us_id}")
    assert view["meanReversionOnlyNotice"] == family_repick_notice("mean_reversion")
    assert view["familyChipIds"] == []
    ready = evaluate_run_gate(
        repicked,
        data_source_id="yahoo_daily",
        unlicensed_acknowledged=True,
        settings_path=us.paths.data.settings_file,
    )
    assert ready.runnable is True
    other = _service(tmp_path)
    other_id = _fill(other, "美股动量策略")
    _say(other, other_id, "Low volatility")
    chosen = other.store.load(other_id)
    assert chosen.repicked_family == "low_volatility"
    assert chosen.mean_reversion_adopted is False
    assert chosen.brief.thesis.value == "美股动量策略"
    card = other.view_for(f"#/research/{other_id}")
    assert card["meanReversionOnlyNotice"] == family_repick_notice("low_volatility")
    assert card["meanReversionChoice"] is True
    assert card["runGate"]["code"] == "MEAN_REVERSION_ACK_REQUIRED"


def test_us_volatility_squeeze_asks_the_family_follow_up(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    _say(service, research_id, "US volatility squeeze strategy")
    loaded = service.store.load(research_id)
    assert loaded.brief.thesis.value is None
    assert loaded.pending_non_mr_thesis == "US volatility squeeze strategy"
    assert "没能理解你的意思" not in loaded.dialogue[-1].text
    assert loaded.dialogue[-1].text == FAMILY_FOLLOWUP
    view = service.view_for(f"#/research/{research_id}")
    assert view["kind"] == "draft"
    assert view["familyChipIds"] == list(PRODUCT_FAMILY_IDS)
    assert view["chatEnabled"] is True


def test_stock_bond_and_all_weather_lock_the_same_market_in_zh_and_en(tmp_path: Path) -> None:
    pairs = (
        (("股债再平衡", "stock-bond rebalance"), "US", "fund", ("SPY", "AGG"), "美股 · 基金"),
        (
            ("全天候", "all weather"),
            "US",
            "fund",
            ("SPY", "TLT", "IEF", "GLD", "DBC"),
            "美股 · 基金",
        ),
        (("A股股债再平衡", "China stock-bond rebalance"), "CN", "equity", (), "A 股 · 股票"),
    )
    for theses, market, asset, symbols, label in pairs:
        seen = []
        for thesis in theses:
            service = _service(tmp_path)
            research_id = service.handle({"type": "create_draft"})["research_id"]
            _say(service, research_id, thesis)
            loaded = service.store.load(research_id)
            universe = loaded.brief.universe.value
            assert universe is not None, thesis
            assert universe.market_unspecified is False, thesis
            assert universe.market.value == market, thesis
            assert universe.asset_class.value == asset, thesis
            assert universe.symbols == symbols, thesis
            listing = service.view_for("#/research")
            row = next(item for item in listing["rows"] if item["id"] == research_id)
            assert row["universeLabel"] == label, thesis
            seen.append((universe.market.value, universe.asset_class.value, universe.symbols))
        assert seen[0] == seen[1]


def test_unlocked_universe_list_row_says_not_selected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    listing = service.view_for("#/research")
    row = next(item for item in listing["rows"] if item["id"] == research_id)
    assert row["universeLabel"] == "待选择"
    assert row["universeLabel"] != "A 股 · 股票"


def test_unrecognized_family_asks_instead_of_running_mean_reversion(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = service.handle({"type": "create_draft"})["research_id"]
    _say(service, research_id, "美股波动收缩策略")
    loaded = service.store.load(research_id)
    assert loaded.brief.thesis.value is None
    assert loaded.mean_reversion_adopted is False
    assert FAMILY_FOLLOWUP in loaded.dialogue[-1].text
    assert service.view_for(f"#/research/{research_id}")["kind"] == "draft"


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
