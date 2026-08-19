# Overnight Lab Phase 9 — Durability and Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fail closed on missing or mismatched dataset snapshots, resume from checkpoint without duplicating trials or resetting `n_trials`, and write `manifest.yaml`, `candidates.parquet`, and `report.md` as views of sealed evidence. Add top-level `alphaloop replay` that re-emits `report.md` without re-running gates.

**Architecture:** Phase 8 makes gate math see strategy weights. Phase 9 teaches the worker to load a content-addressed parquet from `<data_dir>/datasets/<dataset_id>/prices.parquet`, call `require_dataset`, and skip synthetic RNG prices. `run_protocol` stays import-clean: the worker passes `completed_trial_ids` and an `on_trial` callback that writes checkpoints. Protocol counts `n_trials` from unique ledger `trial_id`s after the current row is present. `report.md` is generated from `gates.json` + outcome; it is not a source of truth.

**Tech Stack:** Python 3.9+, pytest, pandas, pyarrow (add to `[project] dependencies` if missing — `loop/persistence.py` already requires it for v0.7 parquet), Phase 1 `RunLayout` / `DatasetRef` / `require_dataset`.

## Global Constraints

- `FOUND` only from complete `GateEvidence`. `llm_judge` is not a hard gate.
- JobStatus and ResearchOutcome stay separate.
- `alphaloop.protocol` must not import `alphaloop.live`, `alphaloop.webui`, or `alphaloop.runtime`.
- Do not rewrite diagnostic or engineer math.
- Missing or mismatched snapshot bytes → `INCONCLUSIVE`, never synthetic prices, never `FOUND`.
- `report.md` is a view of sealed evidence, not the source of truth.
- `n_trials` passed into `run_hard_gates` equals the number of unique `trial_id` values in `trial-ledger.jsonl` after the current trial row exists (including retries that reuse a row).
- Frozen `ResearchSpec` is never mutated. Optional `dataset` is omitted from the `spec_id` hash when `None` so existing IDs stay stable.
- Tests use fixture parquet / synthetic Series passed into `run_protocol` (no network). Worker tests must not rely on RNG prices.
- Source of truth: `docs/requirements/product-positioning-requirements.md` §7 / §12 and `docs/plans/2026-08-19-overnight-lab-remaining-work.md`.

## File Structure

- Modify: `src/alphaloop/contracts/research_spec.py` — optional `dataset: DatasetRef | None`
- Modify: `src/alphaloop/protocol/loop.py` — `completed_trial_ids`, `on_trial`, ledger-based `n_trials`, do not truncate existing `recommendations.json`
- Modify: `src/alphaloop/runtime/worker.py` — load snapshot, fail closed, checkpoint callback; delete `_load_or_synthesize_prices` RNG branch
- Modify: `src/alphaloop/runtime/preflight.py` — declared dataset must exist and match hash
- Create: `src/alphaloop/runtime/artifacts_io.py` — manifest, parquet, report writers
- Create: `src/alphaloop/runtime/dataset_cache.py` — resolve cache path + `require_dataset`
- Modify: `src/alphaloop/cli/jobs.py` and `src/alphaloop/cli/main.py` — `alphaloop replay`
- Modify: `pyproject.toml` — add `pyarrow>=14` to `[project] dependencies` if not already present
- Test: `tests/contracts/test_research_spec.py`
- Test: `tests/protocol/test_protocol_loop.py`
- Test: `tests/runtime/test_worker.py`
- Test: `tests/runtime/test_preflight.py`
- Test: `tests/runtime/test_artifacts_io.py`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/runtime/test_import_graph.py` (unchanged expectations)

## Out of scope (later plans)

- Packaged Web submit / preflight form / progress polling (Phase 10)
- CI pytest workflow, soak, usability study (Phase 11)
- Default `revision_proposer` / LLM planner
- Changing v0.7 `alphaloop loop replay`

---

### Task 1: Optional `DatasetRef` on `ResearchSpec` without shifting existing `spec_id`s

**Files:**
- Modify: `src/alphaloop/contracts/research_spec.py`
- Modify: `src/alphaloop/contracts/__init__.py` only if `DatasetRef` is not already exported (it is)
- Test: `tests/contracts/test_research_spec.py`

**Interfaces:**
- Consumes: existing `new_research_spec(...)` hash payload (`hypothesis`, `success_criteria`, `seed`, `time_budget_s`, `cost_budget_usd`)
- Produces: `ResearchSpec.dataset: Optional[DatasetRef] = None`
  - `new_research_spec(..., dataset: Optional[DatasetRef] = None)`
  - When `dataset is None`, the SHA payload **must not** include a `dataset` key (existing `spec_id` values stay stable)
  - When `dataset` is set, the payload includes `"dataset": {"dataset_id": ..., "sha256": ...}`
  - `from_dict` reads optional `dataset` mapping; `None` / missing / empty → `dataset is None`
  - `to_dict` via `asdict` may include `"dataset": None`; `from_dict` must treat that as unset

- [ ] **Step 1: Write the failing tests**

Add to `tests/contracts/test_research_spec.py`:

```python
from alphaloop.contracts.artifacts import DatasetRef


