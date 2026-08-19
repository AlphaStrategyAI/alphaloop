# Overnight Lab Phase 11 — Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the overnight path on every push with unit tests and a shortened local e2e, complete the job-status × research-outcome matrix, and document soak plus five-minute review as a release checklist — without pretending CI can replace a human study or the AlphaStrategy consumer repo.

**Architecture:** Phases 8–10 close semantics, artifacts, and morning submit. Phase 11 adds `.github/workflows/pytest.yml` that installs the package and runs `pytest -m "not integration"`, fills remaining `derive_research_outcome` combinations, adds a fixture-driven overnight workflow test (JobAPI + `run_worker` + sealed files), and a checkpoint kill/resume test that forbids duplicate `trial_id`s. LLM plan snapshots are **N/A** (no in-run planner). Soak and usability stay markdown checklists.

**Tech Stack:** Python 3.9+, pytest, GitHub Actions `ubuntu-latest`, existing contracts/runtime/protocol tests. Do not add Hypothesis.io. Do not add Playwright.

## Global Constraints

- `FOUND` only from complete `GateEvidence`. `llm_judge` is not a hard gate.
- JobStatus and ResearchOutcome stay separate. Failed/cancelled cannot mint `FOUND` unless a previously sealed `FOUND` exists with complete evidence.
- `alphaloop.protocol` must not import `live` / `webui` / `runtime`.
- CI must not hit the network: deselect `integration` and `llm` markers.
- AlphaStrategy consumer import tests stay excluded (other repository).
- Do not enable Cloud Agent environment builds as part of this work.
- Source of truth: `docs/requirements/product-positioning-requirements.md` §12 and `docs/plans/2026-08-19-overnight-lab-remaining-work.md`.

## File Structure

- Create: `.github/workflows/pytest.yml`
- Modify: `tests/contracts/test_status.py` — full status × evidence matrix
- Create: `tests/runtime/test_overnight_e2e.py` — shortened overnight path
- Create: `tests/runtime/test_checkpoint_resume.py` — fault injection
- Modify: `docs/plans/2026-08-19-overnight-lab-remaining-work.md` only if the release checklist should live there (prefer this file’s § Release checklist)
- Test: `tests/runtime/test_import_graph.py` (run, do not weaken)

## Out of scope

- Real overnight soak on three OS families
- Recruiting users for a 5-minute study
- AlphaStrategy repo CI
- MCP adapter
- Hypothesis library property tests (use explicit accounting instead)

---

### Task 1: Status × outcome matrix

**Files:**
- Modify: `tests/contracts/test_status.py`

**Interfaces:**
- Consumes: `derive_research_outcome(job_status, evidence_complete, all_gates_passed, sealed=None)`
- Produces: parametrized coverage of every `JobStatus` with complete/incomplete × all-pass/any-fail, plus sealed `FOUND` only when evidence is complete

- [ ] **Step 1: Write the failing test**

Add to `tests/contracts/test_status.py`:

```python
@pytest.mark.parametrize(
    "status, complete, passed, expected",
    [
        (JobStatus.QUEUED, False, False, ResearchOutcome.NONE),
        (JobStatus.QUEUED, True, True, ResearchOutcome.NONE),
        (JobStatus.RUNNING, False, False, ResearchOutcome.NONE),
        (JobStatus.RUNNING, True, True, ResearchOutcome.NONE),
        (JobStatus.COMPLETED, True, True, ResearchOutcome.FOUND),
        (JobStatus.COMPLETED, True, False, ResearchOutcome.NO_EVIDENCE),
        (JobStatus.COMPLETED, False, True, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.COMPLETED, False, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.FAILED, True, True, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.FAILED, True, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.FAILED, False, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.CANCELLED, True, False, ResearchOutcome.INCONCLUSIVE),
        (JobStatus.CANCELLED, False, True, ResearchOutcome.INCONCLUSIVE),
    ],
)
def test_status_outcome_matrix(status, complete, passed, expected):
    assert (
        derive_research_outcome(status, complete, passed)
        is expected
    )


def test_cancelled_cannot_claim_found_without_seal():
    assert (
        derive_research_outcome(
            JobStatus.CANCELLED,
            evidence_complete=True,
            all_gates_passed=True,
        )
        is ResearchOutcome.INCONCLUSIVE
    )
```

