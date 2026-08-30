from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

import httpx

from engine.research.models import (
    Attempt,
    ConfirmKind,
    ConfirmRequest,
    ReviewFinding,
    ReviewReport,
    Round,
    RoundDraft,
)

MAX_CONSECUTIVE_REVIEW_FAILURES = 3

FROZEN_REVIEW_RUBRIC = """You are the mandatory independent reviewer for one alphaloop automatic
research-round draft. Return JSON only with exactly:
{"passed": bool, "findings": [{"code": str, "message": str}], "required_changes": str?}
Fail when any of these is present:
1. lookahead bias: any signal, universe choice, fit, or fill uses information unavailable at decision time;
2. economic-logic drift: thesis_locked, universe, method_set, benchmark, or earning mechanism changed without confirmation;
3. data-snooping: OOS data or repeated trials were used to select parameters without a frozen holdout;
4. benchmark mismatch: the benchmark does not match the locked market and underlying asset class.
Missing evidence is a failure. Do not infer approval from timeout, malformed output, or tool failure."""


class LLMPort(Protocol):
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class OpenAICompatibleLLM:
    client: httpx.Client
    base_url: str
    api_key: str
    model: str

    def complete(self, system: str, user: str) -> str:
        response = self.client.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])


class ReviewerPort(Protocol):
    def run(self, round_draft: RoundDraft) -> ReviewReport:
        raise NotImplementedError


@dataclass(slots=True)
class SubagentReviewer:
    llm: LLMPort

    def run(self, round_draft: RoundDraft) -> ReviewReport:
        attempt = round_draft.attempt
        payload = {
            "version_number": round_draft.version_number,
            "round_number": round_draft.round_number,
            "attempt_id": attempt.attempt_id,
            "strategy": {
                "id": attempt.spec.id,
                "thesis_locked": attempt.spec.thesis_locked,
                "universe": repr(attempt.spec.universe),
                "model_family": attempt.spec.model_family,
                "lookback_days": attempt.spec.lookback_days,
            },
            "metrics": repr(attempt.simulation),
            "verification": repr(attempt.verification),
        }
        try:
            raw = self.llm.complete(
                FROZEN_REVIEW_RUBRIC,
                json.dumps(payload, sort_keys=True, default=str),
            )
            parsed = json.loads(raw)
            if set(parsed) - {"passed", "findings", "required_changes"}:
                raise ValueError("unexpected review field")
            if not isinstance(parsed["passed"], bool) or not isinstance(parsed["findings"], list):
                raise TypeError("invalid review field type")
            findings = tuple(
                ReviewFinding(code=item["code"], message=item["message"])
                for item in parsed["findings"]
            )
            required = parsed.get("required_changes")
            if not parsed["passed"] and not required:
                raise ValueError("failed review requires required_changes")
            return ReviewReport(parsed["passed"], findings, required)
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            httpx.HTTPError,
            TimeoutError,
            OSError,
        ) as error:
            return ReviewReport(
                passed=False,
                findings=(ReviewFinding("review_protocol", str(error)),),
                required_changes="retry with a valid independent review result",
            )


RetryFactory = Callable[[RoundDraft, ReviewReport], RoundDraft]
AttemptSink = Callable[[Attempt], None]


@dataclass(frozen=True, slots=True)
class ReviewGateOutcome:
    version_number: int
    attempts: tuple[Attempt, ...]
    successful_round: Round | None
    confirm_request: ConfirmRequest | None


def run_review_gate(
    initial: RoundDraft,
    reviewer: ReviewerPort,
    retry: RetryFactory,
    now: datetime,
    prior_failures: int = 0,
    on_attempt: AttemptSink | None = None,
) -> ReviewGateOutcome:
    if not 0 <= prior_failures < MAX_CONSECUTIVE_REVIEW_FAILURES:
        raise ValueError("prior_failures must be 0, 1, or 2")
    current = initial
    attempts: list[Attempt] = []
    for failure_count in range(
        prior_failures,
        MAX_CONSECUTIVE_REVIEW_FAILURES,
    ):
        report = reviewer.run(current)
        reviewed_attempt = replace(current.attempt, review=report)
        attempts.append(reviewed_attempt)
        if on_attempt is not None:
            on_attempt(reviewed_attempt)
        if report.passed:
            return ReviewGateOutcome(
                version_number=initial.version_number,
                attempts=tuple(attempts),
                successful_round=Round(
                    round_id=f"v{initial.version_number}-r{initial.round_number}",
                    number=initial.round_number,
                    accepted_attempt=reviewed_attempt,
                    completed_at=now,
                ),
                confirm_request=None,
            )
        if failure_count + 1 < MAX_CONSECUTIVE_REVIEW_FAILURES:
            current = retry(replace(current, attempt=reviewed_attempt), report)
            if current.version_number != initial.version_number:
                raise ValueError("automatic review retry cannot advance version")
            if current.attempt.attempt_id in {item.attempt_id for item in attempts}:
                raise ValueError("automatic review retry must be a different attempt")
    return ReviewGateOutcome(
        version_number=initial.version_number,
        attempts=tuple(attempts),
        successful_round=None,
        confirm_request=ConfirmRequest(
            request_id=f"review-blocked-v{initial.version_number}-r{initial.round_number}",
            kind=ConfirmKind.REVIEW_BLOCKED,
            proposed_change="人工检查审查发现，或确认经济逻辑调整后再继续",
            reason="连续3次独立审查未通过",
            effect="研究保持当前版本并停止消耗有效研究时间",
        ),
    )
