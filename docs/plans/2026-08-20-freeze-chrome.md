# Freeze designed accent chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged `#submit-job` uses `--ink` background and `--accent` border/text, not ad-hoc hex.

**Architecture:** CSS only. Same family as `#preview-protocol`. Click/disabled behavior unchanged.

**Tech Stack:** packaged `styles.css`, pytest static + Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-freeze-chrome.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle Preview or Load.

---

### Task 1: Designed chrome

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

Add `test_packaged_console_freeze_chrome` next to preview chrome:

```python
def test_packaged_console_freeze_chrome():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="submit-job"' in html
    freeze_rule = css.find("#submit-job {")
    assert freeze_rule != -1
    freeze_block = css[freeze_rule : css.find("}", freeze_rule)]
    assert "var(--ink)" in freeze_block
    assert "var(--accent)" in freeze_block
    assert "var(--focus)" not in freeze_block
    assert "var(--warn)" not in freeze_block
    assert "#16352c" not in freeze_block
    assert "#2f6b55" not in freeze_block
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html
```

In `test_home_shows_promise_and_submit_form`, after the preview
`wait_for_function`, wait for Freeze:

```python
    page.wait_for_function(
        """() => {
          const el = document.getElementById('submit-job');
          if (!el) return false;
          const style = getComputedStyle(el);
          return (
            style.color === 'rgb(62, 224, 160)' &&
            style.backgroundColor === 'rgb(11, 15, 22)'
          );
        }""",
        timeout=10000,
    )
```

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_freeze_chrome -v
```

Expected: FAIL (`var(--ink)` missing).

- [x] **Step 3: Implement**

```css
#submit-job {
  background: var(--ink);
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 0.45rem;
  padding: 0.55rem 0.8rem;
  font: inherit;
  cursor: pointer;
}
```

Keep `#submit-job:disabled`. `docs/webui.md`: Freeze uses ink
background and FOUND accent, not ad-hoc hex.

- [x] **Step 4: PASS**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_freeze_chrome tests/runtime/test_static_console.py::test_packaged_console_preview_chrome tests/e2e/test_morning_console.py::test_home_shows_promise_and_submit_form -v
```

- [x] **Step 5: Commit**

```bash
git add src/alphaloop/webui/static/styles.css docs/webui.md tests/runtime/test_static_console.py tests/e2e/test_morning_console.py docs/plans/2026-08-20-freeze-chrome.md
git commit -m "feat(webui): give Freeze designed accent chrome"
```
