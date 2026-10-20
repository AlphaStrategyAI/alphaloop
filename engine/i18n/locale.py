"""Resolve the interface language. Research records never store it."""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

_request_locale: ContextVar[str | None] = ContextVar(
    "alphaloop_request_locale",
    default=None,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ui_language_cases.json"
)


def language_from_system_locale(tag: str | None) -> str:
    """zh-* (including zh and zh_TW.UTF-8) is Chinese. Anything else, including missing, is English."""
    if tag is None:
        return "en"
    text = tag.strip()
    if not text:
        return "en"
    primary = text.split(".", 1)[0].split("@", 1)[0]
    lang = primary.replace("-", "_").split("_", 1)[0].lower()
    if lang == "zh":
        return "zh"
    return "en"


def normalize_preference(value: object) -> str:
    """Unknown or missing preferences follow the system. They are not a language."""
    if value in ("system", "zh", "en"):
        return str(value)
    return "system"


def resolve_ui_language(preference: object, system_locale: str | None) -> str:
    chosen = normalize_preference(preference)
    if chosen == "zh":
        return "zh"
    if chosen == "en":
        return "en"
    return language_from_system_locale(system_locale)


def normalize_request_locale(value: object) -> str | None:
    """Desktop sends the resolved language only. Tags and ``system`` do not stick."""
    if value in ("zh", "en"):
        return str(value)
    return None


def push_request_locale(locale: str | None) -> Token[str | None]:
    return _request_locale.set(locale)


def reset_request_locale(token: Token[str | None]) -> None:
    _request_locale.reset(token)


def get_request_locale() -> str | None:
    return _request_locale.get()


def load_ui_language_cases() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
