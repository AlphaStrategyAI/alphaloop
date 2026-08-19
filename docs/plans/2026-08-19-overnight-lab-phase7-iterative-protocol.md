# Overnight Lab Phase 7 — Iterative Protocol Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `run_protocol` a real overnight loop: honor `should_continue`, search method-only parameter variants, count every trial in DSR `n_trials`, and queue economic hypothesis changes for a human instead of executing them.

**Architecture:** Phase 3 already has a constrained DSL, independent market profiles, hard-gate adapters, and stop *rules*. The worker still evaluates one candidate and discards `should_continue(...)`. Phase 7 keeps those modules and changes `protocol/loop.py` plus a small `protocol/search.py` parameter grid. No Web UI, checkpoint resume, dataset snapshot, or CI soak in this plan.

**Tech Stack:** Python 3.9+, pytest, pandas (existing), Phase 1 contracts, Phase 3 `protocol.stop` / `protocol.dsl` / `protocol.gates`.

## Global Constraints

- `FOUND` only from complete `GateEvidence` via `outcome_from_evidence`. `llm_judge` is not a hard gate.
- JobStatus and ResearchOutcome stay separate.
- Method repairs may continue; economic-logic / signal_mechanism / market_scope / benchmark / hard-gate changes are queued, not executed in the same run.
- Negative OOS, cost failure, failed hard gate, regime instability, and expanding an already failed search do not justify more parameter search (`FORBIDDEN_CONTINUE_REASONS`).
- Complete passing evidence stops the loop (`FOUND`). Complete failing evidence stops the loop (`NO_EVIDENCE`).
- `n_trials` passed into `run_hard_gates` equals the number of trial-ledger rows written so far (including the current trial).
- Frozen `ResearchSpec` is never mutated.
- `alphaloop.protocol` must not import `alphaloop.live`, `alphaloop.webui`, or `alphaloop.runtime`.
- Do not rewrite diagnostic or engineer math.
- Tests use synthetic prices only (no network).
- Source of truth: `docs/requirements/product-positioning-requirements.md` §6 and `docs/plans/overnight-research-lab-refactor.md`.

## File Structure

- Create: `src/alphaloop/protocol/search.py` — frozen-kind parameter grids
- Modify: `src/alphaloop/protocol/stop.py` — stop when last evidence is complete and all gates passed
- Modify: `src/alphaloop/protocol/loop.py` — iterate, honor `StopDecision`, write recommendations
- Modify: `src/alphaloop/protocol/__init__.py` — export `method_parameter_grid` if tests import it from the package
- Test: `tests/protocol/test_stop.py`
- Test: `tests/protocol/test_search.py`
- Test: `tests/protocol/test_protocol_loop.py`
- Modify: `tests/runtime/test_import_graph.py` only if a new protocol file would import a forbidden package (it must not)

## Out of scope (later plans)

- Checkpoint payload resume (`load_latest_complete` in the worker)
- Writing `manifest.yaml`, `candidates.parquet`, `report.md`
- Content-addressed dataset fail-closed in the worker
- Packaged Web submit / preflight / progress polling
- CI shortened overnight workflow, soak benchmark, usability study

---

### Task 1: Stop after a complete passing evidence set

**Files:**
- Modify: `src/alphaloop/protocol/stop.py`
- Test: `tests/protocol/test_stop.py`

**Interfaces:**
- Consumes: existing `should_continue(*, remaining_time_s, remaining_cost_usd, last_evidence, proposed_kind, stop_reason) -> StopDecision`
- Produces: when `last_evidence` is not `None`, `last_evidence.complete` is true, and `last_evidence.all_passed` is true, return `StopDecision(continue_search=False, queue_for_human=False, reason="found")` **before** the method-repair fallthrough. Keep the existing hard-gate-failed, budget, economic, and forbidden-reason branches.

- [ ] **Step 1: Write the failing test**

Add to `tests/protocol/test_stop.py`:

