# Honest methodological revisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `morning_view["revisions"]` lists only in-run `method` ledger rows; unique `n_trials` still counts the full ledger.

**Architecture:** Split full-ledger load from the revisions filter in `runtime/morning.py`. Packaged `#revisions` already renders `job.revisions`; empty fillList stays `none`.

**Tech Stack:** Python 3.9+, pytest.

**Spec:** `docs/requirements/2026-08-20-honest-revisions.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N` / unique `n_trials`.
- Do not rewrite trial-ledger.jsonl. Do not start soak jobs.

---

### Task 1: Filter morning revisions

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_morning.py`

**Interfaces:**
- Consumes: trial-ledger JSONL rows with `trial_id` and `revision`
- Produces: `morning_view(...)["revisions"]` = rows with `revision == "method"`
- Produces: `morning_view(...)["n_trials"]` = unique ids over **all** ledger rows

- [x] **Step 1: Failing tests**

Replace `test_revisions_and_queued_hypotheses` in `tests/runtime/test_morning.py` with:

```python
def test_revisions_and_queued_hypotheses(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"trial_id": "c_1", "revision": "none", "parameters": {}}),
                json.dumps(
                    {
                        "trial_id": "c_2",
                        "revision": "method",
                        "parameters": {"window": 21},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "recommendations.json").write_text(
        json.dumps({"queued_hypotheses": [{"statement": "try mean reversion"}]}),
        encoding="utf-8",
    )
    view = morning_view(store.get(job.run_id), tmp_path)
    assert [row["trial_id"] for row in view["revisions"]] == ["c_2"]
    assert view["revisions"][0]["revision"] == "method"
    assert view["n_trials"] == 2
    assert view["queued_hypotheses"][0]["statement"] == "try mean reversion"
    assert view["research_outcome"] == ResearchOutcome.NONE.value
    assert view["stop_reason"] is None
    assert view["primary_evidence"] is None


def test_revisions_omit_first_frozen_grid_point(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    (run_dir / "trial-ledger.jsonl").write_text(
        json.dumps({"trial_id": "c_1", "revision": "none"}) + "\n",
        encoding="utf-8",
    )
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["revisions"] == []
    assert view["n_trials"] == 1
```

Keep `test_morning_view_exposes_seed_and_unique_n_trials`.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_morning.py::test_revisions_and_queued_hypotheses tests/runtime/test_morning.py::test_revisions_omit_first_frozen_grid_point -v
```

Expected: FAIL (`revisions` still includes `c_1` / `none`).

- [x] **Step 3: Implement**

In `src/alphaloop/runtime/morning.py`:

- Keep a full-ledger loader used by `_n_trials`.
- `morning_view["revisions"]` returns only rows with `revision == "method"`.

In `docs/webui.md`, one sentence: methodological revisions are in-run method repairs, not the first frozen grid point.

- [x] **Step 4: PASS** plus unique-`n_trials` test

```bash
python3 -m pytest tests/runtime/test_morning.py::test_revisions_and_queued_hypotheses tests/runtime/test_morning.py::test_revisions_omit_first_frozen_grid_point tests/runtime/test_morning.py::test_morning_view_exposes_seed_and_unique_n_trials -v
```

- [x] **Step 5: Commit**

```bash
git commit -m "feat(runtime): list only in-run method repairs as revisions"
```
