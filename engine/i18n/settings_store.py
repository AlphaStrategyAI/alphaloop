"""App settings file in the data directory. Not the research library, not the keychain.

Writers must keep keys they do not own. ``uiLanguage`` is the I0 field.
Missing file, missing key, unknown value, or corrupt JSON all read as ``system``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from engine.i18n.conventions import settings_file_name, settings_key
from engine.i18n.locale import normalize_preference
from engine.research.data_paths import resolve_data_root


def settings_path(root: Path | None = None) -> Path:
    base = root if root is not None else resolve_data_root(ensure_exists=False)
    return base / settings_file_name()


def read_ui_language_preference(path: Path | None = None) -> str:
    target = path if path is not None else settings_path()
    if not target.is_file():
        return "system"
    try:
        loaded = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return "system"
    if not isinstance(loaded, dict):
        return "system"
    return normalize_preference(loaded.get(settings_key()))


def write_ui_language_preference(preference: str, path: Path | None = None) -> str:
    chosen = normalize_preference(preference)
    if preference not in ("system", "zh", "en"):
        raise ValueError("uiLanguage must be system, zh, or en")
    target = path if path is not None else settings_path()
    current: dict[str, object] = {}
    if target.is_file():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            loaded = None
        if isinstance(loaded, dict):
            current = loaded
    current[settings_key()] = chosen
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return chosen