```python
def test_complete_pass_stops_as_found():
    evidence = GateEvidence(
        results=(GateResult(name=HardGateName.DSR, passed=True, detail={}),),
        required=(HardGateName.DSR,),
    )
    decision = should_continue(
        remaining_time_s=100,
        remaining_cost_usd=1.0,
        last_evidence=evidence,
        proposed_kind=RevisionKind.METHOD,
        stop_reason=None,
    )
    assert decision.continue_search is False
    assert decision.queue_for_human is False
    assert decision.reason == "found"
```

Keep `test_method_repair_with_incomplete_evidence_continues` unchanged (incomplete evidence still continues).

- [ ] **Step 2: Run the new test, expect FAIL**

Run: `python3 -m pytest tests/protocol/test_stop.py::test_complete_pass_stops_as_found -v`

Expected: FAIL because `should_continue` currently falls through to `reason="method_repair"` with `continue_search=True`.

- [ ] **Step 3: Implement the FOUND branch**

In `should_continue`, after the economic / forbidden-reason / budget checks and **before** the complete-fail `hard_gate_failed` branch, add:

```python
    if last_evidence is not None and last_evidence.complete and last_evidence.all_passed:
        return StopDecision(
            continue_search=False,
            queue_for_human=False,
            reason="found",
        )
```

- [ ] **Step 4: Run stop tests**

Run: `python3 -m pytest tests/protocol/test_stop.py -v`

Expected: PASS, including the new test and existing hard-gate-failed / budget / economic tests.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/stop.py tests/protocol/test_stop.py
git commit -m "fix(protocol): stop search when hard gates all pass"
```

---

### Task 2: Method-only parameter grid for the frozen DSL kind

**Files:**
- Create: `src/alphaloop/protocol/search.py`
- Test: `tests/protocol/test_search.py`

**Interfaces:**
- Consumes: `ALLOWED_KINDS` from `alphaloop.protocol.dsl`
- Produces:
  - `method_parameter_grid(kind: str) -> tuple[dict[str, object], ...]`
  - First element is always `{}` (the frozen kind's default parameters)
  - `momentum_12_1` → `({}, {"skip": 42}, {"skip": 63})`
  - `rsi` → `({}, {"window": 21}, {"window": 28})`
  - `roc` → `({}, {"window": 40})`
  - every other allowed kind → `({},)`
  - unknown kind → `({},)` (the loop already treats unknown kind as INCONCLUSIVE before search)
  - Every dict is a **method** revision: keys are factor kwargs only. Never include `signal_mechanism`, `economic_logic`, `market_scope`, `benchmark`, or `hard_gates`.

- [ ] **Step 1: Write failing tests** in `tests/protocol/test_search.py`

```python
from alphaloop.protocol.search import method_parameter_grid
from alphaloop.protocol.stop import RevisionKind, classify_revision
from alphaloop.contracts.research_spec import Hypothesis


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        statement="s",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
    )


def test_grid_starts_with_defaults():
    grid = method_parameter_grid("momentum_12_1")
    assert grid[0] == {}
    assert {"skip": 42} in grid


def test_grid_entries_are_method_revisions():
    frozen = _hypothesis()
    for params in method_parameter_grid("momentum_12_1"):
        kind = classify_revision(frozen, ("dsr",), params)
        assert kind is RevisionKind.METHOD


def test_unknown_kind_has_only_defaults():
    assert method_parameter_grid("NotAClass") == ({},)
```

- [ ] **Step 2: Run tests, expect FAIL**

Run: `python3 -m pytest tests/protocol/test_search.py -v`

Expected: FAIL with `ModuleNotFoundError: alphaloop.protocol.search`.

- [ ] **Step 3: Implement `search.py`**

```python
from __future__ import annotations

from typing import Mapping


_GRIDS: dict[str, tuple[dict[str, object], ...]] = {
    "momentum_12_1": ({}, {"skip": 42}, {"skip": 63}),
    "rsi": ({}, {"window": 21}, {"window": 28}),
    "roc": ({}, {"window": 40}),
}


def method_parameter_grid(kind: str) -> tuple[dict[str, object], ...]:
    grid = _GRIDS.get(kind, ({},))
    return tuple(dict(params) for params in grid)