Existing `test_sealed_found_survives_cancel` and `test_sealed_found_requires_complete_evidence` stay. If any matrix row already fails, **do not** change production status rules to make a green table that contradicts §6.3 — fix the test expectation only after reading `derive_research_outcome`. The rows above match current `src/alphaloop/contracts/status.py`.

- [ ] **Step 2: Run the new tests, expect PASS or FAIL**

Run: `python -m pytest tests/contracts/test_status.py -v`

Expected: PASS on current `main` (the matrix documents the contract). If a row fails, stop and align the test with §6.3, then implement the contract — do not weaken `FOUND`.

This task is still required: it is the §12 “every valid and invalid combination” suite. A passing-first test is acceptable here because the function already exists; do not delete coverage.

- [ ] **Step 3: No production change unless a row contradicts §6.3**

- [ ] **Step 4: Re-run, expect PASS**

- [ ] **Step 5: Commit**

```bash
git add tests/contracts/test_status.py
git commit -m "test(contracts): cover job status and research outcome matrix"
```

---

### Task 2: Ledger `n_trials` accounting

**Files:**
- Test: `tests/protocol/test_protocol_loop.py`

**Interfaces:**
- Consumes: `run_protocol` + `gate_runner` capturing `n_trials`
- Produces: after a method-repair run with two incomplete-then-pass trials, unique ledger `trial_id` count equals last `n_trials` and equals `len(runner.calls)`

Phase 9 already adds ledger-based `n_trials`. This task is the §12 multiple-testing accounting test. If Phase 9 is not merged, this test belongs with Phase 9 Task 2 — **do not duplicate**. If Phase 9 is merged, add:

```python
def test_n_trials_matches_unique_ledger_ids(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        if len(seen) == 1:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    lines = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    ids = [json.loads(line)["trial_id"] for line in lines]
    assert seen[-1] == len(set(ids)) == len(ids)
    assert seen == [1, 2]
```

- [ ] **Step 1: Write the test** (skip creating it if `test_method_repair_retries_and_counts_trials` plus Phase 9 `test_n_trials_counts_existing_ledger_rows` already imply the equality — still add this explicit assertion; it is the property the PRD names)

- [ ] **Step 2: Run, expect FAIL if Phase 9 skipped ledger uniqueness; else PASS**

Run: `python -m pytest tests/protocol/test_protocol_loop.py::test_n_trials_matches_unique_ledger_ids -v`

- [ ] **Step 3: Implement only if FAIL** — uniqueness of `trial_id` in `loop.py` (Phase 9 retry path)

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add tests/protocol/test_protocol_loop.py src/alphaloop/protocol/loop.py
git commit -m "test(protocol): n_trials matches unique trial-ledger ids"
```

If nothing failed and `loop.py` is unchanged:

```bash
git add tests/protocol/test_protocol_loop.py
git commit -m "test(protocol): n_trials matches unique trial-ledger ids"
```

---

### Task 3: Checkpoint kill / resume without duplicate trials

**Files:**
- Create: `tests/runtime/test_checkpoint_resume.py`

**Interfaces:**
- Consumes: `run_protocol` with a `gate_runner` that raises `KeyboardInterrupt` (or `RuntimeError`) after the first `on_trial`, then a second `run_protocol` with `completed_trial_ids` from the last complete checkpoint
- Produces: ledger has unique `trial_id`s; second run does not re-evaluate the first id

This is unit-level fault injection (no OS `kill`). Do not require a live subprocess.

- [ ] **Step 1: Write the failing test**

Create `tests/runtime/test_checkpoint_resume.py`:

```python
from __future__ import annotations

import json

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, IncompleteEvidenceError, evaluate_hard_gates
from alphaloop.protocol.loop import run_protocol
from alphaloop.runtime.checkpoint import Checkpoint, load_latest_complete, write_checkpoint
from tests.protocol.test_protocol_loop import _prices, _spec


