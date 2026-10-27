"""LLM endpoint stored in settings.json. The API key never is.

The desktop writes ``llmBaseUrl``, ``llmModel``, and ``llmPrivacyAcknowledged``.
The API key lives in the secret vault under ``llm-api-key`` and is pushed into
this process by ``install_secrets``. Environment variables still override the
file so an existing reviewer setup keeps working.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

BASE_URL_KEY = "llmBaseUrl"
MODEL_KEY = "llmModel"
PRIVACY_KEY = "llmPrivacyAcknowledged"
SECRET_ID = "llm-api-key"
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


def write_llm_settings(
    path: Path,
    *,
    base_url: str,
    model: str,
    privacy_acknowledged: bool,
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
    return LlmEndpoint(base_url=base_url, api_key=api_key, model=model)
