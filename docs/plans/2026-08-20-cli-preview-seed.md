# CLI preview N, seed, and budgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Human `alphaloop preview` stdout leads with `planned_n_trials` and discloses seed and budgets, matching the packaged preview card.

**Architecture:** Extend `format_protocol_preview` only. `preview_run` already returns the keys. `--json` unchanged. No Job API change.

**Tech Stack:** Python 3.9+, pytest.

**Spec:** `docs/requirements/2026-08-20-cli-preview-seed.md`

## Global Constraints

- Do not invent `FOUND` or a `run_id`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not change `preview_run`. Do not require preview before submit.
- Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: Formatter + docs

**Files:**
- Modify: `src/alphaloop/cli/jobs.py` (`format_protocol_preview`)
- Modify: `docs/cli.md`
- Test: `tests/runtime/test_cli_jobs.py`

**Interfaces:**
- Consumes: preview body keys already returned by `JobAPI.preview_run`
- Produces: `format_protocol_preview(body: dict[str, Any]) -> str` with N first, then seed and budgets

- [x] **Step 1: Failing tests**

Add to `tests/runtime/test_cli_jobs.py`:

```python
def test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets():
    from alphaloop.cli.jobs import format_protocol_preview

    text = format_protocol_preview(
        {
            "ok": True,
            "spec_id": "sp_demo",
            "statement": "momentum holds",
            "signal_mechanism": "momentum_12_1",
            "hard_gates": ["dsr", "walk_forward"],
            "planned_n_trials": 12,
            "seed": 7,
            "time_budget_s": 3600,
            "cost_budget_usd": 0.0,
            "method_parameter_grid": [{}],
        }
    )
    assert text.splitlines()[0] == "planned_n_trials: 12"
    assert "seed: 7" in text
    assert "time_budget_s: 3600" in text
    assert "cost_budget_usd: 0.0" in text
    assert text.index("planned_n_trials:") < text.index("spec_id:")
    assert text.index("seed:") < text.index("grid:")
    assert HOST_CONSTRAINT in text
    assert "Freeze with alphaloop submit --spec PATH" in text
    assert "run_id:" not in text
    assert "FOUND" not in text
```

Keep `test_preview_shows_protocol_without_creating_a_job`.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets -v
```

Expected: FAIL (`planned_n_trials` is not the first line; `seed: 7` missing).

- [x] **Step 3: Implement**

In `format_protocol_preview`, after any preflight error lines, emit:

```
planned_n_trials: {n}
spec_id: ...
statement: ...
signal_mechanism: ...
hard_gates: ...
seed: ...
time_budget_s: ...
cost_budget_usd: ...
grid:
```

Keep existing grid rows, `HOST_CONSTRAINT`, no-alpha sentence, and freeze cue.

In `docs/cli.md`, name seed and budgets in the preview paragraph.

- [x] **Step 4: PASS** plus `test_preview_shows_protocol_without_creating_a_job`

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets tests/runtime/test_cli_jobs.py::test_preview_shows_protocol_without_creating_a_job -v
```

- [x] **Step 5: Commit**

```bash
git commit -m "feat(cli): disclose N, seed, and budgets in protocol preview"
```