def test_second_start_skips_checkpointed_trial_ids(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seq = {"n": 0}

    def on_trial(payload):
        seq["n"] += 1
        write_checkpoint(
            layout,
            Checkpoint(
                seq=seq["n"],
                complete=True,
                payload={
                    "phase": "protocol",
                    "completed_trial_ids": list(payload["completed_trial_ids"]),
                },
            ),
        )
        raise RuntimeError("injected crash")

    def incomplete(required, **kwargs):
        raise IncompleteEvidenceError("missing walk_forward")

    try:
        run_protocol(
            _spec(),
            layout,
            prices=_prices(),
            buy_hold_prices=_prices()["AAPL"],
            benchmark_prices=_prices()["AAPL"],
            gate_runner=incomplete,
            on_trial=on_trial,
        )
    except RuntimeError:
        pass

    ckpt = load_latest_complete(layout)
    assert ckpt is not None
    done = tuple(ckpt.payload["completed_trial_ids"])
    before = layout.trial_ledger.read_text(encoding="utf-8")

    def pass_all(required, **kwargs):
        rows = tuple(GateResult(name=name, passed=True, detail={}) for name in required)
        return evaluate_hard_gates(required, rows)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=pass_all,
        completed_trial_ids=done,
        on_trial=None,
    )
    after = layout.trial_ledger.read_text(encoding="utf-8")
    ids = [json.loads(line)["trial_id"] for line in after.strip().splitlines() if line.strip()]
    assert len(ids) == len(set(ids))
    assert before.strip().splitlines()[0] in after
```

- [ ] **Step 2: Run, expect FAIL if Phase 9 skip/on_trial is missing**

Run: `python -m pytest tests/runtime/test_checkpoint_resume.py::test_second_start_skips_checkpointed_trial_ids -v`

Expected: FAIL (`TypeError: unexpected keyword argument 'on_trial'`) until Phase 9 lands. **Execute this plan after Phase 9.**

- [ ] **Step 3: No extra production code if Phase 9 already implements skip + on_trial**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/test_checkpoint_resume.py
git commit -m "test(runtime): resume skips checkpointed trial ids without duplicates"
```

---

### Task 4: Shortened overnight e2e

**Files:**
- Create: `tests/runtime/test_overnight_e2e.py`
- Create: `tests/fixtures/overnight/prices.parquet` generated in the test (do not commit a large binary; write it in `tmp_path`)

**Interfaces:**
- Consumes: `JobStore` + `run_worker` + fixture prices (300 bdays, AAPL/MSFT/SPY)
- Produces: after `run_worker`, `RunLayout` has `research-spec.yaml` (already), `manifest.yaml`, `trial-ledger.jsonl`, `candidates.parquet`, `evidence/gates.json` **or** `report.md` with `INCONCLUSIVE`/`NO_EVIDENCE`/`FOUND`, never a LoopRunner letter. Deterministic: two runs with the same spec+parquet+seed write byte-identical `gates.json` when evidence exists.

Use `hard_gates=("dsr",)` and a short series if full gates are too slow. Cap runtime: the test must finish in well under 30 seconds on CI.

- [ ] **Step 1: Write the failing test**

Create `tests/runtime/test_overnight_e2e.py`:

```python
from __future__ import annotations

import json

import pandas as pd
import yaml

from alphaloop.contracts.artifacts import RunLayout, DatasetRef, hash_bytes
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.contracts.status import ResearchOutcome
from alphaloop.runtime.worker import run_worker


def _prices_frame():
    idx = pd.bdate_range("2018-01-01", periods=260)
    return pd.DataFrame(
        {
            "AAPL": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "MSFT": 100.0 + pd.Series(range(260), index=idx, dtype=float),
            "SPY": 100.0 + pd.Series(range(260), index=idx, dtype=float),
        }
    )


def test_shortened_overnight_writes_required_artifacts(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_e2e" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="12-1 momentum works",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_e2e", sha256=digest),
    )
    run_id = "j_e2e"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(spec.to_dict()), encoding="utf-8")
    assert run_worker(run_id, tmp_path) == 0
    assert layout.manifest.is_file()
    assert layout.trial_ledger.is_file()
    assert layout.candidates.is_file()
    assert layout.report.is_file()
    report = layout.report.read_text(encoding="utf-8")
    assert any(token in report for token in ("FOUND", "NO_EVIDENCE", "INCONCLUSIVE"))
    assert "target found" not in report
    first = (layout.evidence / "gates.json").read_bytes() if (layout.evidence / "gates.json").is_file() else None
    layout2 = RunLayout(tmp_path / "j_e2e_b")
    layout2.run_dir.mkdir()
    layout2.research_spec.write_text(yaml.safe_dump(spec.to_dict()), encoding="utf-8")
    assert run_worker("j_e2e_b", tmp_path) == 0
    if first is not None:
        second = (layout2.evidence / "gates.json").read_bytes()
        assert first == second
```

