# Protocol preview above Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before bed DOM order is Load/Preview → preview card → errors → Freeze, so the user reviews N before committing.

**Architecture:** Split the Before bed `.actions` row. Keep Load + Preview above `#protocol-preview`. Keep Freeze + keyboard hint below `#preflight-errors`. No JS behavior change.

**Tech Stack:** Packaged `index.html`, pytest static + morning e2e.

**Spec:** `docs/requirements/2026-08-20-preview-before-freeze.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not auto-submit. Do not restyle Load / Preview / Freeze tokens.

---

### Task 1: DOM order

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Write the failing tests**

In `test_packaged_console_preview_card`:

```python
    assert html.find('id="preview-protocol"') < html.find('id="protocol-preview"')
    assert html.find('id="protocol-preview"') < html.find('id="submit-job"')
    assert html.find('id="protocol-preview"') < html.find('id="preflight-errors"')
    assert html.find('id="preflight-errors"') < html.find('id="submit-job"')
```

In e2e `test_preview_does_not_create_a_job`, after the preview card assertions:

```python
    preview_box = page.locator("#protocol-preview").bounding_box()
    submit_box = page.locator("#submit-job").bounding_box()
    assert preview_box is not None and submit_box is not None
    assert preview_box["y"] < submit_box["y"]
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_preview_card -v
```

Expected: FAIL (`protocol-preview` still after `submit-job`).

- [x] **Step 3: Write minimal implementation**

In `index.html` replace the Before bed actions/preview block with:

```html
          <p class="actions">
            <button id="load-example" type="button">Load example</button>
            <button id="preview-protocol" type="button">Preview protocol</button>
          </p>
          <p id="protocol-preview"></p>
          <p id="preflight-errors"></p>
          <p class="actions">
            <button id="submit-job" type="button" disabled>Freeze and submit</button>
            <span id="keyboard-hint">Ctrl/Cmd+Enter: Preview, then Freeze.</span>
          </p>
          <p id="host-constraint"></p>
```

`docs/webui.md`: the preview card sits above Freeze and submit.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_preview_card tests/runtime/test_static_console.py::test_packaged_console_keyboard_preview_then_freeze tests/runtime/test_static_console.py::test_packaged_assets_are_read_only_morning_copy -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: put the protocol preview above Freeze and submit"
```
