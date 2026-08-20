# Console FOUND export receipt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a human Export .asb click, `#export-status` shows the same FOUND receipt as CLI.

**Architecture:** `export_run` adds `export_handoff` from `format_export_handoff`. The packaged console assigns that string to `#export-status` and CSS keeps the four lines.

**Tech Stack:** Packaged static JS/CSS, Job API, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-console-export-receipt.md`

## Global Constraints

- Do not invent `FOUND`. Do not change `assert_exportable` / Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- No auto-export. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not change CLI export stdout.

---

### Task 1: Receipt on API + console

**Files:**
- Modify: `src/alphaloop/runtime/api.py`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_api.py`
- Test: `tests/runtime/test_http.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

```python
from alphaloop.runtime.morning import format_export_handoff

def test_export_run_writes_asb_for_found_ledger_id(...):
    ...
    assert payload["export_handoff"] == format_export_handoff(
        candidate_id="c1",
        exported_path=str(path),
    )
```

HTTP 200: `body["export_handoff"]` equals the same formatter.

Static: `"export_handoff"` in script; `"#export-status"` and `pre-wrap` in CSS; `"http"` not in CSS.

E2E FOUND branch after click: `#export-status` first line `FOUND`; includes
`This export does not claim alpha or future profitability.` and `.asb`.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_api.py::test_export_run_writes_asb_for_found_ledger_id tests/runtime/test_static_console.py::test_packaged_console_asb_export -v
```

- [x] **Step 3: Implement**

`export_run` sets `export_handoff`. Console `status.textContent = body.export_handoff || body.exported_path || ""`. CSS `#export-status { white-space: pre-wrap; }`. Docs.

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "feat(webui): show the FOUND receipt after console export"
```
