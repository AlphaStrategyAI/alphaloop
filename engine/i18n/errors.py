"""Error-code envelope. The desktop localizes ``code`` + ``params``.

``error`` stays the legacy sentence so existing clients and stored run errors do not
change. ``detail`` is raw technical text, untranslated. B1-sec replaces the redactor;
I0 only reserves the hook and calls it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from engine.i18n.conventions import error_code_catalog

TechnicalDetailRedactor = Callable[[str], str]


def identity_redactor(text: str) -> str:
    return text


_redactor: TechnicalDetailRedactor = identity_redactor


def set_technical_detail_redactor(redactor: TechnicalDetailRedactor) -> TechnicalDetailRedactor:
    """Install a redactor. Returns the previous one so callers can restore it."""
    global _redactor
    previous = _redactor
    _redactor = redactor
    return previous


def redact_technical_detail(text: str) -> str:
    return _redactor(text)


def build_error_envelope(
    *,
    code: str,
    message: str,
    params: Mapping[str, Any] | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    safe_params = dict(params or {})
    safe_detail: str | None
    if detail is None or detail == "":
        safe_detail = None
    else:
        safe_detail = redact_technical_detail(detail)
    return {
        "error": message,
        "code": code,
        "params": safe_params,
        "detail": safe_detail,
    }


def contact_email_missing_envelope(
    sources: str,
    *,
    detail: str | None = None,
) -> dict[str, Any]:
    """Example parameterized code from settings §2.6.2. Not raised until that path lands."""
    spec = error_code_catalog()["contact_email_missing"]
    if tuple(spec.get("params", ())) != ("sources",):
        raise RuntimeError("contact_email_missing params drifted from the contract")
    legacy = str(error_code_catalog()["contact_email_missing"]["legacyZh"])
    return build_error_envelope(
        code="contact_email_missing",
        message=legacy,
        params={"sources": sources},
        detail=detail,
    )
