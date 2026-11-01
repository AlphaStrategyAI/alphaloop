"""LLM endpoint stored in settings.json. The API key never is.

The desktop writes ``llmBaseUrl``, ``llmModel``, and ``llmPrivacyAcknowledged``.
The API key lives in the secret vault under ``llm-api-key`` and is pushed into
this process by ``install_secrets``. Environment variables still override the
file so an existing reviewer setup keeps working.

Draft and other new purposes also require a consent record bound to the
effective scheme, host, port, and purpose version. An environment override that
moves the origin does not keep the previous consent.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

BASE_URL_KEY = "llmBaseUrl"
MODEL_KEY = "llmModel"
PRIVACY_KEY = "llmPrivacyAcknowledged"
CONSENT_SCHEME_KEY = "llmConsentScheme"
CONSENT_HOST_KEY = "llmConsentHost"
CONSENT_PORT_KEY = "llmConsentPort"
CONSENT_VERSION_KEY = "llmConsentPurposeVersion"
CONSENT_PURPOSES_KEY = "llmConsentPurposes"
SECRET_ID = "llm-api-key"
LLM_PURPOSE_VERSION = "2026-11-01"
LLM_PURPOSES = (
    "draft",
    "candidate_suggestion",
    "literature_summary",
    "review_note",
)
DRAFT_TIMEOUT_SECONDS = 12.0
_CONSENT_KEYS = (
    CONSENT_SCHEME_KEY,
    CONSENT_HOST_KEY,
    CONSENT_PORT_KEY,
    CONSENT_VERSION_KEY,
    CONSENT_PURPOSES_KEY,
)
# A previous draft must not be able to leave a key in the settings file.
_SECRET_FILE_KEYS = ("llmApiKey", "apiKey", "api_key", "ALPHALOOP_LLM_API_KEY")


@dataclass(frozen=True, slots=True)
class LlmSettings:
    base_url: str = ""
    model: str = ""
    privacy_acknowledged: bool = False


@dataclass(frozen=True, slots=True)
class LlmEndpoint:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True, slots=True)
class EndpointOrigin:
    scheme: str
    host: str
    port: int


@dataclass(frozen=True, slots=True)
class LlmConsent:
    scheme: str
    host: str
    port: int
    purpose_version: str
    purposes: tuple[str, ...]


class LlmCallError(Exception):
    """The draft call did not return a usable body. Callers fall back."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def endpoint_origin(url: str) -> EndpointOrigin | None:
    """Scheme, host, and port. The default port is 80 or 443 when omitted."""
    parsed = urlsplit((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return EndpointOrigin(parsed.scheme, parsed.hostname.lower(), int(port))


def is_loopback_base_url(url: str) -> bool:
    """True only for localhost, 127.0.0.0/8, and ::1. A LAN address is not local."""
    parsed = urlsplit((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "::1"}:
        return True
    parts = host.split(".")
    if len(parts) != 4:
        return False
    numbers: list[int] = []
    for part in parts:
        if not part.isdigit():
            return False
        number = int(part)
        if number > 255:
            return False
        numbers.append(number)
    return numbers[0] == 127


def _read_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def read_llm_settings(path: Path) -> LlmSettings:
    loaded = _read_object(path)
    base_url = loaded.get(BASE_URL_KEY)
    model = loaded.get(MODEL_KEY)
    privacy = loaded.get(PRIVACY_KEY)
    return LlmSettings(
        base_url=base_url.strip() if isinstance(base_url, str) else "",
        model=model.strip() if isinstance(model, str) else "",
        privacy_acknowledged=privacy is True,
    )


def _clean_base_url(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("base url is required")
    if len(text) > 500:
        raise ValueError("base url is too long")
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base url must be an http(s) address")
    if parsed.username or parsed.password or parsed.query:
        raise ValueError("base url must not carry a secret or a query")
    return text


def _clean_model(value: str) -> str:
    text = value.strip()
    if not text or len(text) > 200 or any(ch in text for ch in "\r\n"):
        raise ValueError("model name is required")
    return text


def _read_consent(loaded: Mapping[str, object]) -> LlmConsent | None:
    scheme = loaded.get(CONSENT_SCHEME_KEY)
    host = loaded.get(CONSENT_HOST_KEY)
    port = loaded.get(CONSENT_PORT_KEY)
    version = loaded.get(CONSENT_VERSION_KEY)
    purposes = loaded.get(CONSENT_PURPOSES_KEY)
    if not isinstance(scheme, str) or scheme not in {"http", "https"}:
        return None
    if not isinstance(host, str) or not host.strip():
        return None
    if isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536:
        return None
    if not isinstance(version, str):
        return None
    if not isinstance(purposes, list) or not all(isinstance(item, str) for item in purposes):
        return None
    return LlmConsent(scheme, host.strip().lower(), port, version, tuple(purposes))


def read_llm_consent(path: Path) -> LlmConsent | None:
    return _read_consent(_read_object(path))


def _consent_matches(consent: LlmConsent, base_url: str) -> bool:
    origin = endpoint_origin(base_url)
    if origin is None:
        return False
    return (
        consent.scheme == origin.scheme
        and consent.host == origin.host
        and consent.port == origin.port
    )


def write_llm_settings(
    path: Path,
    *,
    base_url: str,
    model: str,
    privacy_acknowledged: bool,
    purposes: tuple[str, ...] | None = None,
    purpose_version: str | None = None,
) -> LlmSettings:
    """Write the three non-secret fields. Other settings keys stay. Key fields go."""
    chosen = LlmSettings(
        base_url=_clean_base_url(base_url),
        model=_clean_model(model),
        privacy_acknowledged=bool(privacy_acknowledged),
    )
    current = _read_object(path)
    for secret_key in _SECRET_FILE_KEYS:
        current.pop(secret_key, None)
    current[BASE_URL_KEY] = chosen.base_url
    current[MODEL_KEY] = chosen.model
    current[PRIVACY_KEY] = chosen.privacy_acknowledged
    if not chosen.privacy_acknowledged:
        for key in _CONSENT_KEYS:
            current.pop(key, None)
    elif purposes is not None or purpose_version is not None:
        origin = endpoint_origin(chosen.base_url)
        if origin is None:
            raise ValueError("base url must be an http(s) address")
        cleaned: list[str] = []
        for item in purposes or ():
            if item not in LLM_PURPOSES:
                raise ValueError("unknown llm purpose")
            if item not in cleaned:
                cleaned.append(item)
        current[CONSENT_SCHEME_KEY] = origin.scheme
        current[CONSENT_HOST_KEY] = origin.host
        current[CONSENT_PORT_KEY] = origin.port
        current[CONSENT_VERSION_KEY] = purpose_version or LLM_PURPOSE_VERSION
        current[CONSENT_PURPOSES_KEY] = cleaned
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return chosen


def resolve_llm(
    settings_path: Path,
    environ: Mapping[str, str] | None = None,
) -> LlmEndpoint | None:
    """The endpoint to call, or None when the reviewer must stay fail-closed.

    Environment variables win. A file-based endpoint is used only after the
    privacy acknowledgement. A remote host needs a key. A loopback host may omit it.
    """
    from engine.research.secret_memory import peek_secret

    env = os.environ if environ is None else environ
    env_base = (env.get("ALPHALOOP_LLM_BASE_URL") or "").strip()
    env_model = (env.get("ALPHALOOP_LLM_MODEL") or "").strip()
    env_key = env.get("ALPHALOOP_LLM_API_KEY") or ""
    stored = read_llm_settings(settings_path)
    base_url = env_base or stored.base_url
    model = env_model or stored.model
    if not base_url or not model:
        return None
    file_supplies_endpoint = not env_base or not env_model
    if file_supplies_endpoint and not stored.privacy_acknowledged:
        return None
    api_key = env_key if env_key else (peek_secret(SECRET_ID) or "")
    if not api_key and not is_loopback_base_url(base_url):
        return None
    consent = _read_consent(_read_object(settings_path))
    if consent is not None and not _consent_matches(consent, base_url):
        return None
    return LlmEndpoint(base_url=base_url, api_key=api_key, model=model)


def resolve_llm_for_purpose(
    settings_path: Path,
    purpose: str,
    environ: Mapping[str, str] | None = None,
) -> LlmEndpoint | None:
    """Endpoint for one disclosed purpose.

    Legacy ``resolve_llm`` still serves an unscoped reviewer when no consent
    record exists. A new purpose needs the current purpose version and an
    origin that matches the effective URL, including an environment override.
    """
    if purpose not in LLM_PURPOSES:
        return None
    endpoint = resolve_llm(settings_path, environ)
    if endpoint is None:
        return None
    consent = read_llm_consent(settings_path)
    if consent is None:
        return None
    if consent.purpose_version != LLM_PURPOSE_VERSION:
        return None
    if purpose not in consent.purposes:
        return None
    if not _consent_matches(consent, endpoint.base_url):
        return None
    return endpoint


def post_llm_draft(
    endpoint: LlmEndpoint,
    messages: list[dict[str, object]],
    *,
    timeout: float = DRAFT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """POST one chat completion. Redirects, including 307 and 308, are not followed."""
    url = f"{endpoint.base_url.rstrip('/')}/chat/completions"
    headers: dict[str, str] = {}
    if endpoint.api_key:
        headers["Authorization"] = f"Bearer {endpoint.api_key}"
    body = {
        "model": endpoint.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout) as client:
            response = client.post(url, headers=headers, json=body, follow_redirects=False)
    except httpx.TimeoutException as error:
        raise LlmCallError("timeout") from error
    except httpx.HTTPError as error:
        raise LlmCallError("transport") from error
    if 300 <= response.status_code < 400:
        raise LlmCallError("redirect")
    if response.status_code in {401, 402, 403, 429}:
        raise LlmCallError("quota")
    if response.status_code >= 400:
        raise LlmCallError("http")
    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise LlmCallError("schema") from error
    if not isinstance(parsed, dict):
        raise LlmCallError("schema")
    return parsed
