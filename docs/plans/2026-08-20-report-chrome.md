# Sealed report outcome chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged `#report` uses the same FOUND / NO_EVIDENCE / INCONCLUSIVE chrome as `#verdict`, and is readable (`--fg`) rather than muted metadata.

**Architecture:** `fillReport` sets `data-outcome` from `job.research_outcome`. CSS outcome selectors mirror `#verdict` token families. File bytes stay `textContent`.

**Tech Stack:** Packaged `app.js` / `styles.css`, pytest static + morning e2e.

**Spec:** `docs/requirements/2026-08-20-report-chrome.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not render markdown as HTML. Do not rewrite `report.md`.

---

### Task 1: data-outcome + CSS

**Files:**
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Write the failing tests**

In `test_packaged_console_morning_report`:

```python
    fill_at = script.find("function fillReport")
    assert fill_at != -1
    assert "dataset.outcome" in script[fill_at : fill_at + 400]
    assert '#report[data-outcome="FOUND"]' in css
    assert '#report[data-outcome="NO_EVIDENCE"]' in css
    assert '#report[data-outcome="INCONCLUSIVE"]' in css
    found_rule = css.find('#report[data-outcome="FOUND"]')
    found_block = css[found_rule : css.find("}", found_rule)]
    assert "224, 160" in found_block or "var(--accent)" in found_block
    assert "target found" not in css.lower()
```

In e2e `test_replay_rewrites_report`, after `#report` assertions:

```python
    assert page.locator("#report").get_attribute("data-outcome") == outcome
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_report -v
```

Expected: FAIL (`dataset.outcome` / `#report[data-outcome="FOUND"]` missing).

- [x] **Step 3: Write minimal implementation**

`fillReport`:

```javascript
function fillReport(job) {
  const node = document.getElementById("report");
  node.dataset.outcome = job.research_outcome || "";
  node.textContent = job.report_markdown || "";
}
```

Remove `#report` from the muted metadata selector list. Keep the existing `#report { white-space...}` block and add `color: var(--fg)`. Add:

```css
#report[data-outcome="FOUND"] {
  border-color: rgba(62, 224, 160, 0.5);
  box-shadow: 0 0 0 1px rgba(62, 224, 160, 0.12), 0 18px 40px rgba(62, 224, 160, 0.08);
}

#report[data-outcome="NO_EVIDENCE"] {
  border-color: rgba(255, 176, 32, 0.45);
  box-shadow: 0 0 0 1px rgba(255, 176, 32, 0.1), 0 18px 40px rgba(255, 176, 32, 0.08);
}

#report[data-outcome="INCONCLUSIVE"] {
  border-color: rgba(196, 160, 255, 0.45);
  box-shadow: 0 0 0 1px rgba(196, 160, 255, 0.1), 0 18px 40px rgba(196, 160, 255, 0.08);
}
```

`docs/webui.md`: the sealed report uses the same outcome chrome as the verdict.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_report tests/runtime/test_static_console.py::test_packaged_console_lifecycle_chrome -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: give the sealed report the same outcome chrome as the verdict"
```
