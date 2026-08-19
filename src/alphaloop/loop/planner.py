"""
LLM planner helper used by N1, N2, and N5.

The design (docs/plans/v07-hybrid-loop.md § 2.3) commits us to a
*hybrid* runtime: the DAG skeleton is static and deterministic, but
inside N1 (data), N2 (strategy plan), and N5 (report) the LLM gets to
make decisions. This module isolates that LLM-planning surface so:

- All planner calls go through one method that records inputs/outputs
  for replay (design doc § 2.8 R1, § 3.3).
- Tests can inject a fake client (design doc § 4.2).
- The real client is the same one v0.6 uses for the judge.

The planner is intentionally thin: it formats a prompt, calls the
LLM, parses JSON if applicable, and returns a dict. The orchestrator
(N1/N2/N5 bodies) decides *what to do with the response*.

For v0.7 MVP, the planner does not block on a missing API key: if no
client is configured, it falls back to a deterministic stub that
returns a sensible default based on the goal text. This keeps
``alphaloop loop`` runnable on a fresh checkout without credentials
(``--dry-run`` is the canonical way to inspect the planner output
without committing budget).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


# ---------------------------------------------------------------------
# LLM client protocol — same shape as v0.6's judge.LLMClient so the
# judge LLMJudgeClient can be reused directly.
# ---------------------------------------------------------------------


class LLMClient(Protocol):
    """Minimal contract for any LLM backend.

    v0.6's ``alphaloop.judge.LLMJudgeClient`` already implements this.
    """

    def complete(
        self, messages: list[dict], model: str, **kwargs: Any
    ) -> Any:  # returns RawCompletion-like
        ...


# ---------------------------------------------------------------------
# Planner result + the planner itself.
# ---------------------------------------------------------------------


@dataclass
class PlannerCall:
    """A single planner invocation: input prompt + parsed response.

    The runner persists each ``PlannerCall`` into ``judge_calls/`` so
    replay can consume them without re-calling the LLM (design doc §
    2.8 R1 mitigation).
    """

    node: str  # "n1" / "n2" / "n5"
    prompt: list[dict]  # OpenAI-style messages
    response_text: str
    parsed: Optional[dict] = None
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass
class Planner:
    """Stateful planner: holds the client + a call log.

    Tests inject a fake client (e.g. ``FakeLLMClient`` from
    ``tests/conftest.py``) so no real HTTP happens in CI.
    """

    client: Optional[LLMClient] = None
    model: str = "gpt-4o-mini"
    cost_per_1k_tokens: float = 0.00015  # gpt-4o-mini input/output blended
    calls: list[PlannerCall] = field(default_factory=list)

    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def call(
        self,
        node: str,
        messages: list[dict],
        *,
        json_mode: bool = True,
    ) -> PlannerCall:
        """Invoke the LLM once; parse JSON if possible; record.

        If ``client`` is ``None``, returns a deterministic stub so the
        loop is still end-to-end runnable without API keys (design
        doc § 1.6 — cost ≤ $5; many runs need to verify the *shape*
        of the loop without spending budget).
        """
        if self.client is None:
            response_text = _stub_response(node, messages)
            call = PlannerCall(
                node=node,
                prompt=list(messages),
                response_text=response_text,
                parsed=_try_parse_json(response_text),
                cost_usd=0.0,
                latency_ms=0,
            )
            self.calls.append(call)
            return call

        # Real client path.
        try:
            completion = self.client.complete(messages, model=self.model)
        except Exception as e:  # pragma: no cover — defensive
            response_text = json.dumps({"error": f"{type(e).__name__}: {e}"})
            call = PlannerCall(
                node=node,
                prompt=list(messages),
                response_text=response_text,
                parsed=None,
                cost_usd=0.0,
                latency_ms=0,
            )
            self.calls.append(call)
            return call

        # RawCompletion has .content / .prompt_tokens / .completion_tokens.
        content = getattr(completion, "content", str(completion))
        prompt_tokens = int(getattr(completion, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(completion, "completion_tokens", 0) or 0)
        latency_ms = int(getattr(completion, "latency_ms", 0) or 0)
        cost = (prompt_tokens + completion_tokens) / 1000.0 * self.cost_per_1k_tokens

        call = PlannerCall(
            node=node,
            prompt=list(messages),
            response_text=content,
            parsed=_try_parse_json(content) if json_mode else None,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
        self.calls.append(call)
        return call


# ---------------------------------------------------------------------
# Prompt templates + JSON parsing helpers.
# ---------------------------------------------------------------------


GOAL_DATA_HINT_RE = re.compile(
    r"\b(equities|etfs|crypto|forex|fx|stocks|bonds|options|futures|sp500|spy)\b",
    re.IGNORECASE,
)


def _try_parse_json(text: str) -> Optional[dict]:
    """Robust JSON load — tolerates code-fences and prose around dicts."""
    if not isinstance(text, str) or not text.strip():
        return None
    s = text.strip()
    if s.startswith("```"):
        end = s.rfind("```")
        if end > 3:
            inner = s[3:end]
            if "\n" in inner:
                first, rest = inner.split("\n", 1)
                if first.strip().lower() in ("json", "json5", "javascript", ""):
                    inner = rest
            s = inner.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except (ValueError, TypeError):
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last > first:
            try:
                obj = json.loads(s[first : last + 1])
                return obj if isinstance(obj, dict) else None
            except (ValueError, TypeError):
                return None
    return None


def _stub_response(node: str, messages: list[dict]) -> str:
    """Deterministic fallback when no LLM client is configured.

    Goal: keep the loop runnable end-to-end on a fresh checkout
    without credentials. The output is a stable JSON dict that the
    N1/N2/N5 bodies can consume identically to a real LLM response.
    """
    last_user = ""
    for m in messages:
        if m.get("role") == "user":
            last_user = m.get("content", "")

    if node == "n1":
        # Default to a small synthetic universe.
        hint = GOAL_DATA_HINT_RE.search(last_user)
        universe = hint.group(1).lower() if hint else "synthetic"
        return json.dumps(
            {
                "sources": ["synthetic"],
                "symbols": ["AAA", "BBB", "CCC"],
                "start": "2020-01-01",
                "end": "2024-12-31",
                "universe_kind": universe,
            },
            sort_keys=True,
        )

    if node == "n2":
        # Default task universe — 8 strategy × 2 factor combos, light.
        strategies = [
            "BuyHoldStrategy",
            "RebalanceStrategy",
            "MovingAverageCrossoverStrategy",
            "Classic6040Strategy",
            "ValueStrategy",
            "SectorRotationStrategy",
            "RiskParityStrategy",
            "TargetDateStrategy",
        ]
        factors = ["Momentum12M", "MeanReversionZ"]
        tasks: list[dict] = []
        for s in strategies:
            for f in factors:
                tasks.append(
                    {
                        "strategy": s,
                        "factor": f,
                        "params": {},
                    }
                )
        return json.dumps({"tasks": tasks, "n_trials": len(tasks)}, sort_keys=True)

    if node == "n5":
        # Default report stub (one line per pick; N5 body fills it in).
        return json.dumps(
            {
                "report_intro": "Synthetic report — no LLM client configured.",
                "thesis_per_rank": {},
            },
            sort_keys=True,
        )

    return json.dumps({"ok": True}, sort_keys=True)


def prompt_n1(goal: str) -> list[dict]:
    """Build the N1 planner prompt (data plan)."""
    return [
        {
            "role": "system",
            "content": (
                "You are alphaloop's data planner. Reply in JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Goal: {goal}\n"
                "Return JSON with keys: sources (list of 'yahoo'/'akshare'/"
                "'ccxt'/'openbb'/'synthetic'), symbols (list), start, end, "
                "universe_kind. Keep under 4 KB."
            ),
        },
    ]


def prompt_n2(goal: str, n_budget: int) -> list[dict]:
    """Build the N2 planner prompt (strategy plan)."""
    return [
        {
            "role": "system",
            "content": (
                "You are alphaloop's strategy planner. Reply in JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Goal: {goal}\n"
                f"Produce up to {n_budget} task specs as JSON: "
                "{tasks: [{strategy, factor, params}, ...], n_trials: int}. "
                "Strategies are picked from alphaloop.strategies. "
                "Each task has a uuid4 task_id assigned at runtime."
            ),
        },
    ]


def prompt_n5(goal: str, top5: list[dict]) -> list[dict]:
    """Build the N5 planner prompt (report writer)."""
    return [
        {
            "role": "system",
            "content": (
                "You are alphaloop's report writer. Reply in JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Goal: {goal}\n"
                f"Top-5 picks: {json.dumps(top5, sort_keys=True)}\n"
                "Return JSON {report_intro: str, thesis_per_rank: "
                "{<rank_int>: <one_line_thesis>}}."
            ),
        },
    ]


def plan_n1(goal: str, planner: Planner) -> dict:
    """Plan the data load — wraps the LLM call + JSON parse.

    Returns the parsed dict. Falls back to the stub if the response
    is not valid JSON. The runner persists the raw call.
    """
    call = planner.call("n1", prompt_n1(goal))
    if call.parsed is not None:
        return call.parsed
    # Best-effort fallback: ensure the keys N1 expects exist.
    return {"sources": ["synthetic"], "symbols": [], "end": ""}


def plan_n2(goal: str, planner: Planner, n_budget: int = 16) -> dict:
    """Plan the strategy universe — wraps the LLM call + JSON parse.

    The orchestrator (N2 body in ``runner.py``) is responsible for
    stamping each task with a uuid4 task_id; this function only
    returns the *shape* of the universe.
    """
    call = planner.call("n2", prompt_n2(goal, n_budget))
    if call.parsed is not None and "tasks" in call.parsed:
        return call.parsed
    return {"tasks": [], "n_trials": 0}


def plan_n5(
    goal: str, top5: list[dict], planner: Planner
) -> dict:
    """Plan the report — one-line thesis per top-5 rank."""
    call = planner.call("n5", prompt_n5(goal, top5))
    if call.parsed is not None:
        return call.parsed
    return {"report_intro": "", "thesis_per_rank": {}}


# ---------------------------------------------------------------------
# Env var helpers — match design doc § 2.9 resolution order.
# ---------------------------------------------------------------------


def resolve_model(cli_model: Optional[str] = None) -> str:
    """Resolve LLM_MODEL from CLI flag → env → default stub."""
    if cli_model:
        return cli_model
    env = os.environ.get("LLM_MODEL")
    if env:
        return env
    return "gpt-4o-mini"


def has_llm_credentials() -> bool:
    """Return True if both LLM_API_KEY and LLM_MODEL are set."""
    return bool(os.environ.get("LLM_API_KEY")) and bool(
        os.environ.get("LLM_MODEL")
    )


__all__ = [
    "LLMClient",
    "Planner",
    "PlannerCall",
    "plan_n1",
    "plan_n2",
    "plan_n5",
    "prompt_n1",
    "prompt_n2",
    "prompt_n5",
    "resolve_model",
    "has_llm_credentials",
]