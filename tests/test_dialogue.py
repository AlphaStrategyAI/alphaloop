from datetime import UTC, datetime

from engine.dialogue.intent import IntentKind, interpret
from engine.dialogue.slots import SlotName, apply_intent, next_question
from engine.research.models import AssetClass, Market, new_research

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_direction_message_fills_relevant_slots_but_does_not_start() -> None:
    research = new_research("r-dialogue", NOW)

    intent = interpret("我想研究美股低波动回归", research)
    updated = apply_intent(research, intent, NOW)

    assert intent.kind is IntentKind.PROVIDE
    assert updated.brief.thesis.value == "美股低波动回归"
    assert updated.brief.universe.value is not None
    assert updated.brief.universe.value.market is Market.US
    assert updated.brief.universe.value.asset_class is AssetClass.EQUITY
    assert not updated.brief.thesis.locked
    assert updated.status.value == "draft"
    assert next_question(updated).slot is SlotName.THESIS


def test_each_slot_requires_explicit_lock_before_confirm_run() -> None:
    research = new_research("r-lock", NOW)
    messages = (
        "研究美股低波动回归",
        "锁定大致原理",
        "锁定资产类别",
        "最长有效研究时间12小时并锁定",
        "第一轮用走样检验、样本外稳定、拥挤度、换手成本并锁定",
        "最低覆盖至少50个资产、10年、缺失不超过5%并锁定",
    )
    for message in messages:
        research = apply_intent(research, interpret(message, research), NOW)

    prompt = next_question(research)
    assert prompt.slot is None
    assert prompt.message == "五项研究设定已锁定，请检查确认开跑卡。"


def test_off_topic_is_rejected_without_mutation() -> None:
    research = new_research("r-offtopic", NOW)
    intent = interpret("给我讲个笑话", research)

    assert intent.kind is IntentKind.OFF_TOPIC
    assert apply_intent(research, intent, NOW) == research
    assert "只用于完善五项研究设定" in intent.response


def test_confirmation_cannot_be_inferred_from_casual_affirmation() -> None:
    research = new_research("r-yes", NOW)
    intent = interpret("好啊", research)
    assert intent.kind is IntentKind.OFF_TOPIC