```

Do not import `runtime`, `webui`, or `live`.

- [ ] **Step 4: Tests PASS**

Run: `python3 -m pytest tests/protocol/test_search.py tests/runtime/test_import_graph.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/search.py tests/protocol/test_search.py
git commit -m "feat(protocol): add method-only parameter grids for frozen DSL kinds"
```

---

### Task 3: Drive `run_protocol` from `should_continue` and the parameter grid

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_protocol_loop.py`

**Interfaces:**
- Consumes: `should_continue`, `RevisionKind`, `method_parameter_grid`, existing `run_protocol` signature
- Produces: `run_protocol` still returns `ProtocolResult`. Behavior:
  1. Parse the frozen kind once. Unknown kind → `INCONCLUSIVE`, no candidate, as today.
  2. Walk `method_parameter_grid(doc.kind)` in order. Rebuild the `StrategyDocument` with that trial's `parameters` (kind, universe, profile stay frozen).
  3. Before each trial, if `clock` is provided and `spec.time_budget_s - clock() <= 0`, or `remaining_cost_usd` is `<= 0`, stop with `INCONCLUSIVE` when evidence is missing/incomplete, else `outcome_from_evidence` for the last sealed complete set.
  4. Append one trial-ledger JSONL row **before** calling the gate runner: `trial_id`, `kind`, `parameters`, `revision` (`"none"` on the first trial, `"method"` afterwards), `timestamp`.
  5. Call `gate_runner` / `run_hard_gates` with `n_trials` equal to the number of ledger lines now on disk.
  6. `IncompleteEvidenceError`: do not write `gates.json`; keep `last_evidence=None` for the stop check (or an incomplete `GateEvidence` if you construct one). Continue only when `should_continue` says so.
  7. Complete evidence: write `evidence/gates.json` (overwrite with the latest complete set).
  8. Call `should_continue` with `proposed_kind=RevisionKind.METHOD` and `stop_reason=None` unless a later task injects an explicit reason. **Use the returned `StopDecision`.**
  9. `reason == "found"` → `COMPLETED` + `FOUND`, stop.
  10. `reason == "hard_gate_failed"` or any `FORBIDDEN_CONTINUE_REASONS` → `COMPLETED` + `NO_EVIDENCE`, stop. Do not walk the rest of the grid.
  11. `continue_search is True` → next grid entry.
  12. Grid exhausted without `FOUND`: if last evidence is complete and failed → `NO_EVIDENCE`; otherwise `INCONCLUSIVE`.
  13. Never mutate `spec`.

Keep the public `run_protocol(...)` keyword arguments the same so `tests/runtime/test_worker.py` does not break.

- [ ] **Step 1: Write failing tests** in `tests/protocol/test_protocol_loop.py`

Reuse `_spec`, `_prices`. Add:

```python
def test_found_stops_after_first_passing_trial(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
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
    assert calls["n"] == 1
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 1


def test_failed_gate_does_not_walk_the_parameter_grid(tmp_path):
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
    assert calls["n"] == 1


class _IncompleteThenPass:
    def __init__(self):
        self.calls = []

    def __call__(self, required, **kwargs):
        self.calls.append(kwargs["n_trials"])
        if len(self.calls) == 1:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)


def test_method_repair_retries_and_counts_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    runner = _IncompleteThenPass()
    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    assert result.research_outcome is ResearchOutcome.FOUND
    assert runner.calls == [1, 2]
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 2
    assert json.loads(ledger[0])["revision"] == "none"
    assert json.loads(ledger[1])["revision"] == "method"
    assert json.loads(ledger[1])["parameters"] == {"skip": 42}
    evidence = evidence_from_dict(json.loads((layout.evidence / "gates.json").read_text()))
    assert evidence.all_passed is True


def test_budget_exhaustion_after_incomplete_is_inconclusive(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    ticks = {"n": 0}

    def clock():
        ticks["n"] += 1
        return 0 if ticks["n"] == 1 else 1000

    result = run_protocol(
        _spec(time_budget_s=10),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_incomplete,
        clock=clock,
    )
    assert result.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert not (layout.evidence / "gates.json").exists()
```

