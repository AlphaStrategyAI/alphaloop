# Protocol preview card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `#protocol-preview` leads with `planned_n_trials`, shows seed and budgets, and uses designed `--focus` chrome.

**Architecture:** `renderPreview` DOM only plus CSS. `preview_run` keys unchanged. `#host-constraint` stays separate.

**Tech Stack:** packaged `app.js` / `styles.css`, pytest static + Playwright.

**Spec:** `docs/requirements/2026-08-20-preview-card.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle Load/Preview/Freeze buttons.

---

### Task 1: Card + disclosure

**Files:**
- Modify: `src/alphaloop/webui/static/app.js` (`renderPreview`)
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

Add:

```python
def test_packaged_console_preview_card():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="protocol-preview"' in html
    assert "preview-n-trials" in script
    assert "seed:" in script
    assert "time_budget_s:" in script
    assert "cost_budget_usd:" in script
    card = css.find("#protocol-preview:not(:empty)")
    assert card != -1
    card_block = css[card : css.find("}", card)]
    assert "var(--ink)" in card_block
    assert "var(--focus)" in card_block
    assert "var(--accent)" not in card_block
    n_rule = css.find("#preview-n-trials")
    assert n_rule != -1
    n_block = css[n_rule : css.find("}", n_rule)]
    assert "var(--focus)" in n_block
    assert "var(--accent)" not in n_block
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()
```

In `test_preview_does_not_create_a_job`, after preview:

```python
    text = page.locator("#protocol-preview").inner_text()
    assert "planned_n_trials" in text
    assert "seed:" in text
    assert "time_budget_s:" in text
    page.wait_for_function(
        """() => {
          const el = document.getElementById('preview-n-trials');
          if (!el) return false;
          return getComputedStyle(el).color === 'rgb(126, 184, 255)';
        }""",
        timeout=10000,
    )
```

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_preview_card -v
```

Expected: FAIL (`preview-n-trials` missing).

- [ ] **Step 3: Implement**

`renderPreview`: first child `#preview-n-trials` with
`planned_n_trials: {n}`; summary includes seed and budgets; keep
`#protocol-grid`.

CSS: `#protocol-preview:not(:empty)` ink + focus border;
`#preview-n-trials` focus color, larger type.

`docs/webui.md`: preview card leads with planned trial count.

- [ ] **Step 4: PASS** targeted static + `test_preview_does_not_create_a_job`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): show seed, budgets, and N on the protocol preview card"
```
