# Morning primary evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the five-minute primary-evidence sentence and stop reason inside the morning verdict stage, from a shared formatter that cannot mint `FOUND`.

**Architecture:** `format_primary_evidence` in `artifacts_io.py` is the only copy source. `morning_view` exposes `primary_evidence`. `write_report` writes the same string. Packaged `#verdict` clusters `#outcome`, gloss, `#primary-evidence`, and `#stop-reason`.

**Tech Stack:** Python 3.9+, packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-primary-evidence.md`

## Global Constraints

- Do not invent `FOUND`. Do not change `HOST_CONSTRAINT` or existing Help sentences.
- No `FakeWorker` in morning e2e. Do not unfreeze `webui/`.
- `#outcome` text stays the research-outcome token.

---

### Task 1: Shared formatter and morning payload

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/runtime/morning.py`
- Test: `tests/runtime/test_artifacts_io.py`
- Test: `tests/runtime/test_morning.py`

**Interfaces:**
- Produces: `format_primary_evidence(research_outcome: str, *, evidence: Mapping[str, Any] | None, dominant_failures: Sequence[str]) -> str | None`
- Consumes: sealed `research_outcome`, last-loaded evidence dict (or `None`), `funnel["dominant_failures"]`

- [ ] **Step 1: Write the failing tests**

Add to `tests/runtime/test_artifacts_io.py`:

```python
from alphaloop.runtime.artifacts_io import format_primary_evidence


def test_format_primary_evidence_follows_sealed_outcome():
    failed = {"required": ["dsr"], "results": [{"name": "dsr", "passed": False, "detail": {}}]}
    assert format_primary_evidence(
        "FOUND", evidence=failed, dominant_failures=("dsr",)
    ) == "all required hard gates passed"
    assert format_primary_evidence(
        "NO_EVIDENCE", evidence=failed, dominant_failures=("dsr", "walk_forward")
    ) == "dsr failed"
    assert format_primary_evidence(
        "NO_EVIDENCE", evidence=failed, dominant_failures=()
    ) == "a required hard gate failed"
    assert format_primary_evidence(
        "INCONCLUSIVE", evidence=None, dominant_failures=()
    ) == "no sealed gates.json"
    assert format_primary_evidence(
        "INCONCLUSIVE",
        evidence={"required": ["dsr", "walk_forward"], "results": [{"name": "dsr", "passed": True, "detail": {}}]},
        dominant_failures=(),
    ) == "missing walk_forward"
    assert format_primary_evidence(
        "INCONCLUSIVE",
        evidence={"required": ["dsr"], "results": [{"name": "dsr", "passed": True, "detail": {}}]},
        dominant_failures=(),
    ) == "incomplete evidence set"
    assert format_primary_evidence("NONE", evidence=None, dominant_failures=()) is None
```

Extend `test_report_includes_elimination_funnel` (or add):

```python
assert "primary_evidence: dsr failed" in text
```

Add to `tests/runtime/test_morning.py` on existing cases:

```python
# test_passing_gates_found
assert view["primary_evidence"] == "all required hard gates passed"
# test_failed_gate_is_no_evidence
assert view["primary_evidence"] == "dsr failed"
# test_missing_gates_is_inconclusive
assert view["primary_evidence"] == "no sealed gates.json"
# test_revisions_and_queued_hypotheses (NONE)
assert view["primary_evidence"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_artifacts_io.py::test_format_primary_evidence_follows_sealed_outcome tests/runtime/test_morning.py::test_passing_gates_found tests/runtime/test_morning.py::test_failed_gate_is_no_evidence tests/runtime/test_morning.py::test_missing_gates_is_inconclusive tests/runtime/test_morning.py::test_revisions_and_queued_hypotheses tests/runtime/test_artifacts_io.py::test_report_includes_elimination_funnel -v`

Expected: FAIL (`format_primary_evidence` not defined and/or missing key / report line).

- [ ] **Step 3: Write minimal implementation**

In `artifacts_io.py`:

```python
from typing import Any, Mapping, Sequence

def format_primary_evidence(
    research_outcome: str,
    *,
    evidence: Mapping[str, Any] | None,
    dominant_failures: Sequence[str],
) -> str | None:
    if research_outcome == "FOUND":
        return "all required hard gates passed"
    if research_outcome == "NO_EVIDENCE":
        if dominant_failures:
            return f"{dominant_failures[0]} failed"
        return "a required hard gate failed"
    if research_outcome != "INCONCLUSIVE":
        return None
    missing: list[str] = []
    if evidence:
        present = {
            row.get("name")
            for row in (evidence.get("results") or [])
            if isinstance(row, dict)
        }
        missing = [
            name
            for name in (evidence.get("required") or [])
            if name not in present
        ]
    if missing:
        return "missing " + ", ".join(missing)
    if evidence is None:
        return "no sealed gates.json"
    return "incomplete evidence set"
```

`write_report`: after `stop_reason`, load funnel + last gates dict and append `primary_evidence: …` when not `None`.

`morning_view`: after building `funnel` / `evidence`, set `"primary_evidence": format_primary_evidence(job.research_outcome.value, evidence=evidence, dominant_failures=funnel["dominant_failures"])`.

- [ ] **Step 4: Run tests to verify they pass**

Run the same pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/artifacts_io.py src/alphaloop/runtime/morning.py tests/runtime/test_artifacts_io.py tests/runtime/test_morning.py
git commit -m "feat(morning): expose sealed primary_evidence for the five-minute review"
```

---

### Task 2: Verdict cluster in the packaged console

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `job.primary_evidence`, existing `job.stop_reason`
- Produces: `#primary-evidence` and `#stop-reason` inside `#verdict`

- [ ] **Step 1: Write the failing tests**

In `test_packaged_console_morning_verdict_stage`:

```python
assert html.find('id="outcome-gloss"') < html.find('id="primary-evidence"')
assert html.find('id="primary-evidence"') < html.find('id="stop-reason"')
assert html.find('id="stop-reason"') < html.find('id="job-status"')
assert "fillPrimaryEvidence" in script
assert "Primary evidence:" in script
```

In `test_job_detail_while_running_or_later_legal_outcome`:

```python
primary = page.locator("#primary-evidence").inner_text()
assert primary.startswith("Primary evidence:")
assert page.locator("#verdict #stop-reason").count() == 1
```

In `test_missing_columns_are_inconclusive_without_gates`:

```python
assert "no sealed gates.json" in page.locator("#primary-evidence").inner_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_verdict_stage -v`

Expected: FAIL (ids / helper missing).

- [ ] **Step 3: Write minimal implementation**

Move `#stop-reason` into `#verdict`. Add `#primary-evidence` between gloss and stop reason.

`fillPrimaryEvidence(job)`:

```javascript
function fillPrimaryEvidence(job) {
  const node = document.getElementById("primary-evidence");
  const value = job.primary_evidence;
  node.textContent = value
    ? "Primary evidence: " + value
    : "Primary evidence: (running or not yet terminal)";
}
```

Call it from `showJob` after `fillOutcomeGloss`. Style `#primary-evidence` and in-verdict `#stop-reason` as scannable muted lines. No `http` in CSS.

- [ ] **Step 4: Run unit then e2e**

```bash
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration
python3 -m pytest tests/e2e -m e2e
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/webui/static tests/runtime/test_static_console.py tests/e2e/test_morning_console.py
git commit -m "feat(webui): stage primary evidence and stop reason in the verdict"
```
