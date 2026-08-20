# Frozen Grid and Honest Signal Kinds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Walk every frozen `method_parameter_grid` point after a complete hard-gate failure, and stop offering Parkinson/OBV as first-release directional signals.

**Architecture:** Optional `frozen_grid_remaining` on `should_continue` continues with reason `frozen_grid` without expanding the grid or calling `revision_proposer`. `preflight` plus the guided form expose only `DIRECTIONAL_SIGNAL_KINDS`.

**Tech Stack:** existing protocol/runtime, pytest, Playwright e2e, packaged static HTML.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- `FOUND` only from complete `GateEvidence`. PBO failure after a would-be `FOUND` still stops.
- Do not expand a failed search beyond the frozen grid. `expand_failed_search` stays forbidden.
- No FakeWorker in morning e2e. Do not change `HOST_CONSTRAINT`. Do not unfreeze `webui/`.
- `alphaloop.protocol` must not import `runtime`. Use `python3`.

---

### Task 1: Stop rule + protocol walks remaining frozen points

**Files:**
- Modify: `src/alphaloop/protocol/stop.py`
- Modify: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_stop.py`, `tests/protocol/test_protocol_loop.py`

**Interfaces:**
- Consumes: existing `should_continue(*, remaining_time_s, remaining_cost_usd, last_evidence, proposed_kind, stop_reason) -> StopDecision`
- Produces: `should_continue(..., frozen_grid_remaining: int = 0)`; `reason="frozen_grid"` when complete fail and remaining > 0; `run_protocol` passes remaining unevaluated later grid points and does not call `revision_proposer` on that reason

- [ ] **Step 1: Write the failing stop tests**

In `tests/protocol/test_stop.py`, keep `test_failed_gate_does_not_justify_more_search` (omitted remaining still `hard_gate_failed`). Add:

```python
def test_frozen_grid_remaining_continues_after_complete_fail():
    evidence = GateEvidence(
        results=(GateResult(name=HardGateName.DSR, passed=False, detail={}),),
        required=(HardGateName.DSR,),
    )
    decision = should_continue(
        remaining_time_s=100,
        remaining_cost_usd=1.0,
        last_evidence=evidence,
        proposed_kind=RevisionKind.METHOD,
        stop_reason=None,
        frozen_grid_remaining=2,
    )
    assert decision.continue_search is True
    assert decision.queue_for_human is False
    assert decision.reason == "frozen_grid"


def test_explicit_hard_gate_failed_stops_even_with_remaining():
    decision = should_continue(
        remaining_time_s=100,
        remaining_cost_usd=1.0,
        last_evidence=None,
        proposed_kind=RevisionKind.METHOD,
        stop_reason="hard_gate_failed",
        frozen_grid_remaining=2,
    )
    assert decision.continue_search is False
    assert decision.reason == "hard_gate_failed"
