# Morning evidence hard-gate glosses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Morning evidence lines and primary-evidence name interpolation use the same locked hard-gate gloss as the guided form.

**Architecture:** Canonical `HARD_GATE_GLOSS` / `gloss_hard_gate` on `contracts.gates`. `format_gate_line` and `format_primary_evidence` call it. Packaged HTML already has the same strings; a static test ties them together.

**Tech Stack:** Python 3.9+, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-evidence-glosses.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not gloss detail keys. Do not rewrite queued hypothesis prose.

---

### Task 1: Shared gloss + formatters

**Files:**
- Modify: `src/alphaloop/contracts/gates.py`
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `docs/webui.md`
- Modify: `tests/runtime/test_artifacts_io.py`
- Modify: `tests/runtime/test_morning.py`
- Modify: `tests/runtime/test_static_console.py`
- Modify: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

Add to `tests/runtime/test_artifacts_io.py`:

```python
def test_format_gate_line_uses_hard_gate_gloss():
    assert (
        format_gate_line({"name": "dsr", "passed": True, "detail": {}})
        == "dsr — Deflated Sharpe Ratio: pass"
    )
    assert format_gate_line({"name": "custom", "passed": True, "detail": {}}) == "custom: pass"


def test_format_primary_evidence_glosses_gate_names():
    failed = {"required": ["dsr"], "results": [{"name": "dsr", "passed": False, "detail": {}}]}
    assert (
        format_primary_evidence(
            "NO_EVIDENCE", evidence=failed, dominant_failures=("dsr",)
        )
        == "dsr — Deflated Sharpe Ratio failed"
    )
    assert (
        format_primary_evidence(
            "INCONCLUSIVE",
            evidence={
                "required": ["dsr", "walk_forward"],
                "results": [{"name": "dsr", "passed": True, "detail": {}}],
            },
            dominant_failures=(),
        )
        == "missing walk_forward — walk-forward OOS"
    )
```

Keep existing tests; they will fail after implementation until their expected strings gain the gloss.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py::test_format_gate_line_uses_hard_gate_gloss tests/runtime/test_artifacts_io.py::test_format_primary_evidence_glosses_gate_names -v
```

Expected: FAIL (`dsr: pass` / `dsr failed`).

- [ ] **Step 3: Implement**

In `src/alphaloop/contracts/gates.py` after `HardGateName`:

```python
HARD_GATE_GLOSS = {
    HardGateName.DSR.value: "dsr — Deflated Sharpe Ratio",
    HardGateName.WALK_FORWARD.value: "walk_forward — walk-forward OOS",
    HardGateName.VS_RANDOM.value: "vs_random — versus random",
    HardGateName.VS_BUY_HOLD.value: "vs_buy_hold — versus buy-and-hold",
    HardGateName.VS_BENCHMARK.value: "vs_benchmark — versus benchmark",
    HardGateName.DATA_CONSISTENCY.value: "data_consistency — data consistency",
}


def gloss_hard_gate(name: str) -> str:
    key = str(name)
    return HARD_GATE_GLOSS.get(key, key)
```

`format_gate_line`: prefix `f"{gloss_hard_gate(name)}: {verdict}"`.
`format_primary_evidence`: `f"{gloss_hard_gate(dominant_failures[0])} failed"` and missing names via `gloss_hard_gate`.

Update existing exact-string tests and e2e `#evidence` to the glossed forms.
In `test_packaged_hard_gates_keep_token_and_human_gloss`, also assert each `HARD_GATE_GLOSS` value is in the fieldset.

`docs/webui.md`: morning evidence lines use the same hard-gate gloss as the form.

- [ ] **Step 4: PASS**

```bash
python3 -m pytest tests/runtime/test_artifacts_io.py tests/runtime/test_morning.py tests/runtime/test_static_console.py::test_packaged_hard_gates_keep_token_and_human_gloss -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(runtime): gloss hard-gate names on morning evidence lines"
```
