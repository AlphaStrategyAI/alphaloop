"""Localize round change lines for the desktop workbench."""

from __future__ import annotations

_MODEL_LINE_PREFIX = "模型变更："
_CHANGE_LINE_PREFIX = "变更："


def localize_model_changes(changes: tuple[str, ...] | list[str]) -> str:
    if not changes:
        return ""
    mapped = [_localize_token(item) for item in changes]
    return _MODEL_LINE_PREFIX + "、".join(mapped)


def localize_logic_change(description: str | None) -> str | None:
    if not description:
        return None
    return _CHANGE_LINE_PREFIX + _localize_token(description)


def _localize_token(text: str) -> str:
    replacements = (
        ("lookback_days", "回看天数"),
        ("model_family", "模型族"),
        ("signal_definition", "信号定义"),
        ("feature_set", "特征集"),
        ("PARAM", "参数"),
        ("MODEL", "模型"),
    )
    out = text
    for en, zh in replacements:
        out = out.replace(en, zh)
    return out