Tighten `test_protocol_found_from_passing_gates` to `len(ledger) == 1` (still compatible with the new first test). Leave `test_protocol_inconclusive_without_complete_gates` as-is: a runner that always raises `IncompleteEvidenceError` walks the grid then ends `INCONCLUSIVE` without `gates.json`.

- [ ] **Step 2: Run the new tests, expect FAIL**

Run:

```bash
python3 -m pytest tests/protocol/test_protocol_loop.py::test_method_repair_retries_and_counts_trials tests/protocol/test_protocol_loop.py::test_failed_gate_does_not_walk_the_parameter_grid -v
```

Expected: FAIL — current `run_protocol` always uses `n_trials=1`, discards `should_continue`, and never retries.

- [ ] **Step 3: Implement the loop**

In `loop.py`:

- Import `method_parameter_grid` from `.search`.
- After a successful `parse_strategy_document`, iterate `for index, parameters in enumerate(method_parameter_grid(doc.kind))`.
- Build a per-trial document with `dataclasses.replace(doc, parameters=dict(parameters))` (import `replace` from `dataclasses`).
- Compute remaining time as `float(spec.time_budget_s if clock is None else spec.time_budget_s - clock())` at the **start** of each iteration (including the first). If remaining time or remaining cost `<= 0` **before the first trial**, do not call the gate runner; return `INCONCLUSIVE`.
- After a trial, call `should_continue` and branch on `decision.reason` / `decision.continue_search` as specified in Interfaces.
- Write `recommendations.json` once at the start with `{"queued_hypotheses": []}` (Task 4 overwrites it when queueing).

Do not import `alphaloop.loop`. Do not call `LoopRunner`.

- [ ] **Step 4: Run protocol + related runtime tests**

Run:

```bash
python3 -m pytest tests/protocol/test_protocol_loop.py tests/protocol/test_stop.py tests/protocol/test_search.py tests/runtime/test_worker.py tests/runtime/test_complete_from_artifacts.py tests/runtime/test_import_graph.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/loop.py tests/protocol/test_protocol_loop.py
git commit -m "feat(protocol): iterate method repairs and honor stop decisions"
```

---

