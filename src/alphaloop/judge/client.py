"""
LLM judge HTTP client.

This module is the *only* place in alphaloop that makes outbound HTTP
calls for the LLM judge. It is intentionally thin — no streaming, no
tool calls, no embeddings — just a synchronous `complete()` method that
POSTs to `{base_url}/chat/completions` with an OpenAI-compatible JSON
payload and returns a `RawCompletion`.

Configuration resolution order (highest priority first):

1. CLI flag (`--judge-model`, `--judge-api-key`, `--judge-base-url`).
2. Environment variables (`LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`).
3. YAML fallback file (path from `LLM_JUDGE_CONFIG` env var).

If the resolved config has a missing `api_key` or empty `model`, the
client raises `LLMConfigError`. The diagnostic layer catches this and
returns an `LLMJudgeResult(error=...)` with `passes=False`.

Retries: 3 tries on 429/5xx with exponential backoff (1s, 2s, 4s).
Total wall-clock cap is enforced by the timeout setting (default 30s
per request, design doc § 3.4).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

from .types import LLMConfig, RawCompletion


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMConfigError(ValueError):
    """Raised when the judge client is constructed with invalid config.

    Examples: missing API key, empty model, missing base URL. The
    diagnostic layer catches this and produces a SKIP result.
    """


class LLMCallError(RuntimeError):
    """Raised when the HTTP call to the LLM endpoint fails.

    Carries the HTTP status code and response body for logging.
    """

    def __init__(self, status: int, body: str, message: Optional[str] = None):
        self.status = status
        self.body = body
        super().__init__(message or f"LLM call failed: HTTP {status}: {body[:200]}")


# ---------------------------------------------------------------------------
# Client protocol (mirrors types.LLMClient)
# ---------------------------------------------------------------------------


class LLMClient(Protocol):
    """Anything that can produce a chat completion. Used for DI in tests."""

    def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> RawCompletion: ...


# ---------------------------------------------------------------------------
# YAML fallback loader (for `LLM_JUDGE_CONFIG`)
# ---------------------------------------------------------------------------


def _load_yaml_config(path: str) -> dict:
    """Load a tiny subset of YAML from `path` for LLM judge settings.

    Recognized top-level keys (all optional): `model`, `api_key`,
    `base_url`, `timeout_s`. Anything else is ignored (forward-compat).
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise LLMConfigError(f"cannot read LLM judge config at {path}: {e}") from e
    return _parse_yaml(text)


def _parse_yaml(text: str) -> dict:
    """Parse a tiny YAML subset: top-level `key: value` pairs only.

    Values may be quoted with double quotes; multiline values are NOT
    supported in the config file (the bundled prompt template uses
    `judge.prompts` for that).
    """
    out: dict = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'") and len(value) >= 2:
            value = value[1:-1]
        out[key] = value
    return out


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


