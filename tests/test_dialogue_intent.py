from datetime import UTC, datetime

from engine.dialogue.intent import interpret
from engine.dialogue.prompts import SlotName
from engine.research.models import new_research

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_thesis_slot_accepts_combined_market_and_thesis() -> None:
    research = new_research("r-draft", NOW)
    intent = interpret("美股股票的均值回归", research, SlotName.THESIS)
    keys = {key for key, _ in intent.updates}
    assert "thesis" in keys
    assert "universe" in keys
    thesis = next(value for key, value in intent.updates if key == "thesis")
    assert "均值回归" in thesis


def test_extracts_cn_listed_tickers() -> None:
    research = new_research("r-draft", NOW)
    intent = interpret("A股 600519.SH、000858.SZ", research, SlotName.UNIVERSE)
    universe = next(value for key, value in intent.updates if key == "universe")
    assert "600519.SH" in universe.symbols
    assert "000858.SZ" in universe.symbols


def test_minutes_parsed_for_time_slot() -> None:
    research = new_research("r-draft", NOW)
    intent = interpret("30 分钟", research, SlotName.MAX_EFFECTIVE_HOURS)
    hours = next(value for key, value in intent.updates if key == "max_effective_hours")
    assert hours == 0.5
