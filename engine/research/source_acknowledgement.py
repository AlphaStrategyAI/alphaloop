"""User-level acknowledgement that an unlicensed source is personal research only.

One timestamp per source, in the app settings file. Acknowledging Yahoo does
not acknowledge AkShare. Revoking removes the timestamp; a later use asks again.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

UNLICENSED_SOURCE_IDS = frozenset({"yahoo_daily", "akshare_sina_daily"})
_KEY = "unlicensedAcknowledgements"


def is_unlicensed_source(source_id: str) -> bool:
    return source_id in UNLICENSED_SOURCE_IDS


def _read(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _replace_settings(temporary: Path, path: Path) -> None:
    """Publish settings.json. Windows can deny the rename while a reader holds the file."""
    encoded = temporary.read_text(encoding="utf-8")
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 7:
                break
            time.sleep(0.02 * (attempt + 1))
    path.write_text(encoded, encoding="utf-8")


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, name = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
        _replace_settings(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def acknowledged_at(source_id: str, path: Path) -> str | None:
    raw = _read(path).get(_KEY)
    if not isinstance(raw, dict):
        return None
    value = raw.get(source_id)
    if isinstance(value, str) and value:
        return value
    return None


def record_acknowledgement(source_id: str, when: datetime, path: Path) -> str:
    if not is_unlicensed_source(source_id):
        raise ValueError(f"not an unlicensed source: {source_id}")
    payload = _read(path)
    current = payload.get(_KEY)
    stamps = dict(current) if isinstance(current, dict) else {}
    stamp = when.isoformat()
    stamps[source_id] = stamp
    payload[_KEY] = stamps
    _write(path, payload)
    return stamp


def revoke_acknowledgement(source_id: str, path: Path) -> None:
    payload = _read(path)
    current = payload.get(_KEY)
    if not isinstance(current, dict) or source_id not in current:
        return
    stamps = dict(current)
    stamps.pop(source_id, None)
    payload[_KEY] = stamps
    _write(path, payload)
