# Freeze reveals the selected morning job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After Freeze, the selected morning job is on screen; on a wide console Morning stays visible while Before bed scrolls.

**Architecture:** `submitJob` scrolls the selected job card into view after a successful `loadJobs`. CSS `position: sticky` on `#morning` at the two-column breakpoint. Polling `loadJobs` does not scroll.

**Tech Stack:** Packaged `app.js` / `styles.css`, pytest static + morning e2e.

**Spec:** `docs/requirements/2026-08-21-freeze-reveal.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not auto-submit. Do not restyle Load / Preview / Freeze tokens.
- Do not call `scrollIntoView` from `loadJobs`.

---

### Task 1: Reveal after Freeze + sticky Morning

**Files:**
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`
- Modify: `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_static_console.py` add:

```python
def test_packaged_console_freeze_reveals_morning_job():
    root = files("alphaloop.webui.static")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    submit = script[
        script.find("async function submitJob") : script.find(
            'document.getElementById("load-example")'
        )
    ]
    load = script[
        script.find("async function loadJobs") : script.find("let previewedYaml")
    ]
    assert "scrollIntoView" in submit
    assert 'block: "nearest"' in submit
    assert "aria-current" in submit
    assert "scrollIntoView" not in load
    morning = css.find("#morning {")
    assert morning != -1
    block = css[morning : css.find("}", morning)]
    assert "sticky" in block
    assert "top:" in block
    assert "max-height" in block
    assert "http" not in css
    assert "override" not in script.lower()
```

In `tests/e2e/test_morning_console.py`, after `test_valid_submit_shows_host_constraint_and_job_row`:

```python
def test_freeze_reveals_selected_morning_job(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    page.set_viewport_size({"width": 800, "height": 560})
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset))
    page.wait_for_function(
        """() => {
            const el = document.querySelector('#job-list button[aria-current="true"]');
            if (!el) return false;
            const r = el.getBoundingClientRect();
            return r.bottom > 0 && r.top < window.innerHeight;
        }""",
        timeout=15000,
    )


def test_wide_morning_stays_visible_at_freeze(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    page.set_viewport_size({"width": 1280, "height": 560})
    _open_morning(page, real_daemon["base_url"])
    _preview_yaml(page, _spec_yaml(dataset))
    page.locator("#submit-job").scroll_into_view_if_needed()
    metrics = page.evaluate(
        """() => {
            const morning = document.getElementById("morning").getBoundingClientRect();
            const bed = document.getElementById("before-bed").getBoundingClientRect();
            const freeze = document.getElementById("submit-job").getBoundingClientRect();
            return {
                morningVisible: morning.bottom > 0 && morning.top < window.innerHeight,
                freezeVisible: freeze.bottom > 0 && freeze.top < window.innerHeight,
                bedHeight: bed.height,
                vh: window.innerHeight,
            };
        }"""
    )
    assert metrics["bedHeight"] > metrics["vh"]
    assert metrics["freezeVisible"]
    assert metrics["morningVisible"]
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_freeze_reveals_morning_job -v
```

Expected: FAIL (`scrollIntoView` missing from `submitJob`, or `#morning {` missing).

- [x] **Step 3: Write minimal implementation**

In `submitJob`, after `await loadJobs();`:

```javascript
  const selected = document.querySelector('#job-list button[aria-current="true"]');
  const target = selected || document.getElementById("morning");
  if (target) {
    target.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
```

In `styles.css` `@media (min-width: 56rem)` block, add:

```css
  #morning {
    position: sticky;
    top: 1rem;
    max-height: calc(100vh - 2rem);
    overflow: auto;
  }
```

`docs/webui.md`: Freeze reveals the selected morning job. On a wide
console Morning stays visible while Before bed scrolls.

`mkdocs.yml`: register this requirements file and plan after Console
replay.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_freeze_reveals_morning_job -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git commit -m "feat: reveal the selected morning job after Freeze"
```