```

- [ ] **Step 2: Run stop tests to verify they fail**

Run: `python3 -m pytest tests/protocol/test_stop.py::test_frozen_grid_remaining_continues_after_complete_fail tests/protocol/test_stop.py::test_explicit_hard_gate_failed_stops_even_with_remaining -v`

Expected: FAIL (`frozen_grid_remaining` unexpected keyword, or reason is `hard_gate_failed`).

- [ ] **Step 3: Implement `frozen_grid_remaining` in `should_continue`**

Add keyword-only `frozen_grid_remaining: int = 0` after `stop_reason`. After the budget check and inside the complete-fail METHOD branch, if `frozen_grid_remaining > 0` return `StopDecision(continue_search=True, queue_for_human=False, reason="frozen_grid")`; else keep `hard_gate_failed`. Leave the `FORBIDDEN_CONTINUE_REASONS` check above this branch so an explicit `stop_reason` still stops.

- [ ] **Step 4: Write the failing loop tests**

Replace `test_failed_gate_does_not_walk_the_parameter_grid` with:

```python
def test_complete_fail_walks_the_frozen_parameter_grid(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        return _one_fail(required, **kwargs)

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.NO_EVIDENCE
    assert calls["n"] == 3
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 3


def test_later_frozen_grid_point_can_found(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _one_fail(required, **kwargs)
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    assert calls["n"] == 2


def test_frozen_grid_does_not_call_revision_proposer(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        return _one_fail(required, **kwargs)

    def proposer(spec, doc):
        return {"signal_mechanism": "rsi"}

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        revision_proposer=proposer,
    )
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"] == []
    assert result.research_outcome is ResearchOutcome.NO_EVIDENCE
    assert calls["n"] == 3
```

Keep `test_found_stops_after_first_passing_trial` (still one call). Keep `test_economic_proposal_is_queued_and_not_executed` (incomplete evidence still queues).

- [ ] **Step 5: Run loop tests to verify they fail**

Run: `python3 -m pytest tests/protocol/test_protocol_loop.py::test_complete_fail_walks_the_frozen_parameter_grid tests/protocol/test_protocol_loop.py::test_later_frozen_grid_point_can_found tests/protocol/test_protocol_loop.py::test_frozen_grid_does_not_call_revision_proposer -v`

Expected: FAIL (`calls["n"] == 1` or queued hypotheses non-empty).

- [ ] **Step 6: Implement loop remaining count and proposer guard**

In `run_protocol`, bind `grid = method_parameter_grid(doc.kind)` once. After each trial, set

```python
remaining = sum(
    1
    for later in grid[index + 1 :]
    if _candidate_id(doc.kind, later) not in completed_skip
)
decision = should_continue(
    remaining_time_s=remaining_time,
    remaining_cost_usd=remaining_cost,
    last_evidence=stop_evidence,
    proposed_kind=RevisionKind.METHOD,
    stop_reason=None,
    frozen_grid_remaining=remaining,
)
```

On `decision.continue_search`, call `revision_proposer` only when `decision.reason == "method_repair"`. `frozen_grid` just `continue`s. Leave the `found` / PBO / forbidden-reason branches unchanged.

- [ ] **Step 7: Run protocol unit tests**

Run: `python3 -m pytest tests/protocol/test_stop.py tests/protocol/test_protocol_loop.py -q`

Expected: PASS.

---

### Task 2: Honest kinds in DSL, preflight, form, README, e2e

**Files:**
- Modify: `src/alphaloop/protocol/dsl.py`
- Modify: `src/alphaloop/runtime/preflight.py`
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `README.md`
- Modify: `tests/protocol/test_dsl.py`
- Modify: `tests/runtime/test_preflight.py`
- Modify: `tests/runtime/test_static_console.py`
- Modify: `tests/runtime/test_api.py`
- Modify: `tests/e2e/test_morning_console.py`
- Modify: `mkdocs.yml`

**Interfaces:**
- Consumes: `ALLOWED_KINDS`
- Produces: `FEATURE_KINDS`, `VOLUME_KINDS`, `DIRECTIONAL_SIGNAL_KINDS`; preflight errors for the first two; form options = directional kinds only

- [ ] **Step 1: Write the failing kind / preflight / form tests**

In `tests/protocol/test_dsl.py`:

```python
from alphaloop.protocol.dsl import (
    ALLOWED_KINDS,
    DIRECTIONAL_SIGNAL_KINDS,
    FEATURE_KINDS,
    VOLUME_KINDS,
)

def test_directional_signal_kinds_exclude_feature_and_volume():
    assert FEATURE_KINDS == ("parkinson_hist_vol",)
    assert VOLUME_KINDS == ("obv_slope",)
    assert "parkinson_hist_vol" in ALLOWED_KINDS
    assert "obv_slope" in ALLOWED_KINDS
    assert "parkinson_hist_vol" not in DIRECTIONAL_SIGNAL_KINDS
    assert "obv_slope" not in DIRECTIONAL_SIGNAL_KINDS
    assert len(DIRECTIONAL_SIGNAL_KINDS) == 8
    assert DIRECTIONAL_SIGNAL_KINDS == tuple(
        kind
        for kind in ALLOWED_KINDS
        if kind not in FEATURE_KINDS and kind not in VOLUME_KINDS
    )
```

In `tests/runtime/test_preflight.py`:

```python
def test_parkinson_is_rejected_as_signal_mechanism(tmp_path):
    result = preflight(_spec(signal_mechanism="parkinson_hist_vol"), tmp_path)
    assert result.ok is False
    assert any("feature" in err.lower() for err in result.errors)
    assert result.host_constraint == HOST_CONSTRAINT


def test_obv_slope_is_rejected_without_volume(tmp_path):
    result = preflight(_spec(signal_mechanism="obv_slope"), tmp_path)
    assert result.ok is False
    assert any("volume" in err.lower() for err in result.errors)
    assert result.host_constraint == HOST_CONSTRAINT
```

In `tests/runtime/test_static_console.py`, import `DIRECTIONAL_SIGNAL_KINDS` instead of using `ALLOWED_KINDS` for form options:

```python
from alphaloop.protocol.dsl import DIRECTIONAL_SIGNAL_KINDS

for kind in DIRECTIONAL_SIGNAL_KINDS:
    assert f'value="{kind}"' in html
assert 'value="parkinson_hist_vol"' not in html
assert 'value="obv_slope"' not in html
```

In `tests/runtime/test_api.py`:

```python
def test_preview_run_rejects_parkinson_signal(tmp_path):
    api = _api(tmp_path)
    spec = new_research_spec(
        statement="x",
        economic_logic="x",
        signal_mechanism="parkinson_hist_vol",
        market_scope="AAPL",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=1,
        time_budget_s=10,
        cost_budget_usd=1.0,
    )
    preview = api.preview_run(spec)
    assert preview["ok"] is False
    assert any("feature" in err.lower() for err in preview["errors"])
    assert api.list_jobs()["jobs"] == []
```

In `tests/e2e/test_morning_console.py`, add a sibling of `test_invalid_yaml_shows_preflight_errors_without_job` that pastes a valid-shape YAML with `signal_mechanism: parkinson_hist_vol`, previews, asserts `#preflight-errors` mentions feature or Parkinson, and `GET /v1/jobs` is still empty.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest tests/protocol/test_dsl.py::test_directional_signal_kinds_exclude_feature_and_volume tests/runtime/test_preflight.py::test_parkinson_is_rejected_as_signal_mechanism tests/runtime/test_preflight.py::test_obv_slope_is_rejected_without_volume tests/runtime/test_static_console.py::test_packaged_guided_form_preview_grid_and_job_cards tests/runtime/test_api.py::test_preview_run_rejects_parkinson_signal -q`

Expected: FAIL (imports / assertions).

- [ ] **Step 3: Implement constants, preflight, form, README**

In `src/alphaloop/protocol/dsl.py` after `ALLOWED_KINDS`:

```python
FEATURE_KINDS = ("parkinson_hist_vol",)
VOLUME_KINDS = ("obv_slope",)
DIRECTIONAL_SIGNAL_KINDS = tuple(
    kind for kind in ALLOWED_KINDS if kind not in FEATURE_KINDS and kind not in VOLUME_KINDS
)
```

In `preflight`, after the unknown-kind check:

```python
from alphaloop.protocol.dsl import (
    ALLOWED_KINDS,
    FEATURE_KINDS,
    VOLUME_KINDS,
)

if spec.hypothesis.signal_mechanism in FEATURE_KINDS:
    errors.append(
        "parkinson_hist_vol is a volatility feature, not a directional signal_mechanism"
    )
elif spec.hypothesis.signal_mechanism in VOLUME_KINDS:
    errors.append(
        "obv_slope requires a volume series; first-release snapshots are close-only"
    )
elif spec.hypothesis.signal_mechanism not in ALLOWED_KINDS:
    errors.append(
        "unsupported signal_mechanism: "
        f"{spec.hypothesis.signal_mechanism}"
    )
```

Remove the `parkinson_hist_vol` and `obv_slope` `<option>`s from `src/alphaloop/webui/static/index.html`. In `README.md`, list only the eight directional kinds as first-release `signal_mechanism` values.

Register this requirements file and plan in `mkdocs.yml` nav.

- [ ] **Step 4: Run unit tests then e2e**

Run: `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration -q`

Expected: all passed (skip allowed).

Run: `python3 -m pytest tests/e2e -m e2e -q`

Expected: all passed (skip allowed).

- [ ] **Step 5: Commit**

```bash
git add docs src tests README.md mkdocs.yml
git commit -m "feat(protocol): walk frozen method grid; honest close-only signal kinds"
```
