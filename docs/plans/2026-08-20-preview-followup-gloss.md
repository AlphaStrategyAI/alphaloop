# Preview and follow-up glosses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Protocol preview and queued follow-up statements use the same locked signal and gate glosses as the guided form.

**Architecture:** Canonical `SIGNAL_GLOSS` on `protocol.dsl`. `preview_run` adds `signal_label` / `hard_gate_labels`. CLI formatter and packaged `renderPreview` print those labels. `followup_hypotheses` interpolates glosses; queued `signal_mechanism` stays the DSL token.

**Tech Stack:** Python 3.9+, packaged `app.js`, pytest.

**Spec:** `docs/requirements/2026-08-20-preview-followup-gloss.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit queued follow-ups. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not add DSL kinds.

---

### Task 1: SIGNAL_GLOSS + preview + follow-up

**Files:**
- Modify: `src/alphaloop/protocol/dsl.py`
- Modify: `src/alphaloop/runtime/api.py`
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `src/alphaloop/protocol/recommend.py`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `docs/webui.md`, `docs/cli.md`
- Test: `tests/protocol/test_dsl.py` or `tests/protocol/test_recommend.py`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/runtime/test_api.py`
- Test: `tests/runtime/test_static_console.py`

- [ ] **Step 1: Failing tests**

In `tests/protocol/test_recommend.py`:

```python
from alphaloop.contracts.gates import GateResult, HardGateName, evaluate_hard_gates
from alphaloop.contracts.research_spec import new_research_spec
from alphaloop.protocol.dsl import gloss_signal
from alphaloop.protocol.recommend import counterpart_kind, followup_hypotheses


def test_gloss_signal_matches_form_labels():
    assert gloss_signal("momentum_12_1") == "momentum_12_1 — 12-1 momentum"
    assert gloss_signal("rsi") == "rsi — RSI"
    assert gloss_signal("parkinson_hist_vol") == "parkinson_hist_vol"


def test_followup_hypotheses_use_locked_glosses():
    spec = new_research_spec(
        statement="x",
        economic_logic="x",
        signal_mechanism="momentum_12_1",
        market_scope="AAPL",
        market_profile="us-equity-daily",
        benchmark="SPY",
        hard_gates=("dsr", "walk_forward"),
        seed=1,
        time_budget_s=30,
        cost_budget_usd=0.0,
    )
    required = tuple(HardGateName(name) for name in spec.success_criteria.hard_gates)
    evidence = evaluate_hard_gates(
        required,
        tuple(
            GateResult(name=name, passed=name is not HardGateName.DSR, detail={})
            for name in required
        ),
    )
    row = followup_hypotheses(spec, evidence)[0]
    assert row["signal_mechanism"] == "rsi"
    assert "momentum_12_1 — 12-1 momentum" in row["statement"]
    assert "rsi — RSI" in row["statement"]
    assert "dsr — Deflated Sharpe Ratio" in row["statement"]
    assert "not a claim of alpha" in row["statement"].lower()
```

Extend `test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets`:

```python
    assert "momentum_12_1 — 12-1 momentum" in text
    assert "dsr — Deflated Sharpe Ratio" in text
```

Keep counterpart_kind tests.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/protocol/test_recommend.py tests/runtime/test_cli_jobs.py::test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets -v
```

Expected: FAIL (`gloss_signal` missing; preview/follow-up still tokens).

- [ ] **Step 3: Implement**

`SIGNAL_GLOSS` + `gloss_signal` in `dsl.py` (locked table).
`preview_run` adds `signal_label` and `hard_gate_labels`.
`format_protocol_preview` prints glossed signal and gates.
`renderPreview` uses `signal_label` / `hard_gate_labels` with raw fallback.
`followup_hypotheses` interpolates glosses; queued kind stays token.
Docs: one sentence each in `docs/webui.md` and `docs/cli.md`.
Static: every `SIGNAL_GLOSS` value in the signal `<select>`.

- [ ] **Step 4: PASS**

```bash
python3 -m pytest tests/protocol/test_recommend.py tests/runtime/test_cli_jobs.py::test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets tests/runtime/test_api.py::test_preview_run_does_not_create_a_job tests/runtime/test_static_console.py::test_packaged_signal_select_groups_economic_families -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: gloss signals and gates in preview and queued follow-ups"
```