### Task 4: Queue economic revisions without executing them

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_protocol_loop.py`

**Interfaces:**
- Consumes: `classify_revision`, `should_continue`, existing `run_protocol`
- Produces: optional keyword `revision_proposer: Optional[Callable[[ResearchSpec, StrategyDocument], Optional[Mapping[str, object]]]] = None`
  - Default `None` means “only the method grid” (production worker stays method-only).
  - After a trial that did **not** already stop with `found` / `hard_gate_failed` / forbidden reason / budget, if `revision_proposer` returns a mapping, run `classify_revision(spec.hypothesis, spec.success_criteria.hard_gates, proposed)`.
  - `RevisionKind.ECONOMIC`: append `{**proposed, "queued_reason": "economic_change_queued"}` to `queued_hypotheses`, write `recommendations.json`, **do not** parse or evaluate that proposal, return the outcome of the last executed trial (typically `INCONCLUSIVE` or `NO_EVIDENCE`).
  - `RevisionKind.METHOD`: ignore the proposer for that step and continue the grid (the grid is the only method search in this phase).
  - Frozen spec fields remain unchanged.

- [ ] **Step 1: Write the failing test**

```python
def test_economic_proposal_is_queued_and_not_executed(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        raise IncompleteEvidenceError("missing walk_forward")

    def proposer(spec, doc):
        return {"signal_mechanism": "rsi"}

    spec = _spec()
    result = run_protocol(
        spec,
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        revision_proposer=proposer,
    )
    assert spec.hypothesis.signal_mechanism == "momentum_12_1"
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"][0]["signal_mechanism"] == "rsi"
    assert result.research_outcome is ResearchOutcome.INCONCLUSIVE
    assert calls["n"] == 1
```

- [ ] **Step 2: Run the test, expect FAIL**

Run: `python3 -m pytest tests/protocol/test_protocol_loop.py::test_economic_proposal_is_queued_and_not_executed -v`

Expected: FAIL — `run_protocol` does not accept `revision_proposer` and always writes an empty queue.

- [ ] **Step 3: Implement the hook**

After a non-terminal trial, if `revision_proposer` is not `None`:

```python
    proposed = revision_proposer(spec, trial_doc)
    if proposed:
        kind = classify_revision(
            spec.hypothesis,
            spec.success_criteria.hard_gates,
            proposed,
        )
        decision = should_continue(
            remaining_time_s=remaining_time,
            remaining_cost_usd=remaining_cost,
            last_evidence=last_evidence,
            proposed_kind=kind,
            stop_reason=None,
        )
        if decision.queue_for_human:
            queued = [{"queued_reason": decision.reason, **dict(proposed)}]
            layout.recommendations.write_text(
                json.dumps({"queued_hypotheses": queued}, indent=2) + "\n",
                encoding="utf-8",
            )
            return ProtocolResult(
                job_status=JobStatus.COMPLETED,
                research_outcome=(
                    outcome_from_evidence(JobStatus.COMPLETED, last_evidence)
                    if last_evidence is not None and last_evidence.complete
                    else ResearchOutcome.INCONCLUSIVE
                ),
                candidate_id=candidate_id,
                evidence=last_evidence if last_evidence is not None and last_evidence.complete else None,
            )
```

Default production path (`revision_proposer is None`) must still match Task 3 tests.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/protocol/ tests/runtime/test_worker.py tests/runtime/test_morning.py -q`

Expected: PASS. `tests/runtime/test_morning.py::test_revisions_and_queued_hypotheses` still constructs its own `recommendations.json`.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/loop.py tests/protocol/test_protocol_loop.py
git commit -m "feat(protocol): queue economic revisions without executing them"
```

---

### Task 5: Regression sweep and docs pointers

**Files:**
- Modify: `docs/plans/overnight-research-lab-refactor.md` only if Phase 7 bullets drifted during implementation
- Modify: `docs/requirements/product-positioning-requirements.md` §13 only if the Phase 7 link is missing

**Interfaces:** none. This task is the review gate.

- [ ] **Step 1: Full non-integration pytest**

Run: `python3 -m pytest tests/ -m "not integration" -q`

Expected: all previously passing tests still pass; new protocol tests included. Do not skip failures.

- [ ] **Step 2: Confirm import graph**

Run: `python3 -m pytest tests/runtime/test_import_graph.py -v`

Expected: PASS. `search.py` and `loop.py` contain no `alphaloop.live` / `alphaloop.webui` / `alphaloop.runtime` imports.

- [ ] **Step 3: Confirm docs links**

`docs/plans/overnight-research-lab-refactor.md` Phase 7 section and `docs/requirements/product-positioning-requirements.md` §13 both link to this file. `mkdocs.yml` lists `plans/2026-08-19-overnight-lab-phase7-iterative-protocol.md`.

Run: `python3 -m mkdocs build --strict` if MkDocs is installed; otherwise skip with a note.

- [ ] **Step 4: Commit only if docs still need a fix**

```bash
git add docs/plans/overnight-research-lab-refactor.md docs/requirements/product-positioning-requirements.md mkdocs.yml
git commit -m "docs: point Phase 7 iterative protocol at the implementation plan"
```

If those files are already correct, skip the commit.

---

## Spec coverage (self-review)

| PRD item | Task |
| --- | --- |
| §6.1 method repairs recorded | Task 3 ledger `revision` field |
| §6.1 economic change needs a future run | Task 4 |
| §6.1 multiple-testing accounting via `n_trials` | Task 3 `n_trials == ledger length` |
| §6.2 epistemic stop / forbidden continue | Task 1 + Task 3 hard-gate-failed short-circuit |
| §6.2 do not continue until profitable | Task 3 does not walk the grid after a complete fail |
| Frozen spec | Task 3 + Task 4 assertions |
| §12 property-style “every trial counted” | Task 3 `test_method_repair_retries_and_counts_trials` (not Hypothesis/pytest-property; sufficient for this phase) |
| Web submit, artifacts, checkpoint resume, CI soak | Explicitly out of scope |
