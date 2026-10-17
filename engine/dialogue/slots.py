from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from engine.dialogue.intent import Intent, IntentKind
from engine.dialogue.prompts import QUESTIONS, SlotName
from engine.research.models import Research, ResearchBrief, Slot
from engine.research.state_machine import all_slots_locked


@dataclass(frozen=True, slots=True)
class DialoguePrompt:
    slot: SlotName | None
    message: str


_MISSING = object()


def _set_slot(
    brief: ResearchBrief,
    name: str,
    value: object | None = _MISSING,
    lock: bool | None = None,
) -> ResearchBrief:
    current = getattr(brief, name)
    next_slot = Slot(
        current.value if value is _MISSING else value,
        current.locked if lock is None else lock,
    )
    return replace(brief, **{name: next_slot})


def first_open_slot(brief: ResearchBrief) -> SlotName | None:
    for name in SlotName:
        if getattr(brief, name.value).value is None:
            return name
    return None


def apply_intent(research: Research, intent: Intent, now: datetime) -> Research:
    if intent.kind is IntentKind.OFF_TOPIC:
        return research
    brief = research.brief
    for name, value in intent.updates:
        brief = _set_slot(brief, name, value, False)
    for name in intent.unlocks:
        brief = _set_slot(brief, name, None, False)
    return replace(research, brief=brief, updated_at=now)


def next_question(research: Research) -> DialoguePrompt:
    if all_slots_locked(research.brief):
        return DialoguePrompt(None, "五项研究设定已齐全，请检查确认开跑卡。")
    open_slot = first_open_slot(research.brief)
    if open_slot is None:
        return DialoguePrompt(None, "五项研究设定已齐全，请检查确认开跑卡。")
    return DialoguePrompt(open_slot, QUESTIONS[open_slot])


def unlock_all_slots(research: Research, now: datetime) -> Research:
    if research.status.value != "draft":
        raise ValueError("unlock_brief is only valid while research is still in draft")
    brief = research.brief
    for name in SlotName:
        brief = _set_slot(brief, name.value, None, False)
    return replace(research, brief=brief, updated_at=now)


def unlock_slot(research: Research, slot: str, now: datetime) -> Research:
    if research.status.value != "draft":
        raise ValueError("unlock_brief is only valid while research is still in draft")
    try:
        name = SlotName(slot)
    except ValueError:
        raise ValueError(f"unknown brief slot: {slot}") from None
    brief = research.brief
    brief = _set_slot(brief, name.value, None, False)
    return replace(research, brief=brief, updated_at=now)