def test_existing_spec_id_unchanged_without_dataset():
    spec = _spec()
    again = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
    )
    assert spec.spec_id == again.spec_id
    assert getattr(spec, "dataset", None) is None


def test_dataset_changes_spec_id_and_round_trips():
    ref = DatasetRef(dataset_id="ds_fixture", sha256="a" * 64)
    with_ds = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="12-1 momentum",
        market_scope="US large-cap equities",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
        dataset=ref,
    )
    assert with_ds.dataset == ref
    assert with_ds.spec_id != _spec().spec_id
    assert ResearchSpec.from_dict(with_ds.to_dict()) == with_ds
```

- [ ] **Step 2: Run the new tests, expect FAIL**

Run: `python -m pytest tests/contracts/test_research_spec.py::test_existing_spec_id_unchanged_without_dataset tests/contracts/test_research_spec.py::test_dataset_changes_spec_id_and_round_trips -v`

Expected: FAIL (`TypeError: unexpected keyword argument 'dataset'` or `AttributeError: dataset`).

- [ ] **Step 3: Write minimal implementation**

Add field and kwarg. Include dataset in the hash dict only when not `None`. In `from_dict`, parse:

```python
raw_ds = payload.get("dataset")
dataset = None
if isinstance(raw_ds, dict) and raw_ds.get("dataset_id") and raw_ds.get("sha256"):
    dataset = DatasetRef(dataset_id=str(raw_ds["dataset_id"]), sha256=str(raw_ds["sha256"]))
```

Pass `dataset` into both the reconstructed `ResearchSpec` and the `new_research_spec` expected-id check.

- [ ] **Step 4: Run spec tests, expect PASS**

Run: `python -m pytest tests/contracts/test_research_spec.py -v`

Expected: PASS. `test_round_trip_yaml_dict_preserves_fields` still passes.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/contracts/research_spec.py tests/contracts/test_research_spec.py
git commit -m "feat(contracts): optional DatasetRef on ResearchSpec without shifting empty-dataset ids"
```

---

### Task 2: Ledger-based `n_trials`, skip completed ids, keep recommendations

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_protocol_loop.py`

**Interfaces:**
- Consumes: existing `run_protocol(...)`
- Produces: new kwargs
  - `completed_trial_ids: Sequence[str] = ()` — skip these grid entries (do not append, do not run gates)
  - `on_trial: Optional[Callable[[Mapping[str, Any]], None]] = None` — called after each evaluated trial with `{"trial_id": str, "completed_trial_ids": tuple[str, ...], "n_trials": int}`
- `n_trials` passed to `gate_runner` = number of unique `trial_id` values in the ledger after the current row is present
- If `layout.recommendations` already exists, do **not** overwrite it with `{"queued_hypotheses": []}` at start
- If the current `trial_id` is already a ledger line (retry after crash before checkpoint), do **not** append a second line
- Do not import `alphaloop.runtime`

- [ ] **Step 1: Write the failing tests**

Add to `tests/protocol/test_protocol_loop.py`:

```python
def test_n_trials_counts_existing_ledger_rows(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_prior", "kind": "momentum_12_1", "parameters": {}})
        + "\n",
        encoding="utf-8",
    )
    seen = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        return _all_pass(required, **kwargs)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        completed_trial_ids=(),
    )
    assert seen[0] == 2


def test_completed_trial_ids_are_skipped(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    from alphaloop.protocol.loop import _candidate_id

    first_id = _candidate_id("momentum_12_1", {})
    calls = {"n": 0}

    def runner(required, **kwargs):
        calls["n"] += 1
        return _incomplete(required, **kwargs)

    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        completed_trial_ids=(first_id,),
    )
    ledger = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert calls["n"] >= 1
    assert json.loads(ledger[0])["trial_id"] != first_id


