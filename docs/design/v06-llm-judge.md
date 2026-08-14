---
title: "alphaloop v0.6 — LLM-as-Judge Evaluator Design"
version: "0.6"
status: "design"
authors:
  - alphaloop design subagent
date: "2026-08-14"
loop: "alphaloop-v06-llm-judge-design"
related_roadmap_section: "ROADMAP.md § v0.6"
supersedes: "ROADMAP.md mentions 'OpenRouter Fusion' — v0.6 design改为 model-agnostic via env vars (LLM_MODEL + LLM_API_KEY + LLM_BASE_URL). No specific model is hardcoded; the user selects any OpenAI-compatible model via env vars."
---

# alphaloop v0.6 — LLM-as-Judge Evaluator Design

## 0. Context

alphaloop v0.5 (commit `014789638c`, AlphaStrategyAI/alphaloop) ships **6 deterministic
diagnostics** that answer the v1.0 acceptance questions:

1. DSR — Deflated Sharpe Ratio (overfit-adjusted)
2. walk-forward CV — out-of-sample validation
3. cross-source consistency — data integrity
4. vs random — skill vs coin flip
5. vs buy-hold — skill vs passive
6. vs SPY buy-hold — skill vs market

These are *quantitative* — they output numbers and pass/fail booleans.
They do **not** evaluate the *narrative* quality of the backtest report
itself: Is the explanation clear? Are the investment decisions justified?
Are the risks honestly disclosed?

Per **ROADMAP.md § v0.6** and **Jeff Dean's #9 ("accelerate the evaluator")**,
v0.6 adds a 7th diagnostic: an **LLM-as-judge** that scores the report
Markdown on 3 narrative dimensions. The point is to compress the
"human reviewer reads the report → decides if it's honest enough to ship"
step into a fast, repeatable, machine-callable evaluation.

This document is the **design only** — no implementation. It defines the
5 sections the user requested: Goals, Architecture, API, Tests, Risks.

---

## 1. Goals

### 1.1 Primary goal

Add a 7th diagnostic, **`llm_judge()`**, that scores a v1.0-style acceptance
report on three independent dimensions, each scored 1–10:

