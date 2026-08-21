# CLI status revision gloss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop status` / `replay` five-minute cluster names repaired signal kinds with the same locked gloss as the form.

**Architecture:** `format_status_verdict` emits `Revision: {format_revision_line(row)}` after stop reason. `replay_view` adds `revisions` from `build_method_revisions`. Empty omits the line.

**Tech Stack:** Python 3.9+, pytest.

**Spec:** `docs/requirements/2026-08-20-status-revision-gloss.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not rewrite `trial-ledger.jsonl`. Do not execute queued economic revisions.

---

### Task 1: verdict lines + replay payload

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `docs/cli.md`
- Test: `tests/runtime/test_morning.py`

**Interfaces:**
- Consumes: `format_revision_line(row) -> str`
- Consumes: `build_method_revisions(layout) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

In `tests/runtime/test_morning.py`:

```python
def test_format_status_verdict_glosses_revisions():
    text = format_status_verdict(
        {
            "research_outcome": "NO_EVIDENCE",
            "primary_evidence": "dsr — Deflated Sharpe Ratio failed",
            "stop_reason": "hard_gate_failed",
            "status": "completed",
            "revisions": [
                {
                    "trial_id": "c_2",
                    "revision": "method",
                    "kind": "momentum_12_1",
                    "kind_label": "momentum_12_1 — 12-1 momentum",
                    "parameters": {"window": 21},
                }
            ],
            "queued_hypotheses": [
                {"statement": "Try rsi. Not a claim of alpha."}
            ],
        }
    )
    lines = text.splitlines()
    assert (
        "Revision: c_2 · method · momentum_12_1 — 12-1 momentum · window=21"
        in lines
    )
    assert lines.index("Stop reason: hard_gate_failed") < lines.index(
        "Revision: c_2 · method · momentum_12_1 — 12-1 momentum · window=21"
    )
    assert lines.index(
        "Revision: c_2 · method · momentum_12_1 — 12-1 momentum · window=21"
    ) < lines.index("Next run: Try rsi. Not a claim of alpha.")


def test_replay_view_includes_method_revisions(tmp_path):
    from alphaloop.contracts.artifacts import RunLayout

    layout = RunLayout(tmp_path / "j_replay")
    layout.run_dir.mkdir()
    layout.trial_ledger.write_text(
        json.dumps(
            {
                "trial_id": "c_2",
                "revision": "method",
                "kind": "momentum_12_1",
                "parameters": {"window": 21},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    view = replay_view(layout, research_outcome="NO_EVIDENCE", status="completed")
    assert view["revisions"][0]["kind_label"] == "momentum_12_1 — 12-1 momentum"
```

In `test_format_status_verdict_none_omits_optional_lines`, add:

```python
    assert "Revision:" not in text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_morning.py::test_format_status_verdict_glosses_revisions tests/runtime/test_morning.py::test_replay_view_includes_method_revisions tests/runtime/test_morning.py::test_format_status_verdict_none_omits_optional_lines -v
```

Expected: FAIL (`Revision:` missing / `revisions` missing on replay_view).

- [ ] **Step 3: Write minimal implementation**

Import `format_revision_line` in `morning.py`.

`format_status_verdict` after stop reason:

```python
    revisions = view.get("revisions") or []
    if isinstance(revisions, list):
        for row in revisions:
            if not isinstance(row, dict):
                continue
            line = format_revision_line(row)
            if line:
                lines.append("Revision: " + line)
```

`replay_view` payload: `"revisions": build_method_revisions(layout)`.

`docs/cli.md`: the cluster may include revision lines that name the repaired signal with the same gloss as the form.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_morning.py::test_format_status_verdict_glosses_revisions tests/runtime/test_morning.py::test_replay_view_includes_method_revisions tests/runtime/test_morning.py::test_format_status_verdict_none_omits_optional_lines tests/runtime/test_morning.py::test_format_status_verdict_found_cluster tests/runtime/test_morning.py::test_format_status_verdict_queued_next_run -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: gloss repaired signal kinds on CLI status revisions"
```
