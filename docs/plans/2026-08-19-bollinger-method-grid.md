# Bollinger Band literature method grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search `bollinger_zscore` on Bollinger’s 20/2 intermediate default and 10/1.5 short-term setting, keeping `{}` as the in-repo 20/1.5 default.

**Architecture:** Add three dicts to `method_parameter_grid`. Do not change the factor function. Protocol already walks the grid.

**Tech Stack:** Existing protocol search + pytest. Overnight worker for integration/e2e. Playwright matrix unchanged except that it must still pass.

**Spec:** `docs/requirements/2026-08-19-bollinger-method-grid.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`.
- Do not grid `invert`. That is an economic change.
- Do not change RSI/ROC/MACD/momentum grids.
- Morning e2e: real daemon + Chromium; no `FakeWorker` on the research path.
- Plans live under `docs/plans/`.

---

### Task 1: Bollinger search grid

**Files:**
- Modify: `src/alphaloop/protocol/search.py`
- Modify: `tests/protocol/test_search.py`
- Modify: `tests/engineer/test_mean_reversion.py`

**Interfaces:**
- Produces: `method_parameter_grid("bollinger_zscore")` is exactly the three dicts in R1

- [ ] **Step 1: Write the failing tests**

In `tests/protocol/test_search.py`:

```python
def test_bollinger_grid_is_literature_variants():
    grid = method_parameter_grid("bollinger_zscore")
    assert grid[0] == {}
    assert {"window": 20, "num_std": 2.0} in grid
    assert {"window": 10, "num_std": 1.5} in grid
    assert len(grid) == 3
    frozen = _hypothesis()
    for params in grid:
        assert "invert" not in params
        assert classify_revision(frozen, ("dsr",), params) is RevisionKind.METHOD
```

In `tests/engineer/test_mean_reversion.py`:

```python
def test_bollinger_short_window_weights_in_01():
    p = _make_prices()
    w = bollinger_zscore(p, window=10, num_std=1.5)
    assert w.between(0, 1).all()
```

(`_make_prices` already exists in that file.)

- [ ] **Step 2: Run to fail**

Run: `python3 -m pytest tests/protocol/test_search.py::test_bollinger_grid_is_literature_variants tests/engineer/test_mean_reversion.py::test_bollinger_short_window_weights_in_01 -v`

Expected: FAIL — Bollinger grid is `({})`.

- [ ] **Step 3: Implement**

In `src/alphaloop/protocol/search.py` add:

```python
    "bollinger_zscore": (
        {},
        {"window": 20, "num_std": 2.0},
        {"window": 10, "num_std": 1.5},
    ),
```

Do not change `bollinger_zscore()` defaults.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/protocol/test_search.py tests/engineer/test_mean_reversion.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/search.py tests/protocol/test_search.py tests/engineer/test_mean_reversion.py
git commit -m "feat(search): walk Bollinger 20/2 and 10/1.5 as method repairs"
```

---

### Task 2: Protocol ledger and overnight worker

**Files:**
- Modify: `tests/protocol/test_protocol_loop.py`
- Modify: `tests/runtime/test_overnight_e2e.py`
- Modify: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `method_parameter_grid("bollinger_zscore")` length 3
- Produces: three trial ledger rows for a bollinger spec

- [ ] **Step 1: Integration test**

Read `test_n_trials_matches_unique_ledger_ids` in `tests/protocol/test_protocol_loop.py` and add a sibling that uses `signal_mechanism="bollinger_zscore"` and a passing `gate_runner`. Assert the ledger has **3** unique `trial_id` values and that `n_trials` passed into the runner on the last call is 3.

If `_spec()` hard-codes momentum, override `signal_mechanism`.

```python
def test_bollinger_protocol_walks_three_method_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    seen: list[int] = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        if len(seen) < 3:
            raise IncompleteEvidenceError("missing walk_forward")
        return _all_pass(required, **kwargs)

    result = run_protocol(
        _spec(signal_mechanism="bollinger_zscore"),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
    )
    ids = [
        json.loads(line)["trial_id"]
        for line in layout.trial_ledger.read_text().splitlines()
        if line.strip()
    ]
    assert len(set(ids)) == 3
    assert seen == [1, 2, 3]
    assert result.research_outcome is ResearchOutcome.FOUND
```

FOUND here is from a stub gate runner on the third trial, which is how existing protocol tests work. Do not use this pattern in morning e2e. Complete pass/fail still stops the grid (PRD §6.2).

- [ ] **Step 2: Overnight worker test**

```python
def test_bollinger_overnight_walks_three_trials(tmp_path):
    frame = _prices_frame()
    parquet = tmp_path / "datasets" / "ds_bb" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet)
    digest = hash_bytes(parquet.read_bytes())
    spec = new_research_spec(
        statement="Bollinger mean reversion works in US large caps net of costs",
        economic_logic="prices revert after stretching below the lower band",
        signal_mechanism="bollinger_zscore",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=30,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_bb", sha256=digest),
    )
    api = _api(tmp_path)
    created = api.create_run(spec)
    run_id = created["run_id"]
    layout = RunLayout(tmp_path / run_id)
    assert run_worker(run_id, tmp_path) == 0
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "bollinger_zscore" for row in rows)
```

Confirm the ledger schema uses `parameters`. If the field name differs, match the existing ledger writer in `src/alphaloop/protocol/loop.py`.

- [ ] **Step 3: Playwright smoke**

In `tests/e2e/test_morning_console.py`, add a job that submits `signal_mechanism: bollinger_zscore` with `hard_gates: [dsr]` and `time_budget_s: 60`. Wait for a legal outcome. Assert the trial ledger has at least one `bollinger_zscore` row. Do not assert `FOUND`.

```python
def test_bollinger_job_walks_three_trials(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_bb_e2e")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.fill(
        "#spec-yaml",
        _spec_yaml(
            dataset,
            statement="Bollinger mean reversion works in US large caps net of costs",
            signal_mechanism="bollinger_zscore",
            time_budget_s=60,
        ),
    )
    page.click("#submit-job")
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "bollinger_zscore" for row in rows)
    assert "target found" not in page.content()
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/protocol/test_protocol_loop.py::test_bollinger_protocol_walks_three_method_trials tests/runtime/test_overnight_e2e.py::test_bollinger_overnight_walks_three_trials -v`

Expected: PASS

Then: `python3 -m pytest -m "not e2e and not llm" -q` then `python3 -m pytest tests/e2e -m e2e -q`

Expected: unit/integration green; e2e previous skip retained plus the new bollinger job.

- [ ] **Step 5: Commit**

```bash
git add tests/protocol/test_protocol_loop.py tests/runtime/test_overnight_e2e.py tests/e2e/test_morning_console.py
git commit -m "test: walk three Bollinger method trials overnight and on morning e2e"
```

---

## Self-review

1. **Spec coverage:** R1 grid → Task 1. R2 unchanged defaults → Task 1 does not touch `mean_reversion.py` implementation. Acceptance integration/e2e → Task 2.
2. **Placeholders:** none.
3. **Types:** `num_std` is `2.0` / `1.5` floats matching `bollinger_zscore(num_std: float)`.