| Dimension | What it measures | Why it matters |
|-----------|------------------|----------------|
| **Readability** | Can a non-quant reader follow the report and understand what was tested, how, and what was found? | Strategies live or die on whether a PM can read the report in 5 minutes. |
| **Decision合理性** (decision reasonableness) | Are the investment decisions (the strategy's buy/sell/exit rules) internally consistent with the claimed alpha source, and is the alpha source itself plausible? | Catches "this looks like a backtest-overfit curve-fit" before the human reviewer wastes time. |
| **Risk-disclosure completeness** | Does the report disclose: max drawdown, tail risk, regime fragility, transaction cost assumptions, capacity limits, look-ahead risk, survivorship bias? | The single most common failure mode of quant reports is under-disclosed risk. This is the dimension that protects the user. |

### 1.2 Why 3 dimensions, not 1 overall score

User decision: **3 dimensions, not 1 composite**. Rationale baked into design:

- A single "report quality" score is too coarse — it hides *why* a report
  is bad. PMs need to know "this reads great but the risk disclosure is
  catastrophic" so they can ask the right follow-up.
- 3 scores map cleanly to the 3 stakeholder questions: "Can I read it?"
  (readability) / "Should I trust the thesis?" (decision合理性) /
  "What could go wrong?" (risk disclosure).
- Each dimension produces an independent pass/fail using a configurable
  threshold (default ≥ 7/10 → pass). The overall `result.passes` is the
  conjunction (all 3 pass).

### 1.3 Non-goals (explicitly out of scope for v0.6)

- **Replacing** the 6 deterministic diagnostics. The LLM judge is *additive*;
  the 6 numbers stay authoritative for the quantitative questions.
- **Generating** report content. The judge only *scores* an existing report;
  it does not write or rewrite strategies.
- **Choosing** the strategy. The judge is a critic, not a selector.
- **Multi-model ensemble**. ROADMAP.md mentions OpenRouter Fusion; the v0.6
  decision is **single-model via env var** (any OpenAI-compatible model the
  user selects through `LLM_MODEL` — hosted APIs, local vLLM, etc.).
  Ensemble scoring is deferred to v0.7+ if and when inter-rater
  reliability becomes a problem.

### 1.4 Success criteria (measurable)

The design is successful if, after implementation, all of the following hold:

- `alphaloop report` (v0.6) runs the LLM judge on the generated Markdown
  and appends a 4th section "Q7: LLM judge" without changing the 6
  quantitative sections.
- `alphaloop.llm_judge(report_text)` returns a `LLMJudgeResult` with three
  integer scores 1–10, per-dimension reasoning strings, raw model output,
  token usage, and `passes`.
- Test suite grows from 191 → 191 + N (where N ≥ 12 new unit tests + 3
  integration tests); all pass; `pytest` exit code 0.
- With the LLM configured via `LLM_MODEL` and the synthetic universe
  used by `report`, the judge produces a score within `[1, 10]` for each
  dimension on ≥ 99% of runs (no parse failures). Parse failures are loud,
  not silent.
- Total added latency: < 30 s per `report` invocation (typical modern
  LLMs complete a 2k-token prompt in 5–15 s; budget is generous to
  cover slower models).

---

## 2. Architecture

### 2.1 Module layout (proposed)

```
src/alphaloop/
├── diagnostic/
│   ├── __init__.py            # MODIFIED: re-export LLMJudgeResult, llm_judge
│   ├── dsr.py                 # unchanged
│   ├── cv.py                  # unchanged
│   ├── consistency.py         # unchanged
│   ├── benchmarks.py          # unchanged
│   └── judge.py               # NEW: pure function llm_judge() + dataclass
├── judge/
│   ├── __init__.py            # NEW: package init
│   ├── client.py              # NEW: thin OpenAI-compatible HTTP client
│   ├── prompts.py             # NEW: YAML prompt loader + template render
│   └── schemas.py             # NEW: Pydantic / dataclass schemas for I/O
└── cli/
    └── report.py              # MODIFIED: add Q7 section, --judge-model flag
```

**Why split `diagnostic/judge.py` from `judge/`?**

- `diagnostic/judge.py` exposes the **public, pure API**:
  `llm_judge(report: str) -> LLMJudgeResult`. Mirrors how every other
  diagnostic in `diagnostic/` exposes one public function. Tests import
  from here.
- `judge/` is the **infrastructure package** holding the HTTP client,
  prompt templates, and I/O schemas. It is not re-exported from the top
  level — it's an implementation detail of the diagnostic.

This split makes the public API easy to mock in tests: swap the client,
keep the diagnostic logic identical.

### 2.2 Data flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  $ alphaloop report --output reports/v0.md                                │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  run_report(args)  in cli/report.py                                      │
│   1. build synthetic universe (existing)                                 │
│   2. run Q1–Q6 (existing)                                                │
│   3. compose report_markdown = "".join(sections)                         │
│   4. *** NEW *** call llm_judge(report_markdown)                         │
│   5. append "## Q7: LLM Judge" section to markdown                       │
│   6. write file                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  llm_judge(report, model=None, client=None) in diagnostic/judge.py        │
│   - builds the 3-dim prompt via prompts.render_prompt(report)            │
│   - delegates to judge.client.LLMJudgeClient.complete(prompt, model)     │
│   - parses JSON response → LLMJudgeResult                               │
│   - returns result; caller writes to markdown                            │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  judge.client.LLMJudgeClient                                            │
│   - resolves env vars (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL)            │
│   - POSTs to {base_url}/chat/completions (OpenAI-compatible schema)      │
│   - retries on 429/5xx with exponential backoff (3 tries, 1s/2s/4s)     │
│   - returns judge.schemas.RawCompletion(content, usage, model, latency)  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Relationship to existing 6 diagnostics

The 6 deterministic diagnostics and the LLM judge are **parallel siblings**,
not nested:

```
                ┌──────────────────────────────────┐
                │     alphaloop report (CLI)       │
                └──────────────────────────────────┘
                          │           │
              ┌───────────┘           └────────────┐
              ▼                                    ▼
   ┌──────────────────────┐           ┌──────────────────────────┐
   │ 6 quantitative Q's   │           │ Q7: LLM judge (NEW)      │
   │ (DSR, CV, ...)       │           │ 3-dim narrative scoring  │
   │ → numbers, PASS/FAIL │           │ → scores 1-10, PASS/FAIL │
   └──────────────────────┘           └──────────────────────────┘
              │                                    │
              └──────────────┬─────────────────────┘
                             ▼
                ┌──────────────────────────────────┐
                │   markdown report  (combined)    │
                └──────────────────────────────────┘
```

- The 6 quantitative questions are **authoritative** — they determine whether
  the *strategy* is real. The LLM judge does not vote on them.
- The LLM judge is **authoritative** for the 3 narrative dimensions. The
  6 quantitative questions do not vote on them.
- This means a strategy can pass Q1–Q6 (good numbers) but fail Q7
  (badly written report), and vice versa. The user sees both honestly.
- The `report` command writes both sets of results side-by-side in the
  output Markdown; the verdict line at the top is a 7-line summary
  (Q1–Q7).

### 2.4 Failure containment

The LLM call is the only **non-deterministic, network-dependent** step in
the entire `report` pipeline. Failure modes:

| Failure | Behavior | Rationale |
|---------|----------|-----------|
| `LLM_API_KEY` missing | Skip Q7, mark as `SKIP — no API key`. Print warning to stderr. Exit code still 0. | Don't punish users without API keys by failing the whole report. |
| HTTP 4xx (auth/format) | Skip Q7, mark as `SKIP — API error: <code> <msg>`. Exit 0. | Likely a config issue, not a transient failure. Don't retry. |
| HTTP 5xx / 429 | Retry up to 3× with exponential backoff (1s, 2s, 4s). If still failing, skip Q7. | Standard transient-failure handling. |
| Response not valid JSON | Retry once with stricter system prompt. If still failing, skip Q7 and log raw response to `reports/.tmp/`. | One-shot salvage, then move on. |
| Scores out of [1, 10] | Clamp to [1, 10]. Log a warning. Do not skip. | Model occasionally drifts; clamp is safer than fail. |
| Total latency > 60s | Abort, skip Q7. | Don't block the whole report for one slow call. |

The key principle: **a broken LLM call must not break the 6 quantitative
sections**. The deterministic diagnostics are the foundation; the LLM judge
is a layer on top that may degrade gracefully.

### 2.5 Configuration resolution order

The `LLM_MODEL` argument follows this resolution order (highest priority first):

1. CLI flag `--judge-model <name>` (per-invocation override).
2. Environment variable `LLM_MODEL`.
3. **No hardcoded default** — if both CLI flag and `LLM_MODEL` are unset,
   the client constructor raises a clear error and Q7 is SKIPPED. The
   design is deliberately model-agnostic; the user must choose.

Same pattern for `LLM_BASE_URL` (no default — must point to an
OpenAI-compatible endpoint; the provider is the user's choice) and
`LLM_API_KEY` (required, no default — missing key → skip Q7).

---

## 3. API

### 3.1 Public Python API

```python
# src/alphaloop/diagnostic/judge.py

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class DimensionScore:
    """Score and reasoning for a single dimension (1-10)."""
    score: int            # 1-10, clamped
    reasoning: str        # 1-3 sentences from the model
    evidence: str         # quoted text from the report supporting the score


@dataclass
class LLMJudgeResult:
    """Result of an LLM-as-judge evaluation."""
    # Three independent dimension scores
    readability: DimensionScore
    decision_quality: DimensionScore  # named to avoid CJK chars in code
    risk_disclosure: DimensionScore

    # Convenience aggregate: min of the three (conservative)
    @property
    def overall_score(self) -> float:
        return float(min(
            self.readability.score,
            self.decision_quality.score,
            self.risk_disclosure.score,
        ))

    # Pass iff all 3 dimensions meet threshold
    threshold: int = 7
    passes: bool = field(default=False)

    # Observability
    model: str = ""             # actual model that produced the scores
    raw_response: str = ""      # verbatim JSON from the API
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    error: Optional[str] = None # populated iff the call was skipped

    def summary(self) -> str:
        """Markdown-friendly summary, mirrors the format of other diagnostics."""
        verdict = "PASS" if self.passes else ("SKIP" if self.error else "FAIL")
        return (
            f"LLM Judge verdict: {verdict}\n"
            f"  Model: {self.model or '(skipped)'}\n"
            f"  Readability:       {self.readability.score}/10\n"
            f"  Decision quality:  {self.decision_quality.score}/10\n"
            f"  Risk disclosure:   {self.risk_disclosure.score}/10\n"
            f"  Overall (min):     {self.overall_score:.1f}/10\n"
            f"  Threshold:         {self.threshold}/10\n"
            f"  Latency:           {self.latency_ms} ms\n"
            f"  Tokens:            {self.prompt_tokens} prompt + {self.completion_tokens} completion"
        )


class LLMClient(Protocol):
    """Anything that can produce a chat completion. Used for DI in tests."""
    def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> "RawCompletion": ...


@dataclass
class RawCompletion:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    latency_ms: int


def llm_judge(
    report: str,
    *,
    threshold: int = 7,
    model: Optional[str] = None,        # None → env / default
    client: Optional[LLMClient] = None, # None → real HTTP client
) -> LLMJudgeResult:
    """Score a backtest report on 3 narrative dimensions using an LLM.

    Args:
        report: The full Markdown report to evaluate.
        threshold: Minimum score (1-10) required on each dimension
            for `result.passes = True`. Default 7.
        model: Model name to use. If None, resolved from env / default.
        client: Pre-configured LLMClient. If None, a real HTTP client
            is constructed from env vars. Tests inject a fake.

    Returns:
        LLMJudgeResult with 3 dimension scores, overall verdict, and
        observability fields. On any failure, `result.error` is set
        and `result.passes` is False; `summary()` shows SKIP.
    """
```

### 3.2 Prompt template (YAML, loaded at import time)

Stored at `src/alphaloop/judge/prompts/readability.yaml`,
`decision_quality.yaml`, `risk_disclosure.yaml`. The system prompt is
identical across all three; only the rubric differs. A single combined
prompt asks for all 3 scores in one call (cheaper, more consistent).

```yaml
# src/alphaloop/judge/prompts/judge_system.yaml
system: |
  You are an honest, strict reviewer of quantitative trading backtest
  reports. Your job is to score the report on THREE independent
  dimensions, each on a 1-10 scale. You are not evaluating whether
  the strategy is good — other tools do that. You are evaluating the
  QUALITY OF THE REPORT ITSELF: is it clear, is the investment thesis
  sound, and are the risks honestly disclosed?

  You must respond with a single JSON object, nothing else. No
  prose, no markdown fences, no commentary. The JSON schema is:

  {
    "readability": {
      "score": <int 1-10>,
      "reasoning": "<1-3 sentences>",
      "evidence": "<quote from the report>"
    },
    "decision_quality": {
      "score": <int 1-10>,
      "reasoning": "<1-3 sentences>",
      "evidence": "<quote from the report>"
    },
    "risk_disclosure": {
      "score": <int 1-10>,
      "reasoning": "<1-3 sentences>",
      "evidence": "<quote from the report>"
    }
  }

  Scoring rubric (apply per dimension):

  Readability (1-10):
    1-3: Incoherent, jargon-heavy, or missing sections.
    4-6: Understandable but unclear on either the setup, the results,
         or the implications.
    7-8: Clear, well-organized, a non-quant could follow the main thread.
    9-10: Excellent — figures, tables, and callouts make the report
          skim-readable in <5 minutes.

  Decision quality (1-10):
    1-3: The investment thesis is missing, contradicts itself, or
         describes a curve-fit.
    4-6: Thesis is present but only weakly supported by the data shown.
    7-8: Thesis is internally consistent and the data supports it
         (or honestly explains where it doesn't).
    9-10: Thesis is crisp, the alpha source is named, regime
          dependencies are explicit, and the report explains when
          the strategy SHOULD NOT be traded.

  Risk disclosure (1-10):
    1-3: No mention of max drawdown, tail risk, transaction costs,
         capacity, look-ahead bias, or survivorship bias.
    4-6: Mentions some risks but omits at least one critical category.
    7-8: Discloses drawdown, costs, and capacity; mentions
         look-ahead / survivorship as caveats.
    9-10: Comprehensive — includes regime fragility, parameter
          sensitivity, and an explicit "do not trade if X" list.

user: |
  Below is the backtest report to evaluate. Score it honestly on the
  three dimensions above. Cite specific text from the report in your
  evidence field — do not invent quotes.

  <report>
  {report_markdown}
  </report>
```

The template is rendered by `judge.prompts.render_prompt(report)`, which
loads the YAML, substitutes `{report_markdown}`, and returns the messages
list `[{role: "system", ...}, {role: "user", ...}]`.

### 3.3 CLI flag

The `report` command gains one new flag and one new env-var-aware default:

```python
# src/alphaloop/cli/report.py — modifications

parser.add_argument(
    "--judge-model",
    help=(
        "LLM model to use for Q7 (LLM judge). Overrides LLM_MODEL env var. "
        "Use --judge-model=skip to disable Q7 entirely. "
        "No default — must be set via --judge-model or LLM_MODEL env var."
    ),
)
parser.add_argument(
    "--judje-threshold",  # NB: typo is intentional placeholder; will be --judge-threshold
    type=int,
    default=7,
    help="Minimum per-dimension score (1-10) for Q7 to pass. Default: 7.",
)
parser.add_argument(
    "--no-judge",
    action="store_true",
    help="Skip Q7 entirely (equivalent to --judge-model=skip).",
)
```

Resolution inside `run_report`:

```python
def _resolve_judge_settings(args) -> tuple[bool, str, int]:
    """Decide whether to run Q7, and with which model + threshold."""
    if args.no_judge or args.judge_model == "skip":
        return False, "", args.judge_threshold
    model = args.judge_model or os.environ.get("LLM_MODEL")
    if not model or model == "skip":
        return False, "", args.judge_threshold
    return True, model, args.judge_threshold
```

The flag names follow the pattern already established by `--output`,
`--seed`, and `--method`.

### 3.4 Environment variables

| Variable | Required? | Default | Purpose |
|----------|-----------|---------|---------|
| `LLM_API_KEY` | Yes (to run Q7) | — | Bearer token for the LLM API. Missing → Q7 SKIP, exit 0. |
| `LLM_BASE_URL` | No (required to point somewhere) | — | OpenAI-compatible base URL. No default — must point to the user's chosen provider (OpenRouter, Anthropic proxy, local vLLM, Moonshot, etc.). |
| `LLM_MODEL` | Yes (to run Q7) | — | Model name passed to the chat completions endpoint. No hardcoded default — must be set by the user to the name of their chosen OpenAI-compatible model. |
| `LLM_TIMEOUT_S` | No | `30` | Per-request timeout in seconds. |

All four are read once at client construction time. No live re-reads.

---

## 4. Tests

### 4.1 Test layout

```
tests/
├── diagnostic/
│   ├── test_dsr.py           (existing)
│   ├── test_cv.py            (existing)
│   ├── test_consistency.py   (existing)
│   ├── test_benchmarks.py    (existing)
│   └── test_judge.py         # NEW (unit tests for the public API)
├── judge/
│   ├── __init__.py
│   ├── test_client.py        # NEW (HTTP client: retries, env, errors)
│   ├── test_prompts.py       # NEW (YAML loader, template render)
│   └── test_schemas.py       # NEW (response parsing, clamping)
└── integration/
    ├── test_report_cli.py    (existing)
    └── test_report_with_judge.py  # NEW (end-to-end with fake client)
```

Target: **15 new tests** (≥ 12 unit + 3 integration), bringing the total
to 191 + 15 = 206.

### 4.2 Mock strategy

The single most important test design decision: **never make a real HTTP
call in tests**. The `LLMClient` protocol lets us inject a fake.

```python
# tests/judge/conftest.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FakeLLMClient:
    """Records calls, returns scripted responses in order."""
    responses: list[str] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    _idx: int = 0
    # Optional failure injection
    raise_on_call: Optional[Exception] = None
    delay_ms: int = 0

    def complete(self, messages, model, temperature=0.0, max_tokens=1024):
        self.calls.append({
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        if self.raise_on_call is not None:
            raise self.raise_on_call
        if self._idx >= len(self.responses):
            raise AssertionError(
                f"FakeLLMClient exhausted: {self._idx} calls, "
                f"only {len(self.responses)} responses scripted"
            )
        content = self.responses[self._idx]
        self._idx += 1
        return RawCompletion(
            content=content,
            prompt_tokens=sum(len(m["content"]) // 4 for m in messages),
            completion_tokens=len(content) // 4,
            model=model,
            latency_ms=self.delay_ms,
        )
```

For tests that want to verify *what* the judge sends to the LLM, the
`calls` list captures every request. For tests that want to verify *how*
the judge handles LLM output, the `responses` list scripts the LLM's
replies in order.

### 4.3 Unit test cases (test_judge.py)

| # | Test name | What it asserts |
|---|-----------|-----------------|
| 1 | `test_passes_when_all_three_above_threshold` | Inject a response with all scores = 9 → `result.passes = True`. |
| 2 | `test_fails_when_one_dimension_below_threshold` | Inject readability=9, decision=9, risk=5 → `result.passes = False`; `result.overall_score == 5`. |
| 3 | `test_threshold_is_per_dimension_not_average` | Set threshold=8, scores=[10, 10, 7] → fails (risk below 8), even though average = 9. |
| 4 | `test_clamps_out_of_range_scores` | Inject scores=0 and 15 → both clamped to 1 and 10; `result.passes` reflects clamped values. |
| 5 | `test_handles_missing_dimension_in_response` | Inject JSON with only `readability` → other two default to score=1 with reasoning "missing from response"; `result.passes = False`. |
| 6 | `test_invalid_json_returns_error_result` | Inject non-JSON response → `result.error is not None`, `result.passes = False`, summary shows SKIP. |
| 7 | `test_records_latency_and_tokens` | FakeLLMClient with `delay_ms=250` and known content length → `result.latency_ms >= 250` and tokens > 0. |
| 8 | `test_propagates_model_name_from_client` | Verify `result.model` matches what the client returned, not what was requested (catches silent model fallback). |
| 9 | `test_passes_full_report_through_to_prompt` | Use a known report string; verify it appears verbatim in `FakeLLMClient.calls[0]["messages"][-1]["content"]`. |
| 10 | `test_summary_format_matches_other_diagnostics` | Run `result.summary()`, assert it contains "verdict:", "Readability:", "Risk disclosure:", matches the format of `DeflatedSharpeResult.summary()`. |
| 11 | `test_default_threshold_is_7` | Call `llm_judge(report, client=fake)` with no threshold; verify `result.threshold == 7`. |
| 12 | `test_custom_threshold_propagates` | Call with `threshold=9` and all scores=8 → fails. |

### 4.4 Integration tests (test_report_with_judge.py)

These run the *full* `alphaloop report` CLI end-to-end with a fake client:

| # | Test name | What it asserts |
|---|-----------|-----------------|
| 13 | `test_report_includes_q7_section_when_client_provided` | Run `run_report` with a `FakeLLMClient` patched into the env; assert the output Markdown contains "## Q7: LLM Judge" and three numeric scores. |
| 14 | `test_report_skips_q7_when_no_api_key` | Unset `LLM_API_KEY`; run `run_report`; assert Q7 section says SKIP and Q1–Q6 are still present. |
| 15 | `test_report_respects_no_judge_flag` | Run `run_report --no-judge`; assert the output contains no Q7 section. |

Integration tests use `monkeypatch.setenv` / `monkeypatch.delenv` plus a
module-level fixture that patches `alphaloop.cli.report.LLMJudgeClient`
to return a `FakeLLMClient`.

### 4.5 What we are *not* testing (out of scope)

- **Real LLM quality.** We are not asserting that any particular model
  gives "correct" scores on a held-out corpus. That is an eval problem,
  not a unit-test problem — it's deferred to v0.7 when we have a small
  labeled dataset of "obviously good vs obviously bad" reports.
- **Prompt robustness across languages.** We assume the report is in
  English (matching all existing v1.0 report examples). i18n is out.
- **Cost / billing.** Per user decision ("不限制, 先跑跑看"), we are not
  asserting per-call costs. We do record `prompt_tokens` +
  `completion_tokens` in the result so the user can monitor manually.

### 4.6 Verification gate

Per Coder Self-Harness Protocol, before the v0.6 implementation is
declared "done":

```bash
cd /Users/assistant/hermes-lab/alphaloop && \
  python -m pytest tests/ -q --tb=short 2>&1 | tail -30
```

Expected: `206 passed in <time>` (191 existing + 15 new), exit code 0.
Any new failure → loop is not done, return to fix.

---

## 5. Risks

### 5.1 Risk matrix

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | LLM (any model via `LLM_MODEL`) emits non-JSON or partially-JSON responses | Medium | Medium | Single retry with stricter system prompt. If still failing, populate `result.error` and SKIP Q7. Loud logging to `reports/.tmp/`. |
| R2 | LLM score drifts out of [1, 10] range | Low | Low | Clamp scores in `LLMJudgeResult` constructor; warning logged but never fails the report. |
| R3 | Judge bias toward "give everyone 8/10" | Medium | High | (a) System prompt explicitly forbids it; (b) tests inject 1, 5, and 10 responses to verify clamping & propagation; (c) v0.7 will add a small labeled eval set to measure calibration. |
| R4 | API outage / network timeout | Medium | Low | 3 retries with exponential backoff (1s/2s/4s). Total cap 60s. Then SKIP Q7 with error message. The 6 quantitative questions are unaffected. |
| R5 | User runs `report` without setting `LLM_API_KEY` | High | Low | Documented behavior: Q7 SKIP, exit 0, warning to stderr. CI sets a dummy key so test suite doesn't hit the network. |
| R6 | LLM hallucinates quotes in `evidence` field | High | Medium | Add a unit test that injects a clearly-fake quote and asserts `result.passes` is False (catches "judge is fooled by itself"). Document this as a known limitation in v0.6; v0.7 may add quote-verification. |
| R7 | LLM rate limiting (429) under parallel use | Low (v0.6 single-call) → Medium (v0.7 loop) | Medium | Backoff retry handles v0.6. v0.7 will need a token bucket and possibly local queueing. |
| R8 | Cost overruns on the chosen LLM | Low (single call per report) → Medium (v0.7 loop with N reports) | Medium | Per user decision: not limited in v0.6. The `result` records `prompt_tokens` + `completion_tokens` for the user to monitor. v0.7 will add `--max-judge-budget-usd` as a hard cap. |
| R9 | Chinese-character encoding errors in report path / output | Low | Medium | All file I/O uses `encoding="utf-8"` (matches existing pattern in `cli/report.py`). The dimension name in Python is `decision_quality` (no CJK in code); the *display* label is "Decision合理性" — applied only at Markdown render time. |
| R10 | Judge model silently swaps (provider downgrades) | Low | High | `result.model` records the *actual* model name returned by the API, not the requested name. CI asserts these match. |
| R11 | Test suite flakes on real network | N/A (no network in tests) | — | All tests use `FakeLLMClient`. CI sets `LLM_API_KEY=test-dummy-not-used` so the env-var code path is exercised without a real call. |
| R12 | Report Markdown contains injected prompt-injection attempts | Low | Medium | The judge prompt wraps the report in `<report>...</report>` tags and instructs the model to treat content inside as data, not instructions. The system prompt is also placed *before* the user message. (Defense-in-depth, not bulletproof — see § 5.3.) |

### 5.2 Cost & performance budget

Per user decision ("不限制, 先跑跑看"), v0.6 has **no hard budget**.
However, the design records the following to enable future budgeting:

- `result.prompt_tokens` and `result.completion_tokens` (from API response).
- `result.latency_ms` (client-measured wall clock).
- `result.model` (actual model name).

Observed envelope for a v0.5-style 2 KB report (model-agnostic, estimated):

- Prompt: ~1.5 KB system + 2 KB report + 0.5 KB user wrapper ≈ 4 KB ≈ 1000 tokens.
- Completion: ~600 tokens (3 dimension JSON objects with reasoning).
- Latency: 5–15 s typical for most modern LLMs, 30 s tail.
- Cost: depends entirely on the chosen model — anywhere from free
  (local vLLM) to ~$0.01 per report (budget-tier hosted models) to
  several cents (premium models like GPT-5.5 or Claude Sonnet 4).

In v0.7 (loop running ~500 strategy reports), this is ~$5 per loop run.
Acceptable; revisit if/when that becomes painful.

### 5.3 Prompt injection: known limitation

The LLM judge is reading arbitrary Markdown produced by `run_report`.
The Markdown is itself generated by alphaloop's own code (not by a
user-controlled template), so prompt-injection risk in v0.6 is low.
But: a *future* feature (e.g., user-supplied strategy descriptions
embedded in the report) could turn the report into an injection vector.

The current design's defense — wrapping the report in `<report>` tags
and instructing the model to treat it as data — is **defense-in-depth,
not a guarantee**. v0.7 should add a sanitization pass that strips any
"ignore previous instructions"-style strings from the report before
passing it to the judge. For v0.6, this is documented as a known
limitation and not implemented.

### 5.4 Calibration: known limitation

We have no labeled dataset of "good" vs "bad" alphaloop reports to
measure whether the judge actually distinguishes them. The judge
*should* work — the rubric is specific and the prompt is structured —
but we will not know until we run it on real reports and eyeball the
output. **v0.6 ships without calibration evidence**; v0.7 will add a
small manual eval (10–20 reports scored by a human and by the judge,
correlation reported).

This is acceptable per the ROADMAP v0.6 framing: "add the judge so the
research loop can iterate faster." Calibration is a research-loop
problem to solve in v0.7+, not a v0.6 blocker.

### 5.5 Reversibility

The LLM judge is **fully reversible** in v0.6:

- No existing code is deleted; only `diagnostic/__init__.py` and
  `cli/report.py` are modified to add new exports and a new section.
- Removing the judge (reverting to v0.5) is a 2-commit revert:
  remove the Q7 section from `run_report` and un-export the new names
  from `diagnostic/__init__.py`.
- The 6 quantitative diagnostics and their behavior are **unchanged**.

This is intentional. If the judge turns out to be useless or harmful,
we can rip it out without affecting the v1.0 acceptance guarantee.

---

## 6. Out of scope / deferred

For the avoidance of doubt, the following are **not** part of v0.6
and will be tracked separately:

- **Multi-model ensemble / OpenRouter Fusion** (mentioned in ROADMAP.md
  § v0.6 as the original idea). v0.6 ships single-model via env var
  (any OpenAI-compatible model the user selects through `LLM_MODEL`).
  Revisit if inter-rater reliability becomes a problem.
- **Local-model support** (llama.cpp, vLLM). The OpenAI-compatible
  client *happens* to work with local servers via `LLM_BASE_URL`, but
  no local-specific tests, examples, or docs in v0.6.
- **Calibration dataset** — see § 5.4.
- **Prompt-injection sanitization** — see § 5.3.
- **`alphaloop loop` integration** (v0.7 work). v0.6 only adds the
  judge as a callable function and a CLI section in `report`.
- **MCP server exposure** (`alphaloop serve`, v1.0 work). The judge
  function will be MCP-friendly by design (pure function, dataclass
  result) but no `serve` command ships in v0.6.

---

## 7. References

- `ROADMAP.md § v0.6` — original scope statement.
- `src/alphaloop/diagnostic/dsr.py` — pattern reference for result
  dataclass + `summary()` + `passes` field.
- `src/alphaloop/diagnostic/cv.py` — pattern reference for walk-forward
  result dataclass.
- `src/alphaloop/cli/report.py` — pattern reference for Q-section
  composition + CLI flag registration.
- `tests/diagnostic/test_dsr.py` — pattern reference for unit-test
  layout (sys.path insert, plain pytest functions, no fixtures beyond
  `tmp_path`).
- Jeff Dean, *Alpha Engineer* interview (2026-08-07), point #9
  ("accelerate the evaluator") — the motivation for this feature.
- Lilian Weng, *Harness Engineering* (2026-07) — context for why
  "evaluator" is itself a first-class subsystem.
- Karpathy, *LLM Wiki* — the source of the "judge-as-critic" pattern.

---

## 8. Approval gate

Per the loop state file (`alphaloop-v06-llm-judge-design.md`):

> plan step 6: Commander review + forward to user for explicit OK
> plan step 7: (after user OK) Commander dispatch development subagent

**This design doc must be reviewed and explicitly approved by the user
before any implementation work begins.** No code, no tests, no commits,
no PRs — only this document, awaiting OK.