def test_existing_recommendations_are_not_truncated(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.recommendations.write_text(
        json.dumps({"queued_hypotheses": [{"statement": "keep me"}]}) + "\n",
        encoding="utf-8",
    )
    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
    )
    rec = json.loads(layout.recommendations.read_text(encoding="utf-8"))
    assert rec["queued_hypotheses"][0]["statement"] == "keep me"


def test_retry_does_not_duplicate_ledger_row(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    from alphaloop.protocol.loop import _candidate_id

    first_id = _candidate_id("momentum_12_1", {})
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": first_id, "kind": "momentum_12_1", "parameters": {}})
        + "\n",
        encoding="utf-8",
    )
    run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=_all_pass,
        completed_trial_ids=(),
    )
    lines = layout.trial_ledger.read_text(encoding="utf-8").strip().splitlines()
    ids = [json.loads(line)["trial_id"] for line in lines]
    assert ids.count(first_id) == 1
```

If `_candidate_id` is private, duplicate the hash in the test instead of importing it:

```python
import hashlib

def _cid(kind, parameters):
    encoded = json.dumps({"kind": kind, "parameters": dict(parameters)}, sort_keys=True).encode()
    return "c_" + hashlib.sha256(encoded).hexdigest()[:16]
```

Prefer exporting nothing new. Copy the 16-char hash helper in the test file.

- [ ] **Step 2: Run the new tests, expect FAIL**

Run:

```
python -m pytest tests/protocol/test_protocol_loop.py::test_n_trials_counts_existing_ledger_rows tests/protocol/test_protocol_loop.py::test_completed_trial_ids_are_skipped tests/protocol/test_protocol_loop.py::test_existing_recommendations_are_not_truncated tests/protocol/test_protocol_loop.py::test_retry_does_not_duplicate_ledger_row -v
```

Expected: FAIL (`TypeError: unexpected keyword argument 'completed_trial_ids'` and/or `seen[0] == 1` and/or truncated recommendations).

- [ ] **Step 3: Write minimal implementation**

In `run_protocol`:

1. Add kwargs `completed_trial_ids: Sequence[str] = ()` and `on_trial: Optional[Callable[[Mapping[str, Any]], None]] = None`.
2. Replace the unconditional `recommendations.write_text(empty)` with: write empty JSON only when `layout.recommendations` is missing.
3. Helper `_ledger_rows(layout) -> list[dict]` and `_ledger_ids(rows) -> list[str]`.
4. In the grid loop, `if candidate_id in set(completed_trial_ids): continue`.
5. Append a ledger row only when `candidate_id` is not already in `_ledger_ids`.
6. `n_trials = len(dict.fromkeys(_ledger_ids(_ledger_rows(layout))))` after ensuring the current id is present.
7. After gates (success or `IncompleteEvidenceError`), if `on_trial` is not `None`, call it with the mapping above. Include the current id in `completed_trial_ids` only after the trial **finished evaluating** (including incomplete evidence). Skipping a crash mid-gate is the worker's problem: it must not add the id to the checkpoint until `on_trial` runs.

Keep Phase 8 return math and stop order.

- [ ] **Step 4: Run protocol tests, expect PASS**

Run: `python -m pytest tests/protocol -v`

Expected: PASS. `test_method_repair_retries_and_counts_trials` still sees `[1, 2]` on a fresh layout.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/protocol/loop.py tests/protocol/test_protocol_loop.py
git commit -m "feat(protocol): resume-safe trial ledger and n_trials from unique ids"
```

---

### Task 3: Worker fail-closed dataset load and checkpoint callback

**Files:**
- Create: `src/alphaloop/runtime/dataset_cache.py`
- Modify: `src/alphaloop/runtime/worker.py`
- Test: `tests/runtime/test_worker.py`

