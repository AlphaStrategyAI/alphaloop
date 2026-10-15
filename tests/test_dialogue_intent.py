from engine.dialogue.intent import interpret
from engine.research.models import new_research
from datetime import UTC, datetime

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_universe_message_strips_trailing_slot_label_from_thesis() -> None:
    research = new_research("r-draft", NOW)
    intent = interpret("我想研究美股股票低波动回归，大致原理", research)
    thesis = next(value for key, value in intent.updates if key == "thesis")
    assert "大致原理" not in thesis
