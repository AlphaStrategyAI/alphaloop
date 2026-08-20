# Morning elimination funnel bars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the existing search-wide funnel as a stacked count bar and per-gate tracks so a five-minute reader sees how the grid died without parsing muted text.

**Architecture:** Keep `build_funnel` / `morning_view.funnel` unchanged. Teach the packaged static page to render `#funnel-bars` from those counts.

**Tech Stack:** Packaged HTML/CSS/JS under `src/alphaloop/webui/static/`, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-funnel-bars.md`

## Global Constraints

- Do not promise alpha. Do not invent `FOUND`. No new hard gate.
- `HOST_CONSTRAINT` and help sentences stay locked. No `FakeWorker` in morning e2e.
- Do not unfreeze the Vite SPA under `webui/`.

---

### Task 1: Packaged assets + unit assertions

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `job.funnel.n_evaluated`, `n_passed`, `n_failed`, `n_incomplete`, `failure_counts`, `dominant_failures`
- Produces: `#funnel-bars .funnel-stack .funnel-seg[data-key][data-pct]`; `#funnel .funnel-fail-fill[data-pct]`

- [ ] **Step 1: Write the failing tests**

In `test_packaged_guided_form_preview_grid_and_job_cards` (or a new `test_packaged_funnel_bars`):

```python
def test_packaged_funnel_bars():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="funnel-bars"' in html
    assert "funnel-stack" in script
    assert "funnel-seg" in script
    assert "data-pct" in script
    assert "incomplete:" in script
    assert "funnel-fail-fill" in script
    assert ".funnel-stack" in css
    assert ".funnel-seg[data-key=\"passed\"]" in css
    assert ".funnel-seg[data-key=\"failed\"]" in css
    assert ".funnel-seg[data-key=\"incomplete\"]" in css
```

In `test_job_detail_while_running_or_later_legal_outcome`:

```python
    assert page.locator("#funnel-bars").count() == 1
```

In `test_terminal_outcome_matches_cli_status` after opening detail:

```python
    page.wait_for_selector("#funnel-bars .funnel-stack")
    passed = page.locator('#funnel-bars .funnel-seg[data-key="passed"]')
    assert passed.count() == 1
    assert passed.get_attribute("data-pct") is not None
```

- [ ] **Step 2: Run the static test to verify it fails**

Run: `python3 -m pytest tests/runtime/test_static_console.py::test_packaged_funnel_bars -v`

Expected: FAIL (missing `#funnel-bars`).

- [ ] **Step 3: Implement**

`index.html` after `#funnel-summary`:

```html
          <div id="funnel-bars"></div>
```

`app.js` helpers and `showJob` funnel block:

```javascript
function funnelPct(part, whole) {
  const denom = whole > 0 ? whole : 1;
  const pct = Math.round((Number(part) || 0) / denom * 100);
  if (pct < 0) {
    return 0;
  }
  if (pct > 100) {
    return 100;
  }
  return pct;
}

function appendFunnelSeg(stack, key, count, whole) {
  const seg = document.createElement("span");
  seg.className = "funnel-seg";
  seg.dataset.key = key;
  const pct = funnelPct(count, whole);
  seg.dataset.pct = String(pct);
  seg.style.width = pct + "%";
  stack.appendChild(seg);
}

function fillFunnel(job) {
  const funnel = job.funnel || {};
  const evaluated = funnel.n_evaluated || 0;
  const passed = funnel.n_passed || 0;
  const failed = funnel.n_failed || 0;
  const incomplete = funnel.n_incomplete || 0;
  document.getElementById("funnel-summary").textContent = [
    "evaluated: " + evaluated,
    "passed: " + passed,
    "failed: " + failed,
    "incomplete: " + incomplete,
  ].join(" · ");
  const bars = document.getElementById("funnel-bars");
  bars.innerHTML = "";
  if (evaluated + passed + failed + incomplete > 0) {
    const stack = document.createElement("div");
    stack.className = "funnel-stack";
    const whole = evaluated > 0 ? evaluated : passed + failed + incomplete;
    appendFunnelSeg(stack, "passed", passed, whole);
    appendFunnelSeg(stack, "failed", failed, whole);
    appendFunnelSeg(stack, "incomplete", incomplete, whole);
    bars.appendChild(stack);
  }
  const counts = funnel.failure_counts || {};
  fillList(
    document.getElementById("funnel"),
    funnel.dominant_failures,
    function (name) {
      return name;
    }
  );
  const items = document.getElementById("funnel").querySelectorAll("li");
  Array.prototype.forEach.call(items, function (li) {
    if (li.textContent === "none") {
      return;
    }
    const name = li.textContent;
    const count = counts[name] || 0;
    li.className = "funnel-fail";
    li.textContent = "";
    const label = document.createElement("span");
    label.textContent = name + " × " + count;
    const track = document.createElement("span");
    track.className = "funnel-fail-track";
    const fill = document.createElement("span");
    fill.className = "funnel-fail-fill";
    const pct = funnelPct(count, failed);
    fill.dataset.pct = String(pct);
    fill.style.width = pct + "%";
    track.appendChild(fill);
    li.appendChild(label);
    li.appendChild(track);
  });
}
```

Replace the existing `fillList(#funnel)` + `#funnel-summary` block in `showJob` with `fillFunnel(job)`.

CSS:

```css
.funnel-stack {
  display: flex;
  height: 1.15rem;
  border-radius: 999px;
  overflow: hidden;
  background: var(--line);
  margin: 0.7rem 0 1rem;
}
.funnel-seg {
  display: block;
  height: 100%;
  min-width: 0;
}
.funnel-seg[data-key="passed"] {
  background: var(--accent);
}
.funnel-seg[data-key="failed"] {
  background: var(--warn);
}
.funnel-seg[data-key="incomplete"] {
  background: var(--inconclusive);
}
#funnel li.funnel-fail {
  display: grid;
  grid-template-columns: minmax(7rem, 12rem) minmax(4rem, 1fr);
  gap: 0.5rem;
  align-items: center;
  margin: 0.4rem 0;
}
#funnel .funnel-fail-track {
  height: 0.55rem;
  background: var(--line);
  border-radius: 999px;
  overflow: hidden;
}
#funnel .funnel-fail-fill {
  display: block;
  height: 100%;
  background: var(--warn);
}
```

- [ ] **Step 4:** unit then e2e.

```bash
python3 -m pytest tests/runtime/test_static_console.py -q
python3 -m pytest tests/e2e -m e2e -q
```

- [ ] **Step 5: Commit**

---

### Task 2: Docs nav + majority-folds loop-exit pointer

**Files:**
- Modify: `mkdocs.yml`
- Modify: `docs/requirements/2026-08-20-majority-folds.md`

- [ ] Add nav entries next to Morning funnel.
- [ ] Point majority-folds remaining product at this cycle.
- [ ] Commit with the feature if not already included.