**Interfaces:**
- Consumes: `DatasetRef`, `require_dataset`, `load_latest_complete`, `write_checkpoint`
- Produces:
  - `dataset_parquet_path(data_dir: Path, dataset_id: str) -> Path` = `data_dir / "datasets" / dataset_id / "prices.parquet"`
  - `load_prices(data_dir: Path, spec: ResearchSpec) -> tuple[dict[str, pd.Series], pd.Series, pd.Series]`
    - If `spec.dataset is None` **and** `layout` run-dir `prices.parquet` is also missing: raise `DatasetUnavailableError` (do not RNG)
    - If `spec.dataset` is set: read cache parquet bytes, `require_dataset(spec.dataset, blob)`, then `pd.read_parquet`
    - If `spec.dataset is None` but `run_dir / "prices.parquet"` exists (legacy test fixture): load it without a hash (tests may still drop a file next to the spec). Prefer cache when `dataset` is set.
  - `_run_protocol` catches `DatasetUnavailableError` / `DatasetMismatchError` and writes no `gates.json` (supervisor then completes as `INCONCLUSIVE`)
  - `preflight`: when `spec.dataset` is not `None`, require
    `data_dir / "datasets" / spec.dataset.dataset_id / "prices.parquet"`
    exists and `require_dataset` succeeds. Missing → error
    `"dataset snapshot is unavailable"`. Mismatch → error containing
    `"hash mismatch"`. Unset `dataset` does not fail preflight.
  - `clock` / `remaining_cost_usd` from Phase 8 stay
  - `completed_trial_ids` from `load_latest_complete(layout).payload["completed_trial_ids"]` or `()`
  - `on_trial` writes `Checkpoint(seq=previous+1, complete=True, payload={"phase": "protocol", "completed_trial_ids": list(...)})`
- Delete the `numpy.random.default_rng` synthetic branch

- [ ] **Step 1: Write the failing tests**

Add helpers at the top of `tests/runtime/test_worker.py` if missing:

```python
import pandas as pd
from alphaloop.contracts.artifacts import DatasetRef, hash_bytes
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.runtime.checkpoint import write_checkpoint, Checkpoint


def _write_prices_parquet(path, prices: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(prices).to_parquet(path)
```

Add:

```python
def test_run_worker_without_snapshot_does_not_synthesize(tmp_path):
    run_id = "j_nosnap"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    assert run_worker(run_id, tmp_path) == 0
    assert not (layout.evidence / "gates.json").exists()
    assert not layout.trial_ledger.exists() or layout.trial_ledger.read_text() == ""


def test_run_worker_rejects_hash_mismatch(tmp_path):
    idx = pd.bdate_range("2018-01-01", periods=30)
    frame = pd.DataFrame({"AAPL": range(30), "MSFT": range(30), "SPY": range(30)}, index=idx)
    blob_path = tmp_path / "datasets" / "ds_bad" / "prices.parquet"
    _write_prices_parquet(blob_path, {c: frame[c] for c in frame.columns})
    spec = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr",),
        seed=7,
        time_budget_s=60,
        cost_budget_usd=1.0,
        dataset=DatasetRef(dataset_id="ds_bad", sha256="0" * 64),
    )
    run_id = "j_mismatch"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(spec.to_dict()), encoding="utf-8")
    assert run_worker(run_id, tmp_path) == 0
    assert not (layout.evidence / "gates.json").exists()


def test_run_worker_resumes_from_checkpoint_ids(monkeypatch, tmp_path):
    captured = {}

    def fake_run_protocol(spec, layout, **kwargs):
        captured["completed"] = kwargs.get("completed_trial_ids")
        captured["on_trial"] = kwargs.get("on_trial")
        return None

    monkeypatch.setattr("alphaloop.protocol.loop.run_protocol", fake_run_protocol)
    run_id = "j_resume"
    layout = RunLayout(tmp_path / run_id)
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    idx = pd.bdate_range("2018-01-01", periods=30)
    _write_prices_parquet(
        layout.run_dir / "prices.parquet",
        {"AAPL": pd.Series(range(30), index=idx, dtype=float),
         "MSFT": pd.Series(range(30), index=idx, dtype=float),
         "SPY": pd.Series(range(30), index=idx, dtype=float)},
    )
    write_checkpoint(
        layout,
        Checkpoint(
            seq=3,
            complete=True,
            payload={"phase": "protocol", "completed_trial_ids": ["c_already"]},
        ),
    )
    assert run_worker(run_id, tmp_path) == 0
    assert captured["completed"] == ["c_already"] or captured["completed"] == ("c_already",)
    captured["on_trial"]({"trial_id": "c_new", "completed_trial_ids": ("c_already", "c_new"), "n_trials": 2})
    latest = load_latest_complete(layout)
    assert latest is not None
    assert latest.seq == 4
    assert latest.payload["completed_trial_ids"][-1] == "c_new"
```