@dataclass
class LLMJudgeClient:
    """OpenAI-compatible chat-completion client for the LLM judge.

    Resolution order (highest priority first):

    1. Explicit constructor args (`model`, `api_key`, `base_url`).
    2. CLI-flag overrides passed to `from_env_or_args`.
    3. Environment variables (`LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`).
    4. YAML fallback file (`LLM_JUDGE_CONFIG` env var).

    Attributes:
        config: The resolved `LLMConfig`. Holds the chosen model,
            base URL, and API key. The key is *never* logged.
        max_retries: How many times to retry on 429/5xx. Default 3
            (initial + 2 retries = 3 attempts total).
        backoff_base_s: Initial backoff in seconds; doubled each retry.
            Default 1.0 → waits 1s, 2s, 4s.
    """

    config: LLMConfig
    max_retries: int = 3
    backoff_base_s: float = 1.0

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_env_or_args(
        cls,
        *,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        yaml_path: Optional[str] = None,
        timeout_s: Optional[int] = None,
    ) -> "LLMJudgeClient":
        """Resolve config from explicit args → env vars → YAML fallback.

        Raises LLMConfigError if `model` or `api_key` is still missing
        after resolution.
        """
        # 1. Explicit args
        resolved_model = model or os.environ.get("LLM_MODEL", "")
        resolved_key = api_key or os.environ.get("LLM_API_KEY", "")
        resolved_url = base_url or os.environ.get("LLM_BASE_URL", "")
        resolved_timeout = timeout_s if timeout_s is not None else _int_env(
            "LLM_TIMEOUT_S", default=30
        )

        # 2. YAML fallback (only if explicitly pointed at, by env or arg)
        yaml_path = yaml_path or os.environ.get("LLM_JUDGE_CONFIG")
        if yaml_path:
            yaml_cfg = _load_yaml_config(yaml_path)
            resolved_model = resolved_model or yaml_cfg.get("model", "")
            resolved_key = resolved_key or yaml_cfg.get("api_key", "")
            resolved_url = resolved_url or yaml_cfg.get("base_url", "")
            if "timeout_s" in yaml_cfg and timeout_s is None:
                try:
                    resolved_timeout = int(yaml_cfg["timeout_s"])
                except (TypeError, ValueError):
                    pass

        if not resolved_model:
            raise LLMConfigError(
                "LLM_MODEL not set (use --judge-model, LLM_MODEL env var, "
                "or LLM_JUDGE_CONFIG yaml fallback)"
            )
        if not resolved_key:
            raise LLMConfigError(
                "LLM_API_KEY not set (use --judge-api-key, LLM_API_KEY env var, "
                "or LLM_JUDGE_CONFIG yaml fallback)"
            )

        cfg = LLMConfig(
            model=resolved_model,
            api_key=resolved_key,
            base_url=resolved_url,
            timeout_s=resolved_timeout,
        )
        return cls(config=cfg)

    # ------------------------------------------------------------------
    # Chat completion
    # ------------------------------------------------------------------

    def complete(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> RawCompletion:
        """POST to `{base_url}/chat/completions` and return RawCompletion.

        Retries on 429/5xx with exponential backoff (1s, 2s, 4s by
        default). Raises `LLMCallError` on any other HTTP failure or
        after exhausting retries.
        """
        use_model = model or self.config.model
        url = self._chat_url()
        body = json.dumps(
            {
                "model": use_model,
                "messages": list(messages),
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
            }
        ).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        attempts = max(1, int(self.max_retries))
        last_error: Optional[Exception] = None
        start = time.monotonic()

        for attempt in range(attempts):
            try:
                req = urllib.request.Request(
                    url, data=body, headers=headers, method="POST"
                )
                with urllib.request.urlopen(
                    req, timeout=self.config.timeout_s
                ) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    payload = json.loads(raw)
                    latency_ms = int((time.monotonic() - start) * 1000)
                    return _parse_completion(payload, latency_ms=latency_ms)
            except urllib.error.HTTPError as e:
                # Retry only on 429 and 5xx.
                status = getattr(e, "code", 0)
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                if status == 429 or 500 <= status < 600:
                    last_error = LLMCallError(status, err_body)
                    if attempt + 1 < attempts:
                        time.sleep(self.backoff_base_s * (2 ** attempt))
                        continue
                    raise last_error
                raise LLMCallError(status, err_body)
            except urllib.error.URLError as e:
                # Network error — retry.
                last_error = LLMCallError(0, str(e))
                if attempt + 1 < attempts:
                    time.sleep(self.backoff_base_s * (2 ** attempt))
                    continue
                raise last_error

        # Should be unreachable, but be defensive.
        if last_error is not None:
            raise last_error
        raise LLMCallError(0, "unknown failure: retry loop exited without error")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _chat_url(self) -> str:
        url = (self.config.base_url or "").rstrip("/")
        if not url:
            # No base URL — we still let the user skip if they wired a
            # custom client. But for the real HTTP client, this is a
            # config error.
            raise LLMConfigError(
                "LLM_BASE_URL not set (use --judge-base-url or LLM_BASE_URL env var)"
            )
        return f"{url}/chat/completions"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _int_env(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _parse_completion(payload: Any, *, latency_ms: int) -> RawCompletion:
    """Extract `content`, `model`, and `usage` from an OpenAI-shaped JSON."""
    model = ""
    content = ""
    prompt_tokens = 0
    completion_tokens = 0

    if isinstance(payload, dict):
        model = str(payload.get("model", "") or "")
        choices = payload.get("choices") or []
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message") or {}
                if isinstance(msg, dict):
                    content = str(msg.get("content", "") or "")
        usage = payload.get("usage") or {}
        if isinstance(usage, dict):
            try:
                prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            except (TypeError, ValueError):
                prompt_tokens = 0
            try:
                completion_tokens = int(usage.get("completion_tokens", 0) or 0)
            except (TypeError, ValueError):
                completion_tokens = 0

    return RawCompletion(
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
        latency_ms=latency_ms,
    )