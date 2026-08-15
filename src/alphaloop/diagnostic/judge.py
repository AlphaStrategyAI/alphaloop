"""
Q7: LLM-as-Judge diagnostic — narrative quality scoring for backtest reports.

This is the *7th* diagnostic in the alphaloop acceptance suite. It
answers the question "is this report itself honestly written?" by
asking an LLM to score the report Markdown on three independent
dimensions:

- readability:       Can a non-quant reader follow the report?
- decision_quality:  Are the investment decisions justified by the data?
- risk_disclosure:   Are risks honestly disclosed?

The judge is **additive**, not a replacement for the 6 quantitative
diagnostics (DSR, CV, consistency, vs random, vs buy-hold, vs SPY).
A strategy can pass Q1–Q6 but fail Q7 (well-tested, poorly explained)
and vice versa; both outcomes are reported honestly.

Resolution order for LLM connection (highest priority first):

1. CLI flag (`--judge-model`, `--judge-api-key`, `--judge-base-url`).
2. Environment variables (`LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`).
3. YAML fallback (`LLM_JUDGE_CONFIG` env var).

A missing `model` or `api_key` is **not** fatal — the judge returns a
`LLMJudgeResult(error="...")` and the rest of the report continues.
The 6 quantitative sections are never blocked by a missing LLM key.

See `docs/design/v06-llm-judge.md` for the design rationale.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from ..judge import (
    DimensionScore,
    LLMClient,
    LLMJudgeClient,
    LLMJudgeResult,
    RawCompletion,
)
from ..judge.client import LLMCallError, LLMConfigError
from ..judge.prompts import render_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def llm_judge(
    report: str,
    *,
    threshold: int = 7,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    client: Optional[LLMClient] = None,
    yaml_path: Optional[str] = None,
) -> LLMJudgeResult:
    """Score a backtest report on 3 narrative dimensions using an LLM.

    Args:
        report: The full Markdown report to evaluate. Will be embedded
            verbatim in the user prompt between `<report>...</report>`
            tags.
        threshold: Minimum score (1-10) required on each dimension
            for the result to pass. Default 7.
        model: Model name to use. If None, resolved from env vars
            (`LLM_MODEL`) or the YAML fallback (`LLM_JUDGE_CONFIG`).
        api_key: API key. If None, resolved from `LLM_API_KEY` env var
            or the YAML fallback.
        base_url: OpenAI-compatible endpoint URL. If None, resolved
            from `LLM_BASE_URL` env var or the YAML fallback.
        client: Pre-configured `LLMClient` (used by tests). If None,
            a real `LLMJudgeClient` is constructed from env vars.
        yaml_path: Optional path to a YAML config file. If not given,
            uses `LLM_JUDGE_CONFIG` env var.

    Returns:
        `LLMJudgeResult` with three dimension scores, per-dimension
        reasoning/evidence, observability fields (model, tokens,
        latency, raw_response), and a `passes` flag.

        On any failure (missing config, network error, invalid JSON,
        out-of-range scores, ...), `result.error` is set and
        `result.passes` is False; `summary()` shows SKIP. The 6
        quantitative diagnostics are unaffected.
    """
    # Pre-build the result with a default threshold; we'll mutate it
    # later as we learn things. Keeping it as a single object lets us
    # populate observability fields even on early-return error paths.
    result = LLMJudgeResult(threshold=int(threshold))

    # 1. Resolve the client.
    if client is None:
        try:
            client = LLMJudgeClient.from_env_or_args(
                model=model,
                api_key=api_key,
                base_url=base_url,
                yaml_path=yaml_path,
            )
        except LLMConfigError as e:
            result.error = f"config: {e}"
            logger.warning("LLM judge skipped — %s", e)
            return result

    # 2. Render the prompt.
    try:
        messages = render_prompt(report)
    except (ValueError, IOError) as e:
        result.error = f"prompt: {e}"
        logger.warning("LLM judge skipped — %s", e)
        return result

    # 3. Call the LLM.
    use_model = model or _client_default_model(client) or os.environ.get(
        "LLM_MODEL", ""
    )
    try:
        completion: RawCompletion = client.complete(messages, model=use_model)
    except LLMCallError as e:
        result.error = f"call: HTTP {e.status}: {e.body[:120]}"
        logger.warning("LLM judge skipped — %s", result.error)
        return result
    except LLMConfigError as e:
        result.error = f"config: {e}"
        logger.warning("LLM judge skipped — %s", e)
        return result
    except Exception as e:  # pragma: no cover — last-resort guard
        result.error = f"unexpected: {type(e).__name__}: {e}"
        logger.warning("LLM judge skipped — %s", result.error)
        return result

    result.model = completion.model or use_model
    result.raw_response = completion.content
    result.prompt_tokens = completion.prompt_tokens
    result.completion_tokens = completion.completion_tokens
    result.latency_ms = completion.latency_ms

    # 4. Parse the JSON response.
    parsed = _safe_json_loads(completion.content)
    if parsed is None:
        result.error = "parse: response was not valid JSON"
        logger.warning(
            "LLM judge parse failure — raw response saved; first 200 chars: %r",
            completion.content[:200],
        )
        return result

    # 5. Build per-dimension scores.
    result.readability = _dimension_from(parsed.get("readability"), "readability")
    result.decision_quality = _dimension_from(
        parsed.get("decision_quality"), "decision_quality"
    )
    result.risk_disclosure = _dimension_from(
        parsed.get("risk_disclosure"), "risk_disclosure"
    )
    return result


# ---------------------------------------------------------------------------
# Helpers (private)
# ---------------------------------------------------------------------------


def _client_default_model(client: LLMClient) -> str:
    """Best-effort lookup of the default model name on a client.

    The `LLMClient` Protocol only requires `complete()`; some concrete
    clients (e.g. `LLMJudgeClient`) carry a `config.model` attribute,
    others (e.g. test fakes) may not. This helper does the safe thing.
    """
    cfg = getattr(client, "config", None)
    if cfg is None:
        return ""
    return getattr(cfg, "model", "") or ""


def _safe_json_loads(text: str) -> Optional[dict]:
    """Robust JSON load.

    Handles three common LLM failure modes:
    1. Valid JSON (no-op).
    2. JSON wrapped in markdown fences (```json ... ```).
    3. JSON with leading/trailing prose.

    Returns the parsed dict on success, None on failure (never raises).
    """
    if not isinstance(text, str) or not text.strip():
        return None

    s = text.strip()

    # Strip code fences if present.
    if s.startswith("```"):
        # Find the closing fence; everything between is the body.
        end = s.rfind("```")
        if end > 3:
            inner = s[3:end]
            # Drop an optional language hint on the first line.
            if "\n" in inner:
                first, rest = inner.split("\n", 1)
                if first.strip().lower() in ("json", "json5", "javascript", ""):
                    inner = rest
            s = inner.strip()

    # First attempt: parse the whole thing.
    try:
        loaded = json.loads(s)
        return loaded if isinstance(loaded, dict) else None
    except (ValueError, TypeError):
        pass

    # Second attempt: find the first { ... last } block.
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last > first:
        candidate = s[first : last + 1]
        try:
            loaded = json.loads(candidate)
            return loaded if isinstance(loaded, dict) else None
        except (ValueError, TypeError):
            return None

    return None


def _dimension_from(raw: object, name: str) -> DimensionScore:
    """Build a `DimensionScore` from a parsed JSON dict (or anything)."""
    if not isinstance(raw, dict):
        return DimensionScore(
            score=1,
            reasoning="missing from response",
            evidence="",
        )
    score = raw.get("score", 1)
    try:
        score_int = int(score)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        score_int = 1
    # Clamp happens in DimensionScore.__post_init__.
    return DimensionScore(
        score=score_int,
        reasoning=str(raw.get("reasoning", "") or ""),
        evidence=str(raw.get("evidence", "") or ""),
    )


# ---------------------------------------------------------------------------
# Diagnostic protocol compatibility
# ---------------------------------------------------------------------------


def run(report: str, **kwargs) -> LLMJudgeResult:
    """Diagnostic-protocol entry point.

    Mirrors how other diagnostics expose `run(...)` — but for the judge,
    the canonical entry point is the `llm_judge(...)` function above.
    Kept as a thin wrapper so future dispatchers can treat all
    diagnostics uniformly.
    """
    return llm_judge(report, **kwargs)