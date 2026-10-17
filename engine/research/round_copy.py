"""Localize round change lines for the desktop workbench."""

from __future__ import annotations

from engine.research.display_names import format_model_token, localize_user_string

_MODEL_LINE_PREFIX = "模型变更："
_CHANGE_LINE_PREFIX = "变更："


def localize_model_changes(changes: tuple[str, ...] | list[str]) -> str:
    if not changes:
        return ""
    mapped = [format_model_token(item) for item in changes]
    return _MODEL_LINE_PREFIX + "、".join(mapped)


def localize_logic_change(description: str | None) -> str | None:
    if not description:
        return None
    return _CHANGE_LINE_PREFIX + localize_user_string(description)
