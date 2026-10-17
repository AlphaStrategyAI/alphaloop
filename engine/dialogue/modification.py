from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from engine.dialogue.intent import Intent, IntentKind, interpret
from engine.dialogue.prompts import SlotName
from engine.dialogue.slots import apply_intent
from engine.dialogue.turns import append_dialogue
from engine.research.models import DialogueRole, Research, ResearchBrief

PENDING_MODIFY_REPLY = "已记下修改，点「确认修改并开新版」后才会开新版本。"


def interpret_modification(message: str, research: Research) -> Intent:
    """Parse a settings change on paused/completed research (any slot)."""
    updates: list[tuple[str, object]] = []
    for slot in SlotName:
        partial = interpret(message, research, slot)
        if partial.kind is IntentKind.PROVIDE:
            updates.extend(partial.updates)
    seen: set[str] = set()
    unique: list[tuple[str, object]] = []
    for name, value in updates:
        if name in seen:
            continue
        seen.add(name)
        unique.append((name, value))
    if unique:
        return Intent(IntentKind.PROVIDE, tuple(unique))
    return Intent(
        IntentKind.OFF_TOPIC,
        response="没能识别要改哪项设定。例如：把最长研究时间改成 6 小时。",
    )


def process_modification_dialogue(research: Research, message: str, now: datetime) -> Research:
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    intent = interpret_modification(text, research)
    with_user = append_dialogue(research, DialogueRole.USER, text, now)
    updated = apply_intent(with_user, intent, now)
    reply = (
        intent.response
        if intent.kind is IntentKind.OFF_TOPIC
        else PENDING_MODIFY_REPLY
    )
    return append_dialogue(updated, DialogueRole.ASSISTANT, reply, now)


def finalize_modification_confirm_dialogue(research: Research, now: datetime) -> Research:
    dialogue = research.dialogue
    if (
        dialogue
        and dialogue[-1].role is DialogueRole.ASSISTANT
        and PENDING_MODIFY_REPLY in dialogue[-1].text
    ):
        dialogue = dialogue[:-1]
    version = research.current_version_number or 1
    research = replace(research, dialogue=dialogue)
    return append_dialogue(
        research,
        DialogueRole.ASSISTANT,
        f"已开始第 {version} 版。",
        now,
    )


def brief_differs_from_latest_version(research: Research) -> bool:
    if not research.versions:
        return True
    snapshot: ResearchBrief = research.versions[-1].brief_snapshot
    return research.brief != snapshot