If Phase 9 is missing `dataset=` / writers, this test fails until Phase 9 lands. **Execute after Phase 9.**

- [ ] **Step 2: Run, expect FAIL until artifacts exist**

Run: `python -m pytest tests/runtime/test_overnight_e2e.py::test_shortened_overnight_writes_required_artifacts -v`

Expected: FAIL on missing `manifest.yaml` before Phase 9; PASS after.

- [ ] **Step 3: No extra production code if Phase 9 writers exist**

If `gates.json` is missing because DSR is incomplete on the fixture, the report must still contain `INCONCLUSIVE` — that is a valid overnight outcome. Do not loosen gates to force `FOUND`.

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/test_overnight_e2e.py
git commit -m "test(runtime): shortened overnight path writes sealed artifacts"
```

---

### Task 5: GitHub Actions pytest

**Files:**
- Create: `.github/workflows/pytest.yml`

**Interfaces:**
- Consumes: repo at `push` / `pull_request`
- Produces: one job `pytest` on `ubuntu-latest`, Python 3.11
  - `pip install -e ".[dev]"` plus `pyarrow` if not already a core dependency after Phase 9
  - `python -m pytest -m "not integration and not llm" --ignore=tests/integration`
  - `PYTHONPATH` not required if `pip install -e .` works
  - Do not deploy Pages from this workflow

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/pytest.yml`:

```yaml
name: pytest

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: pytest-${{ github.ref }}
  cancel-in-progress: true

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install package
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"
          python -m pip install pyarrow

      - name: Run unit tests
        run: python -m pytest -m "not integration and not llm" --ignore=tests/integration
```

If Phase 9 already added `pyarrow` to `[project] dependencies`, the extra `pip install pyarrow` line is harmless. Keep it so the workflow does not depend on merge order.

- [ ] **Step 2: Run the same command locally**

Run:

```
python -m pytest -m "not integration and not llm" --ignore=tests/integration
```

Expected: PASS (or the same failures you must fix before claiming the workflow is green). Do not add `continue-on-error`.

- [ ] **Step 3: No application code**

- [ ] **Step 4: Confirm import graph still in the default pytest path** (`tests/runtime/test_import_graph.py` is not under `tests/integration`)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pytest.yml
git commit -m "ci: run unit tests excluding integration and live LLM"
```

---

### Task 6: Release checklist (soak + five-minute review)

**Files:**
- Modify: none if `docs/plans/2026-08-19-overnight-lab-remaining-work.md` already has §8 Release checklist (it does as of 2026-08-19)

**Interfaces:** none in code. Do **not** add a pytest named `test_usability_study` that asserts `True`.

- [ ] **Step 1: Confirm remaining-work §8 lists soak, five-minute review, and AlphaStrategy-out-of-repo**

Open `docs/plans/2026-08-19-overnight-lab-remaining-work.md` and check the three bullets exist. If a later edit removed them, restore that section verbatim from the 2026-08-19 design.

- [ ] **Step 2: No pytest for soak or usability**

- [ ] **Step 3: No application code**

- [ ] **Step 4: `python3 -m mkdocs build --strict` if MkDocs is installed**

Expected: exit 0.

- [ ] **Step 5: Commit only if docs changed**

```bash
git add docs/plans/2026-08-19-overnight-lab-remaining-work.md
git commit -m "docs: record soak and five-minute review as release checks"
```
