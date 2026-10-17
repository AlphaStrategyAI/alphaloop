from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from engine.dialogue.slots import unlock_slot
from engine.dialogue.turns import append_dialogue
from engine.research.models import DialogueRole, Research
from engine.research.user_errors import UserFacingError


def reopen_after_pool_failure(
    research: Research,
    error: UserFacingError,
    now: datetime,
) -> Research:
    """Put pool resolution failures back into the chat instead of a dead-end confirm card."""
    updated = unlock_slot(research, "universe", now)
    updated = append_dialogue(updated, DialogueRole.ASSISTANT, error.message, now)
    return updated
