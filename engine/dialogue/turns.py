from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from engine.dialogue.intent import Intent, IntentKind, interpret
from engine.dialogue.slots import apply_intent, next_question
from engine.research.models import DialogueRole, DialogueTurn, Research, ResearchStatus


def append_dialogue(
    research: Research,
    role: DialogueRole,
    text: str,
    now: datetime,
) -> Research:
    turn = DialogueTurn(role=role, text=text)
    return replace(
        research,
        dialogue=research.dialogue + (turn,),
        updated_at=now,
    )


def process_send_dialogue(research: Research, message: str, now: datetime) -> Research:
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if research.status is not ResearchStatus.DRAFT:
        from engine.dialogue.modification import process_modification_dialogue

        return process_modification_dialogue(research, text, now)
    prompt = next_question(research)
    intent = interpret(text, research, prompt.slot)
    with_user = append_dialogue(research, DialogueRole.USER, text, now)
    updated = apply_intent(with_user, intent, now)
    if intent.kind is IntentKind.OFF_TOPIC:
        reply = intent.response or prompt.message
    else:
        reply = next_question(updated).message
    return append_dialogue(updated, DialogueRole.ASSISTANT, reply, now)
