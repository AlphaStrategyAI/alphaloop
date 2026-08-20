# Verdict Export button chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `#handoff` Export .asb control uses designed chrome and FOUND accent color, not the user-agent button.

**Architecture:** Extend packaged `styles.css`. Group `#handoff .export-asb` with the existing qualifying export button; add a FOUND-scoped accent rule.

**Tech Stack:** Packaged static CSS, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-handoff-export-button.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- No auto-export. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not change CLI export stdout.

---

### Task 1: CSS

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

```python
assert "#handoff .export-asb" in css
assert "#verdict[data-outcome=\"FOUND\"] #handoff .export-asb" in css
assert "var(--accent)" in css
assert "http" not in css
```

E2E FOUND branch after the export button is visible:

```python
style = page.locator("#verdict #handoff button.export-asb").first.evaluate(
    "el => getComputedStyle(el)"
)
assert style["borderColor"] == "rgb(62, 224, 160)"
assert style["color"] == "rgb(62, 224, 160)"
```

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_asb_export -v
```

- [x] **Step 3: Implement**

Add `#handoff .export-asb` to the existing designed-button group.
Add `#verdict[data-outcome="FOUND"] #handoff .export-asb` accent rule.

- [x] **Step 4: Tests pass**

- [x] **Step 5: Commit**

```bash
git commit -m "feat(webui): style the verdict Export control as a FOUND handoff"
```
