from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from engine.dialogue.intent import Intent, IntentKind
from engine.research.models import Research, ResearchBrief, Slot
from engine.research.state_machine import all_slots_locked


class SlotName(StrEnum):
    THESIS = "thesis"
    UNIVERSE = "universe"
    MAX_EFFECTIVE_HOURS = "max_effective_hours"
    ROUND1_METHODS = "round1_methods"
    COVERAGE_FLOOR = "coverage_floor"


@dataclass(frozen=True, slots=True)
class DialoguePrompt:
    slot: SlotName | None
    message: str


QUESTIONS = {
    SlotName.THESIS: "这个策略凭什么获得收益，哪个可观察信号代表这个机制？",
    SlotName.UNIVERSE: "请锁定市场、资产类别；基金还要说明底层是股票还是债券。",
    SlotName.MAX_EFFECTIVE_HOURS: "最多允许多少小时的有效研究时间？暂停和等待确认不计时。",
    SlotName.ROUND1_METHODS: "第一轮使用哪些冻结验证方法？",
    SlotName.COVERAGE_FLOOR: "最低覆盖需要多少资产、多少年历史、最多多少缺失比例？",
}


def _set_slot(brief: ResearchBrief, name: str, value: object | None, lock: bool | None) -> ResearchBrief:
    current = getattr(brief, name)
    next_slot = Slot(
        current.value if value is None else value,
        current.locked if lock is None else lock,
    )
    return replace(brief, **{name: next_slot})


def apply_intent(research: Research, intent: Intent, now: datetime) -> Research:
    if intent.kind is IntentKind.OFF_TOPIC:
        return research
    brief = research.brief
    for name, value in intent.updates:
        brief = _set_slot(brief, name, value, None)
    for name in intent.locks:
        if getattr(brief, name).value is not None:
            brief = _set_slot(brief, name, None, True)
    for name in intent.unlocks:
        brief = _set_slot(brief, name, None, False)
    return replace(research, brief=brief, updated_at=now)


def next_question(research: Research) -> DialoguePrompt:
    if all_slots_locked(research.brief):
        return DialoguePrompt(None, "五项研究设定已锁定，请检查确认开跑卡。")
    for name in SlotName:
        slot = getattr(research.brief, name.value)
        if slot.value is None or not slot.locked:
            return DialoguePrompt(name, QUESTIONS[name])
    raise AssertionError("unreachable slot state")
