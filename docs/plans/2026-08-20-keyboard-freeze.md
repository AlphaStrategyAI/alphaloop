# Keyboard preview-then-freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ctrl/Cmd+Enter previews, then freezes, using the existing button paths. Visible `#keyboard-hint`. No job without a successful preview.

**Architecture:** One window `keydown` listener. If Freeze is enabled, `submitJob`; else `previewProtocol`. Hint copy is locked.

**Tech Stack:** Packaged static JS, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-keyboard-freeze.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Freeze stays disabled until Preview succeeds. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: Chord + hint

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

Static:

```python
def test_packaged_console_keyboard_preview_then_freeze():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="keyboard-hint"' in html
    assert html.find('id="submit-job"') < html.find('id="keyboard-hint"')
    assert "Ctrl/Cmd+Enter: Preview, then Freeze." in html
    assert 'addEventListener("keydown"' in script
    assert "ctrlKey" in script
    assert "metaKey" in script
    assert "previewProtocol()" in script
    assert "submitJob()" in script
    assert "#keyboard-hint" in css
    assert "http" not in css
    assert "override" not in script.lower()
```

E2E `test_home_shows_promise_and_submit_form`: `#keyboard-hint` text.

New e2e `test_ctrl_enter_previews_then_freezes`:

```python
def test_ctrl_enter_previews_then_freezes(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _fill_spec(page, _spec_yaml(dataset, time_budget_s=30))  # or load-example + dataset
    page.keyboard.press("Control+Enter")
    page.wait_for_function(
        "() => document.getElementById('submit-job') && !document.getElementById('submit-job').disabled",
        timeout=10000,
    )
    assert page.locator("#job-list button").count() == 0
    page.keyboard.press("Control+Enter")
    page.wait_for_selector("#job-list button", timeout=15000)
    assert page.locator("#job-list button").count() >= 1
```

Use the same YAML fill helper as `_preview_then_submit` but skip the clicks.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_keyboard_preview_then_freeze -v
```

- [ ] **Step 3: Implement**

HTML hint. Window keydown as specified. CSS muted hint. `docs/webui.md` one sentence. mkdocs nav.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): Ctrl/Cmd+Enter previews then freezes"
```
