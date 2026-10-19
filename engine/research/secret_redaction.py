"""Strip secrets from text that can leave the process.

The builtin redactor always runs. ``set_text_redactor`` adds another pass so a
later i18n envelope can wrap this without becoming the only filter. I0's
``set_technical_detail_redactor`` is not on main yet; call ``redact_text`` from
that hook when it lands.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from urllib.parse import urlsplit, urlunsplit

_MIN_SECRET_LEN = 8
_REDACTED = "«redacted»"
_URL = re.compile(r"(?i)\b(?:https?|wss?)://[^\s<>\"']+")
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_TOKEN_SEGMENT = re.compile(
    r"(?i)^(?:sk|ghp|github_pat|xox[baprs]|AKIA|ya29)[A-Za-z0-9_\-]{8,}$"
    r"|^(?:[A-Za-z0-9+/]{24,}={0,2}|[A-Fa-f0-9]{32,}|[A-Za-z0-9_\-]{32,})$"
)

_lock = threading.Lock()
_known: set[str] = set()
_extra: Callable[[str], str] | None = None


def register_secret(value: str) -> None:
    """Remember a secret for exact replacement. Values shorter than 8 are ignored."""
    if isinstance(value, str) and len(value) >= _MIN_SECRET_LEN:
        with _lock:
            _known.add(value)


def clear_registered_secrets() -> None:
    with _lock:
        _known.clear()


def set_text_redactor(redactor: Callable[[str], str] | None) -> None:
    """Install an extra pass. The builtin exact-and-URL redactor still runs first."""
    global _extra
    _extra = redactor


def known_secrets() -> tuple[str, ...]:
    with _lock:
        return tuple(sorted(_known, key=len, reverse=True))


def redact_text(text: str) -> str:
    if not text:
        return text
    out = text
    for secret in known_secrets():
        out = out.replace(secret, _REDACTED)
    out = _URL.sub(lambda match: _redact_url(match.group(0)), out)
    extra = _extra
    if extra is not None:
        out = extra(out)
    return out


def redact_filename(name: str) -> str:
    """Drop secret-shaped path segments from a single file or directory name."""
    cleaned = redact_text(name)
    if _looks_like_token(cleaned):
        return _REDACTED
    return cleaned


def _looks_like_token(segment: str) -> bool:
    if not segment or _UUID.fullmatch(segment):
        return False
    return _TOKEN_SEGMENT.fullmatch(segment) is not None


def _redact_url(raw: str) -> str:
    tail = ""
    while raw and raw[-1] in ".,);":
        tail = raw[-1] + tail
        raw = raw[:-1]
    try:
        parts = urlsplit(raw)
    except ValueError:
        return _REDACTED + tail
    netloc = parts.netloc
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]
    segments = []
    for segment in parts.path.split("/"):
        segments.append(_REDACTED if _looks_like_token(segment) else segment)
    path = "/".join(segments)
    if parts.path.startswith("/") and not path.startswith("/"):
        path = "/" + path
    return urlunsplit((parts.scheme, netloc, path, "", "")) + tail


class RedactingLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        if record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        return True


def install_redacting_log_filter() -> None:
    """Redact every logger, not only the root logger's own records."""
    if getattr(logging.Logger.handle, "_alphaloop_redacting", False):
        return
    original = logging.Logger.handle

    def handle(self: logging.Logger, record: logging.LogRecord) -> None:
        RedactingLogFilter().filter(record)
        original(self, record)

    handle._alphaloop_redacting = True  # type: ignore[attr-defined]
    logging.Logger.handle = handle  # type: ignore[method-assign]
