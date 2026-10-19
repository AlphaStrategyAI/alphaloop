"""Process-local secrets. Never written to disk, env, or logs by this module."""

from __future__ import annotations

import threading
import time

from engine.research.secret_redaction import clear_registered_secrets, register_secret

DESKTOP_REQUIRED_MESSAGE = "需要密钥才能继续。请从桌面应用启动。"
DESKTOP_REQUIRED_CODE = "SECRETS_REQUIRE_DESKTOP"
_SYNC_WAIT_SEC = 30.0

_lock = threading.Lock()
_secrets: dict[str, str] = {}
_owner = "cli"
_synced = False
_started = time.monotonic()


def configure_process_owner(owner: str) -> None:
    """``desktop`` waits briefly for the shell to push secrets. ``cli`` does not."""
    global _owner, _started, _synced
    with _lock:
        _owner = owner
        _started = time.monotonic()
        _synced = False
        _secrets.clear()
        clear_registered_secrets()


def install_secrets(mapping: dict[str, str]) -> tuple[str, ...]:
    """Replace the in-memory set. Marks the desktop push as received."""
    global _synced
    cleaned: dict[str, str] = {}
    for key, value in mapping.items():
        secret_id = str(key)
        secret = str(value)
        if secret_id and secret:
            cleaned[secret_id] = secret
    with _lock:
        _secrets.clear()
        clear_registered_secrets()
        for secret_id, secret in cleaned.items():
            _secrets[secret_id] = secret
            register_secret(secret)
        _synced = True
        return tuple(sorted(_secrets))


def peek_secret(secret_id: str) -> str | None:
    with _lock:
        return _secrets.get(secret_id)


def secret_gate(required: tuple[str, ...]) -> str:
    """``ok`` to run, ``wait`` while the desktop push is still in flight, else ``pause``."""
    if not required:
        return "ok"
    with _lock:
        missing = any(secret_id not in _secrets for secret_id in required)
        if not missing:
            return "ok"
        if _owner == "desktop" and not _synced and (time.monotonic() - _started) < _SYNC_WAIT_SEC:
            return "wait"
        return "pause"