Add to `tests/runtime/test_preflight.py`:

```python
from alphaloop.contracts.artifacts import DatasetRef
from alphaloop.contracts.research_spec import new_research_spec


def test_declared_dataset_must_exist(tmp_path):
    spec = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
        dataset=DatasetRef(dataset_id="ds_missing", sha256="a" * 64),
    )
    result = preflight(spec, tmp_path)
    assert result.ok is False
    assert any("dataset" in err.lower() for err in result.errors)
    assert result.host_constraint == HOST_CONSTRAINT


def test_declared_dataset_hash_must_match(tmp_path):
    parquet = tmp_path / "datasets" / "ds_x" / "prices.parquet"
    parquet.parent.mkdir(parents=True)
    parquet.write_bytes(b"not-a-real-parquet-but-hashed")
    spec = new_research_spec(
        statement="12-1 momentum works in US large caps net of costs",
        economic_logic="past winners continue",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL, MSFT",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward", "vs_benchmark"),
        seed=7,
        time_budget_s=3600,
        cost_budget_usd=5.0,
        dataset=DatasetRef(dataset_id="ds_x", sha256="0" * 64),
    )
    result = preflight(spec, tmp_path)
    assert result.ok is False
    assert any("hash" in err.lower() for err in result.errors)
```

Update `test_run_worker_default_path_writes_protocol_artifacts` to write `prices.parquet` next to the spec before `run_worker`. Without that file the default path must no longer create a ledger from RNG data.

- [ ] **Step 2: Run the new tests, expect FAIL**

Run:

```
python -m pytest tests/runtime/test_worker.py::test_run_worker_without_snapshot_does_not_synthesize tests/runtime/test_worker.py::test_run_worker_rejects_hash_mismatch tests/runtime/test_worker.py::test_run_worker_resumes_from_checkpoint_ids -v
```

Expected: FAIL (today the no-snapshot path synthesizes prices and likely writes a ledger).

- [ ] **Step 3: Write minimal implementation**

`dataset_cache.py`:

```python
class DatasetUnavailableError(FileNotFoundError):
    pass


def dataset_parquet_path(data_dir: Path, dataset_id: str) -> Path:
    return Path(data_dir) / "datasets" / dataset_id / "prices.parquet"
```

`load_prices` reads bytes, `require_dataset` when `spec.dataset` is set, parses columns to `dict[str, pd.Series]`, primary = first universe ticker, benchmark = `spec.hypothesis.benchmark` or primary.

`_run_protocol`:

```python
    ckpt = load_latest_complete(layout)
    done = tuple((ckpt.payload.get("completed_trial_ids") or []) if ckpt else ())
    seq = ckpt.seq if ckpt else 0

    def on_trial(payload):
        nonlocal seq
        seq += 1
        write_checkpoint(
            layout,
            Checkpoint(
                seq=seq,
                complete=True,
                payload={
                    "phase": "protocol",
                    "completed_trial_ids": list(payload["completed_trial_ids"]),
                },
            ),
        )

    try:
        prices, buy_hold, benchmark = load_prices(layout, spec, data_dir=layout.run_dir.parent)
    except (DatasetUnavailableError, DatasetMismatchError):
        return
    started = time.monotonic()
    run_protocol(..., completed_trial_ids=done, on_trial=on_trial, clock=..., remaining_cost_usd=...)
```

Pass `data_dir` as `layout.run_dir.parent` (the Job API data root). Cache path is sibling `datasets/`.

Keep writing the initial seq=1 heartbeat checkpoint **or** stop writing a dummy `{"phase": "protocol"}` checkpoint before the loop so resume ids are not empty. Preferred: do **not** write a complete checkpoint before the first trial. Heartbeat-only is enough. Update `test_run_worker_checkpoints_and_heartbeats_before_dry_run` — that test uses `runner_factory` (LoopRunner stopgap) and may keep the old seq=1 checkpoint. Do not break the stopgap path.

In `preflight`, after existing checks:

```python
dataset = getattr(spec, "dataset", None)
if dataset is not None:
    path = Path(data_dir) / "datasets" / dataset.dataset_id / "prices.parquet"
    if not path.is_file():
        errors.append("dataset snapshot is unavailable")
    else:
        try:
            require_dataset(dataset, path.read_bytes())
        except DatasetMismatchError:
            errors.append("dataset snapshot hash mismatch")
```

