from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


def contracts_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "contracts"
    return Path(__file__).resolve().parents[2] / "contracts"


@lru_cache(maxsize=1)
def conventions() -> dict[str, Any]:
    return json.loads(
        (contracts_dir() / "i18n-conventions.json").read_text(encoding="utf-8")
    )


def placeholder_marker() -> str:
    return str(conventions()["placeholderMarker"])


def settings_file_name() -> str:
    return str(conventions()["settingsFileName"])


def settings_key() -> str:
    return str(conventions()["settingsKey"])


@lru_cache(maxsize=1)
def error_code_catalog() -> dict[str, dict[str, Any]]:
    payload = json.loads(
        (contracts_dir() / "error-codes.json").read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise TypeError("error-codes.json must be an object")
    return payload
