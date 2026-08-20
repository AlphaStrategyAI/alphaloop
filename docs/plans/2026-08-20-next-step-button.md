# Verdict Load-into-editor button chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `#next-step` Load into editor control uses designed chrome and NO_EVIDENCE warn color, not the user-agent button or FOUND green.

**Architecture:** Extend packaged `styles.css`. Group `#next-step .load-queued` with the existing queued load button; add a NO_EVIDENCE-scoped `--warn` rule.

**Tech Stack:** Packaged static CSS, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-next-step-button.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: CSS

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

```python
assert "#next-step .load-queued" in css
assert '#verdict[data-outcome="NO_EVIDENCE"] #next-step .load-queued' in css
```

E2E in `test_load_queued_fills_editor_without_submitting` before click:

```python
button = page.locator("#verdict #next-step button.load-queued")
assert button.evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(11, 15, 22)"
if page.locator("#verdict").get_attribute("data-outcome") == "NO_EVIDENCE":
    assert button.evaluate("el => getComputedStyle(el).color") == "rgb(255, 176, 32)"
```

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_verdict_stage -v
```

- [x] **Step 3: Implement**

Add `#next-step .load-queued` to the designed-button group.
Add `#verdict[data-outcome="NO_EVIDENCE"] #next-step .load-queued` warn rule.

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "feat(webui): style the verdict Load control as a next-run handoff"
```
