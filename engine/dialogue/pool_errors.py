from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from engine.dialogue.slots import unlock_slot
from engine.dialogue.turns import append_dialogue
from engine.research.data_availability import TRANSIENT_DATA_CODE
from engine.research.models import DialogueRole, Research
from engine.research.user_errors import UserFacingError


def _append_user_error(research: Research, error: UserFacingError, now: datetime) -> Research:
    return append_dialogue(
        research,
        DialogueRole.ASSISTANT,
        error.message,
        now,
        error_code=error.code,
        error_params=error.params,
        error_detail=error.detail,
    )


def reopen_after_pool_failure(
    research: Research,
    error: UserFacingError,
    now: datetime,
) -> Research:
    """Put pool resolution failures back into the chat instead of a dead-end confirm card."""
    if error.code == TRANSIENT_DATA_CODE:
        return _append_user_error(research, error, now)
    updated = unlock_slot(research, "universe", now)
    return append_dialogue(updated, DialogueRole.ASSISTANT, error.message, now)


def record_transient_confirm_notice(
    research: Research,
    error: UserFacingError,
    now: datetime,
) -> Research:
    """Keep locked slots; only surface retry copy for confirm-time data outages."""
    message = error.message if error.code in error.message else f"{error.message}（{error.code}）"
    coded = UserFacingError(error.code, message, params=error.params, detail=error.detail)
    return _append_user_error(research, coded, now)
