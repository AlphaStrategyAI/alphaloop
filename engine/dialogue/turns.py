from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from engine.dialogue.intent import Intent, IntentKind, interpret
from engine.dialogue.prompts import SlotName
from engine.dialogue.slots import apply_intent, next_question
from engine.research.coverage_parse import parse_coverage_parts
from engine.i18n.errors import redact_technical_detail
from engine.research.models import CoverageFloor, DialogueRole, DialogueTurn, Research, ResearchStatus
from engine.research.thesis_scope import (
    MEAN_REVERSION_ONLY_NOTICE,
    is_mean_reversion_ack,
    thesis_is_non_mean_reversion,
)


def append_dialogue(
    research: Research,
    role: DialogueRole,
    text: str,
    now: datetime,
    *,
    error_code: str | None = None,
    error_params: dict[str, Any] | None = None,
    error_detail: str | None = None,
) -> Research:
    turn = DialogueTurn(
        role=role,
        text=text,
        error_code=error_code,
        error_params=dict(error_params) if error_params else None,
        error_detail=error_detail,
    )
    return replace(
        research,
        dialogue=research.dialogue + (turn,),
        updated_at=now,
    )


def dialogue_turn_view(turn: DialogueTurn) -> dict[str, Any]:
    """View payload. A coded error is localized by the desktop, so the legacy sentence stays out of `text`."""
    if not turn.error_code:
        return {"role": turn.role.value, "text": turn.text}
    payload: dict[str, Any] = {
        "role": turn.role.value,
        "text": "",
        "errorCode": turn.error_code,
        "errorParams": dict(turn.error_params or {}),
    }
    if turn.error_detail:
        payload["errorDetail"] = redact_technical_detail(turn.error_detail)
    return payload


def _apply_coverage_scratch(
    research: Research,
    message: str,
    active_slot: SlotName | None,
) -> Research:
    if research.brief.coverage_floor.value is not None:
        return research
    assets, years, missing = parse_coverage_parts(message)
    min_assets = assets if assets is not None else research.coverage_min_assets_scratch
    min_years = years if years is not None else research.coverage_min_years_scratch
    max_missing = (
        missing if missing is not None else research.coverage_max_missing_pct_scratch
    )
    if min_assets is None and min_years is None and max_missing is None:
        return research
    if min_assets is not None and min_years is not None and max_missing is not None:
        floor = CoverageFloor(
            min_assets=min_assets,
            min_years=min_years,
            max_missing_pct=max_missing,
        )
        from engine.research.models import Slot

        brief = replace(research.brief, coverage_floor=Slot(floor, True))
        return replace(
            research,
            brief=brief,
            coverage_min_assets_scratch=None,
            coverage_min_years_scratch=None,
            coverage_max_missing_pct_scratch=None,
        )
    return replace(
        research,
        coverage_min_assets_scratch=min_assets,
        coverage_min_years_scratch=min_years,
        coverage_max_missing_pct_scratch=max_missing,
    )


def process_send_dialogue(research: Research, message: str, now: datetime) -> Research:
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if research.status is not ResearchStatus.DRAFT:
        from engine.dialogue.modification import process_modification_dialogue

        return process_modification_dialogue(research, text, now)
    if research.pending_non_mr_thesis and is_mean_reversion_ack(text):
        intent = Intent(IntentKind.PROVIDE, (("thesis", research.pending_non_mr_thesis),))
        with_user = append_dialogue(research, DialogueRole.USER, text, now)
        updated = apply_intent(with_user, intent, now)
        updated = replace(updated, pending_non_mr_thesis=None)
        return append_dialogue(updated, DialogueRole.ASSISTANT, next_question(updated).message, now)
    prompt = next_question(research)
    intent = interpret(text, research, prompt.slot)
    held_thesis: str | None = None
    if intent.kind is IntentKind.PROVIDE:
        kept: list[tuple[str, object]] = []
        for name, value in intent.updates:
            if (
                name == "thesis"
                and isinstance(value, str)
                and thesis_is_non_mean_reversion(value)
            ):
                held_thesis = value
                continue
            kept.append((name, value))
        if held_thesis is not None:
            intent = (
                Intent(IntentKind.PROVIDE, tuple(kept))
                if kept
                else Intent(IntentKind.OFF_TOPIC, response=MEAN_REVERSION_ONLY_NOTICE)
            )
    with_user = append_dialogue(research, DialogueRole.USER, text, now)
    updated = apply_intent(with_user, intent, now)
    updated = _apply_coverage_scratch(updated, text, prompt.slot)
    if held_thesis is not None:
        updated = replace(updated, pending_non_mr_thesis=held_thesis)
    elif any(name == "thesis" for name, _value in intent.updates):
        updated = replace(updated, pending_non_mr_thesis=None)
    if held_thesis is not None:
        return append_dialogue(updated, DialogueRole.ASSISTANT, MEAN_REVERSION_ONLY_NOTICE, now)
    if intent.kind is IntentKind.OFF_TOPIC:
        reply = intent.response or prompt.message
        if research.dialogue and research.dialogue[-1].text == reply:
            reply = f"没能理解你的意思。{reply}"
    else:
        reply = next_question(updated).message
    last_assistant = next(
        (turn.text for turn in reversed(updated.dialogue) if turn.role is DialogueRole.ASSISTANT),
        None,
    )
    if reply == last_assistant and intent.kind is IntentKind.OFF_TOPIC:
        reply = f"没能理解你的意思。{reply}"
    return append_dialogue(updated, DialogueRole.ASSISTANT, reply, now)