- [ ] **Step 4: Run worker tests, expect PASS**

Run: `python -m pytest tests/runtime/test_worker.py tests/runtime/test_preflight.py tests/runtime/test_import_graph.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/dataset_cache.py src/alphaloop/runtime/worker.py src/alphaloop/runtime/preflight.py tests/runtime/test_worker.py tests/runtime/test_preflight.py
git commit -m "feat(runtime): fail closed on dataset snapshots and resume completed trial ids"
```

---

### Task 4: `manifest.yaml`, `candidates.parquet`, `report.md`

**Files:**
- Create: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/runtime/worker.py` — call writers after `run_protocol`
- Modify: `pyproject.toml` — `pyarrow>=14` in `[project] dependencies` if missing
- Test: `tests/runtime/test_artifacts_io.py`

**Interfaces:**
- Consumes: `RunLayout`, `ResearchSpec`, `ProtocolResult` (or outcome + optional evidence dict)
- Produces:
  - `write_manifest(layout, spec, *, engine_version: str) -> Path` YAML with keys:
    `engine_version` (use `alphaloop.__version__` → `0.5.0`), `seed`, `spec_id`,
    `dataset_id` (or `null`), `dataset_sha256` (or `null`), `time_budget_s`, `cost_budget_usd`
  - `write_candidates_parquet(layout) -> Path` — one row per ledger line: `trial_id`, `kind`, `parameters` (JSON string), `revision`
  - `write_report(layout, *, research_outcome: str, stop_reason: str | None) -> Path` Markdown that includes the outcome token, stop reason, and each `gates.json` result `name: pass|fail`. No LLM prose. Header `# Research conclusion`
- Call all three at the end of `_run_protocol` even on `INCONCLUSIVE` (report still says `INCONCLUSIVE`; parquet may be empty)

- [ ] **Step 1: Write the failing tests**

Create `tests/runtime/test_artifacts_io.py`:

```python
from __future__ import annotations

import json

import pandas as pd
import yaml

from alphaloop import __version__
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, evidence_to_dict, evaluate_hard_gates
from alphaloop.runtime.artifacts_io import write_candidates_parquet, write_manifest, write_report
from tests.runtime.test_supervisor import _spec


def test_manifest_records_engine_seed_and_null_dataset(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    spec = _spec()
    write_manifest(layout, spec, engine_version=__version__)
    payload = yaml.safe_load(layout.manifest.read_text(encoding="utf-8"))
    assert payload["engine_version"] == "0.5.0"
    assert payload["seed"] == spec.seed
    assert payload["spec_id"] == spec.spec_id
    assert payload["dataset_id"] is None
    assert payload["dataset_sha256"] is None


def test_candidates_parquet_mirrors_ledger(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_1", "kind": "rsi", "parameters": {"window": 21}, "revision": "method"})
        + "\n",
        encoding="utf-8",
    )
    write_candidates_parquet(layout)
    frame = pd.read_parquet(layout.candidates)
    assert list(frame["trial_id"]) == ["c_1"]
    assert list(frame["kind"]) == ["rsi"]


def test_report_is_a_view_of_sealed_evidence(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=True, detail={}),),
    )
    layout.evidence.mkdir()
    (layout.evidence / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    write_report(layout, research_outcome="FOUND", stop_reason="all_gates_passed")
    text = layout.report.read_text(encoding="utf-8")
    assert "# Research conclusion" in text
    assert "FOUND" in text
    assert "all_gates_passed" in text
    assert "dsr" in text.lower()
```

- [ ] **Step 2: Run the new tests, expect FAIL**

Run: `python -m pytest tests/runtime/test_artifacts_io.py -v`

Expected: FAIL with `ModuleNotFoundError: alphaloop.runtime.artifacts_io`.

- [ ] **Step 3: Write minimal implementation**

Implement the three writers. Parameters column: `json.dumps(parameters, sort_keys=True)`. Use `df.to_parquet(..., index=False)`. Empty ledger → empty parquet with those columns.

Wire `_run_protocol` to call them after `run_protocol` returns. Map outcome to morning stop reasons already defined in `runtime/morning.py` (`STOP_REASON_ALL_GATES_PASSED`, etc.) so the report matches the Web console. Import those constants from `morning.py` (runtime may import runtime).

