"""
Type definitions for the LLM-as-judge evaluator.

Three independent dimensions are scored 1-10:

- readability:       Can a non-quant reader follow the report?
- decision_quality:  Are the investment decisions justified by the data?
- risk_disclosure:   Are risks honestly disclosed?

`LLMJudgeResult` is the public result object; its `summary()` method
renders a Markdown-friendly block that mirrors the format of the other
diagnostics in `alphaloop.diagnostic`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------


def _clamp_score(value: object, default: int = 1) -> int:
    """Clamp an arbitrary value into the integer range [1, 10].

    Used after parsing the LLM response to guard against out-of-range
    or non-numeric scores (a known model-drift failure mode).
    """
    try:
        v = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if v < 1:
        return 1
    if v > 10:
        return 10
    return v


# ---------------------------------------------------------------------------
# Dimension score
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Score and reasoning for a single dimension (1-10).

    Attributes:
        score: Integer in [1, 10]. Out-of-range values are clamped.
        reasoning: 1-3 sentences from the model.
        evidence: Quoted text from the report supporting the score
            (verbatim where possible; the LLM is instructed not to invent).
    """

    score: int = 1
    reasoning: str = ""
    evidence: str = ""

    def __post_init__(self) -> None:
        # Clamp silently — the design doc § 5.1 R2 says clamp, never fail.
        self.score = _clamp_score(self.score, default=1)


# ---------------------------------------------------------------------------
# Raw completion (transport-level observability)
# ---------------------------------------------------------------------------


@dataclass
class RawCompletion:
    """The raw LLM chat-completion response, as returned by the client.

    Used by `LLMJudgeClient.complete()` and by tests (FakeLLMClient
    returns one of these per call).
    """

    content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# Public result
# ---------------------------------------------------------------------------


@dataclass
class LLMJudgeResult:
    """Result of an LLM-as-judge evaluation.

    Three independent dimension scores (each 1-10, clamped). The result
    `passes` iff all three meet `threshold` (default 7).

    Observability fields (`model`, `raw_response`, `prompt_tokens`,
    `completion_tokens`, `latency_ms`) are always populated — even on
    failure — so the user can monitor cost and latency in v0.7+.

    `error` is populated iff the LLM call was skipped (missing config,
    network failure, invalid JSON, ...). When `error` is set, `passes`
    is `False` and `summary()` renders SKIP.
    """

    # Three independent dimension scores
    readability: DimensionScore = field(default_factory=DimensionScore)
    decision_quality: DimensionScore = field(default_factory=DimensionScore)
    risk_disclosure: DimensionScore = field(default_factory=DimensionScore)

    # Pass iff all 3 dimensions meet threshold
    threshold: int = 7

    # Observability
    model: str = ""
    raw_response: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    error: Optional[str] = None

    def __post_init__(self) -> None:
        # Clamp threshold defensively — same range as dimension scores.
        if not isinstance(self.threshold, int):
            try:
                self.threshold = int(self.threshold)
            except (TypeError, ValueError):
                self.threshold = 7
        if self.threshold < 1:
            self.threshold = 1
        if self.threshold > 10:
            self.threshold = 10

    # ------------------------------------------------------------------
    # Convenience aggregates
    # ------------------------------------------------------------------

    @property
    def overall_score(self) -> float:
        """Min of the three dimension scores (conservative aggregate)."""
        return float(
            min(
                self.readability.score,
                self.decision_quality.score,
                self.risk_disclosure.score,
            )
        )

    @property
    def passes(self) -> bool:
        """True iff every dimension score is >= threshold and no error."""
        if self.error is not None:
            return False
        return (
            self.readability.score >= self.threshold
            and self.decision_quality.score >= self.threshold
            and self.risk_disclosure.score >= self.threshold
        )

    # ------------------------------------------------------------------
    # Markdown summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Markdown-friendly summary, mirrors the format of other diagnostics."""
        if self.error is not None:
            verdict = "SKIP"
        elif self.passes:
            verdict = "PASS"
        else:
            verdict = "FAIL"
        return (
            f"LLM Judge verdict: {verdict}\n"
            f"  Model: {self.model or '(skipped)'}\n"
            f"  Readability:       {self.readability.score}/10\n"
            f"  Decision quality:  {self.decision_quality.score}/10\n"
            f"  Risk disclosure:   {self.risk_disclosure.score}/10\n"
            f"  Overall (min):     {self.overall_score:.1f}/10\n"
            f"  Threshold:         {self.threshold}/10\n"
            f"  Latency:           {self.latency_ms} ms\n"
            f"  Tokens:            {self.prompt_tokens} prompt + "
            f"{self.completion_tokens} completion"
        )


# ---------------------------------------------------------------------------
# Client protocol (for dependency injection in tests)
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """Anything that can produce a chat completion. Used for DI in tests.

    Implementations must be synchronous; the diagnostic layer wraps a
    single call per `llm_judge()` invocation.
    """

    def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> RawCompletion: ...


# ---------------------------------------------------------------------------
# LLMConfig (resolution result)
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    """Resolved LLM connection settings for a single judge invocation.

    Created by `LLMJudgeClient.from_env_or_args(...)`. Holds the model
    name to use, the base URL, and the API key. `api_key` is *never*
    serialized to logs or Markdown — only its presence is checked.
    """

    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout_s: int = 30