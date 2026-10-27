from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from engine.dialogue.intent import APOLOGY_PREFIX, Intent, IntentKind, interpret
from engine.dialogue.prompts import SlotName
from engine.dialogue.slots import apply_intent, next_question
from engine.i18n.errors import redact_technical_detail
from engine.research.a1_copy import MOMENTUM_UNSUPPORTED_NOTICE
from engine.research.coverage_parse import parse_coverage_parts
from engine.research.family_choice import show_ack, show_chips
from engine.research.family_intent import classify_thesis
from engine.research.models import (
    CoverageFloor,
    DialogueRole,
    DialogueTurn,
    Research,
    ResearchStatus,
)
from engine.research.thesis_scope import (
    FAMILY_FOLLOWUP,
    MEAN_REVERSION_DECLINE_NOTICE,
    MEAN_REVERSION_ONLY_NOTICE,
    explicit_family_choice,
    family_repick_notice,
    is_mean_reversion_ack,
    is_mean_reversion_decline,
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
    max_missing = missing if missing is not None else research.coverage_max_missing_pct_scratch
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


def _apology_once(reply: str) -> str:
    """A repeated failed turn says it once. The slot reply may already include it."""
    if reply.startswith(APOLOGY_PREFIX):
        return reply
    return f"{APOLOGY_PREFIX}{reply}"


def _reask(research: Research) -> str:
    if research.pending_non_mr_thesis or (
        not (research.brief.thesis.value or "") and show_chips(research)
    ):
        return FAMILY_FOLLOWUP
    if classify_thesis(str(research.brief.thesis.value or "")).outcome == "block":
        return MOMENTUM_UNSUPPORTED_NOTICE
    if research.mean_reversion_declined:
        return MEAN_REVERSION_DECLINE_NOTICE
    return MEAN_REVERSION_ONLY_NOTICE


def _apply_family_repick(research: Research, text: str, choice, now: datetime) -> Research:
    """A button and the same typed family name share this path. The original thesis stays."""
    with_user = append_dialogue(research, DialogueRole.USER, text, now)
    updated = with_user
    pending = research.pending_non_mr_thesis
    if pending and not (research.brief.thesis.value or ""):
        updated = apply_intent(
            updated,
            Intent(IntentKind.PROVIDE, (("thesis", pending),)),
            now,
        )
    updated = replace(
        updated,
        repicked_family=choice.family_id,
        mean_reversion_adopted=choice.outcome == "run",
        mean_reversion_declined=False,
        pending_non_mr_thesis=None,
    )
    return append_dialogue(
        updated, DialogueRole.ASSISTANT, family_repick_notice(choice.family_id), now
    )


def process_send_dialogue(research: Research, message: str, now: datetime) -> Research:
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if research.status is not ResearchStatus.DRAFT:
        from engine.dialogue.modification import process_modification_dialogue

        return process_modification_dialogue(research, text, now)
    if is_mean_reversion_decline(text) and show_ack(research):
        with_user = append_dialogue(research, DialogueRole.USER, text, now)
        updated = replace(with_user, mean_reversion_declined=True)
        return append_dialogue(updated, DialogueRole.ASSISTANT, MEAN_REVERSION_DECLINE_NOTICE, now)
    thesis_now = research.brief.thesis.value if isinstance(research.brief.thesis.value, str) else ""
    pending = research.pending_non_mr_thesis or ""
    current_hit = classify_thesis(pending or thesis_now)
    if is_mean_reversion_ack(text) and (pending or thesis_now):
        with_user = append_dialogue(research, DialogueRole.USER, text, now)
        # Momentum, trend, and breakout never treat a yes as adoption.
        if current_hit.outcome == "block" and not research.repicked_family:
            return append_dialogue(
                with_user, DialogueRole.ASSISTANT, MOMENTUM_UNSUPPORTED_NOTICE, now
            )
        if research.repicked_family and research.repicked_family != "mean_reversion":
            updated = replace(
                with_user,
                mean_reversion_adopted=True,
                mean_reversion_declined=False,
                pending_non_mr_thesis=None,
            )
            return append_dialogue(
                updated, DialogueRole.ASSISTANT, next_question(updated).message, now
            )
        if current_hit.outcome == "disclose" or (
            pending and classify_thesis(pending).outcome == "disclose"
        ):
            if pending:
                updated = apply_intent(
                    with_user,
                    Intent(IntentKind.PROVIDE, (("thesis", pending),)),
                    now,
                )
            else:
                updated = with_user
            updated = replace(
                updated,
                pending_non_mr_thesis=None,
                mean_reversion_adopted=True,
                mean_reversion_declined=False,
            )
            return append_dialogue(
                updated, DialogueRole.ASSISTANT, next_question(updated).message, now
            )
    if show_ack(research) or show_chips(research):
        choice = explicit_family_choice(text)
        if choice is not None:
            return _apply_family_repick(research, text, choice, now)
    prompt = next_question(research)
    intent = interpret(text, research, prompt.slot)
    unrecognized_thesis: str | None = None
    if intent.kind is IntentKind.PROVIDE:
        kept: list[tuple[str, object]] = []
        for name, value in intent.updates:
            # An unrecognized thesis is not stored as mean reversion. Ask which family.
            if (
                name == "thesis"
                and isinstance(value, str)
                and classify_thesis(value).outcome == "none"
            ):
                unrecognized_thesis = value
                continue
            kept.append((name, value))
        if unrecognized_thesis is not None:
            kept = [item for item in kept if item[0] != "universe"]
            intent = (
                Intent(IntentKind.PROVIDE, tuple(kept))
                if kept
                else Intent(IntentKind.OFF_TOPIC, response=FAMILY_FOLLOWUP)
            )
    protect_thesis = show_ack(research) or show_chips(research)
    if protect_thesis and intent.kind is IntentKind.PROVIDE:
        kept_updates = tuple(item for item in intent.updates if item[0] != "thesis")
        if not kept_updates:
            with_user = append_dialogue(research, DialogueRole.USER, text, now)
            return append_dialogue(with_user, DialogueRole.ASSISTANT, _reask(research), now)
        intent = Intent(IntentKind.PROVIDE, kept_updates)
    with_user = append_dialogue(research, DialogueRole.USER, text, now)
    updated = apply_intent(with_user, intent, now)
    updated = _apply_coverage_scratch(updated, text, prompt.slot)
    if unrecognized_thesis is not None:
        updated = replace(updated, pending_non_mr_thesis=unrecognized_thesis)
        return append_dialogue(updated, DialogueRole.ASSISTANT, FAMILY_FOLLOWUP, now)
    if any(name == "thesis" for name, _value in intent.updates):
        updated = replace(updated, pending_non_mr_thesis=None)
    if intent.kind is IntentKind.OFF_TOPIC:
        reply = intent.response or prompt.message
        if research.dialogue and research.dialogue[-1].text == reply:
            reply = _apology_once(reply)
    else:
        reply = next_question(updated).message
    last_assistant = next(
        (turn.text for turn in reversed(updated.dialogue) if turn.role is DialogueRole.ASSISTANT),
        None,
    )
    if reply == last_assistant and intent.kind is IntentKind.OFF_TOPIC:
        reply = _apology_once(reply)
    return append_dialogue(updated, DialogueRole.ASSISTANT, reply, now)