On dataset load failure, still write manifest + empty parquet + report with `INCONCLUSIVE` / `incomplete_evidence`.

- [ ] **Step 4: Run artifact + worker tests, expect PASS**

Run: `python -m pytest tests/runtime/test_artifacts_io.py tests/runtime/test_worker.py -v`

Expected: PASS. Extend `test_run_worker_default_path_writes_protocol_artifacts` to `assert layout.manifest.exists()` and `assert layout.report.exists()` after adding the fixture parquet from Task 3.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/artifacts_io.py src/alphaloop/runtime/worker.py pyproject.toml tests/runtime/test_artifacts_io.py tests/runtime/test_worker.py
git commit -m "feat(runtime): write overnight manifest, candidates parquet, and evidence report"
```

---

### Task 5: Top-level `alphaloop replay`

**Files:**
- Modify: `src/alphaloop/cli/jobs.py` — register `replay`
- Modify: `src/alphaloop/cli/main.py` — dispatch `replay` like `status`
- Test: `tests/runtime/test_cli_jobs.py`

**Interfaces:**
- Consumes: `write_report`, `RunLayout`, job record via daemon **or** artifacts on disk
- Produces: `alphaloop replay RUN_ID [--data-dir DIR]`
  - Does **not** call `LoopReplay`
  - Reads `runs/<id>/evidence/gates.json` and `research-spec.yaml`
  - Rewrites `report.md`
  - Prints `research_outcome` from `gates.json` via `outcome_from_evidence(JobStatus.COMPLETED, evidence)` when evidence is complete; otherwise `INCONCLUSIVE`
  - Exit 2 if run dir missing
- Match `docs/cli.md` usage: `alphaloop replay <run_id> [--data-dir DIR]` (ignore `--output` unless already trivial; YAGNI: no `--output`, rewrite in place)

- [ ] **Step 1: Write the failing test**

Add to `tests/runtime/test_cli_jobs.py`:

```python
import json
from alphaloop.contracts.artifacts import RunLayout
from alphaloop.contracts.gates import GateResult, HardGateName, evidence_to_dict, evaluate_hard_gates


def test_parser_has_top_level_replay():
    parser = create_parser()
    assert "replay" in parser.format_help()


def test_replay_rewrites_report_without_looprunner(tmp_path, capsys):
    layout = RunLayout(tmp_path / "j_replay")
    layout.run_dir.mkdir()
    layout.research_spec.write_text(yaml.safe_dump(_spec().to_dict()), encoding="utf-8")
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=True, detail={}),),
    )
    layout.evidence.mkdir()
    (layout.evidence / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    rc = main(["replay", "j_replay", "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "FOUND" in captured.out
    assert layout.report.is_file()
    assert "FOUND" in layout.report.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the new tests, expect FAIL**

Run: `python -m pytest tests/runtime/test_cli_jobs.py::test_parser_has_top_level_replay tests/runtime/test_cli_jobs.py::test_replay_rewrites_report_without_looprunner -v`

Expected: FAIL (`invalid choice: 'replay'`).

- [ ] **Step 3: Write minimal implementation**

In `register()` add parser `replay` with positional `run_id` and `--data-dir`. `run_replay` builds `RunLayout(data_dir / run_id)`, loads evidence, derives outcome, `write_report(...)`, prints `research_outcome: FOUND` (or the actual token).

In `main()`, add `"replay"` to the job-command set that calls `parsed.func`.

Do not route through `_handle_loop`.

- [ ] **Step 4: Run CLI tests, expect PASS**

Run: `python -m pytest tests/runtime/test_cli_jobs.py tests/test_cli.py -v`

Expected: PASS. Legacy `alphaloop loop replay` tests in `tests/test_loop.py` still pass and are not part of this command.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/cli/jobs.py src/alphaloop/cli/main.py tests/runtime/test_cli_jobs.py
git commit -m "feat(cli): replay overnight report.md from sealed artifacts"
```

---

### Task 6: Regression sweep

**Files:** none required unless tests failed

- [ ] **Step 1: Run**

```
python -m pytest tests/protocol tests/runtime tests/contracts tests/cli/test_export.py tests/bundle -v
```

Expected: PASS (`not integration`).

- [ ] **Step 2: Commit only if you had to fix a regression**
