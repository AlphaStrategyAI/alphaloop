# Torn trial-ledger resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skip unparseable `trial-ledger.jsonl` lines so SIGKILL mid-append cannot crash resume or invent extra `n_trials`.

**Architecture:** Match `artifacts_io._ledger_rows` skip rules inside `protocol.loop._ledger_rows`. Protocol must not import runtime.

**Tech Stack:** Python 3.9+, pytest.

**Spec:** `docs/requirements/2026-08-20-torn-ledger.md`

## Global Constraints

- Do not invent `FOUND`. Do not shrink DSR `N` below unique parsed ids.
- `alphaloop.protocol` must not import `live` / `webui` / `runtime`.

---

### Task 1: Skip torn JSONL in the protocol ledger reader

**Files:**
- Modify: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_protocol_loop.py`

- [ ] **Step 1: Write the failing test**

```python
def test_torn_trailing_ledger_line_does_not_crash_resume(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    first_id = _cid("momentum_12_1", {})
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": first_id, "kind": "momentum_12_1", "parameters": {}})
        + "\n{\"trial_id\": \"c_partial\"",
        encoding="utf-8",
    )
    seen = []

    def runner(required, **kwargs):
        seen.append(kwargs["n_trials"])
        return _incomplete(required, **kwargs)

    result = run_protocol(
        _spec(),
        layout,
        prices=_prices(),
        buy_hold_prices=_prices()["AAPL"],
        benchmark_prices=_prices()["AAPL"],
        gate_runner=runner,
        completed_trial_ids=(),
    )
    assert result.research_outcome is not ResearchOutcome.FOUND
    assert seen
    assert seen[0] == 1
    parsed = []
    for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("trial_id"):
            parsed.append(row["trial_id"])
    assert first_id in parsed
    assert parsed.count(first_id) == 1
    assert "c_partial" not in parsed
```

- [ ] **Step 2: Run to verify FAIL**

Run: `python3 -m pytest tests/protocol/test_protocol_loop.py::test_torn_trailing_ledger_line_does_not_crash_resume -v`

Expected: FAIL (`JSONDecodeError`).

- [ ] **Step 3: Skip bad lines in `_ledger_rows`**

Same loop as `artifacts_io._ledger_rows`: strip, skip empty, `try/except json.JSONDecodeError`, keep `dict` rows only.

- [ ] **Step 4: PASS, then full unit + e2e**

- [ ] **Step 5: Commit**
