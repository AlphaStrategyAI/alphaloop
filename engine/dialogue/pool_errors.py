from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from engine.dialogue.slots import unlock_slot
from engine.dialogue.turns import append_dialogue
from engine.research.data_availability import TRANSIENT_DATA_CODE
from engine.research.models import DialogueRole, Research
from engine.research.user_errors import UserFacingError


def reopen_after_pool_failure(
    research: Research,
    error: UserFacingError,
    now: datetime,
) -> Research:
    """Put pool resolution failures back into the chat instead of a dead-end confirm card."""
    if error.code == TRANSIENT_DATA_CODE:
        return append_dialogue(research, DialogueRole.ASSISTANT, error.message, now)
    updated = unlock_slot(research, "universe", now)
    updated = append_dialogue(updated, DialogueRole.ASSISTANT, error.message, now)
    return updated


def record_transient_confirm_notice(
    research: Research,
    error: UserFacingError,
    now: datetime,
) -> Research:
    """Keep locked slots; only surface retry copy for confirm-time data outages."""
    text = error.message if error.code in error.message else f"{error.message}（{error.code}）"
    return append_dialogue(research, DialogueRole.ASSISTANT, text, now)
