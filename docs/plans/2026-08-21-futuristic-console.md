# Futuristic console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the packaged morning Web into a day/night handoff desk: stage nav, LOCAL instruments, graphite surfaces, short motion — without remapping locked semantic colors or unfreezing `webui/`.

**Architecture:** Keep the single packaged page. Add `#stage-nav` + `data-stage` on `#console` so Help is auxiliary and narrow viewports show one stage. Restyle `styles.css` around existing IDs and token RGBs. `app.js` only adds `setConsoleStage` / instrument refresh.

**Tech Stack:** packaged `index.html` / `styles.css` / `app.js`, pytest static, Playwright e2e.

**Spec:** `docs/requirements/2026-08-21-futuristic-console.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not remap `--accent` `#3ee0a0`, `--warn` `#ffb020`, `--inconclusive` `#c4a0ff`, `--focus` `#7eb8ff`, `--ink` `#0b0f16`, `--fg` `#f3efe6`.
- Keep `@keyframes overnight-pulse` and `prefers-reduced-motion` `animation: none`. Keep a `repeating-linear-gradient` string in CSS as an instrument hairline, not a body scan grid.
- No webfont `http`. No `override` in `app.js`. First `#morning {` block in CSS must remain the sticky Morning rule.

---

### Task 1: Stage nav and instruments (tests)

**Files:**
- Modify: `tests/runtime/test_static_console.py`
- Modify: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: packaged HTML/JS/CSS as served today
- Produces: failing assertions for `#stage-nav`, `#local-chip`, `setConsoleStage`, Help-as-auxiliary e2e

- [ ] **Step 1: Write the failing tests**

Add after `test_packaged_console_job_list_keys` in `tests/runtime/test_static_console.py`:

```python
def test_packaged_console_stage_nav_and_instruments():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="stage-nav"' in html
    assert 'id="stage-before-bed"' in html
    assert 'id="stage-morning"' in html
    assert 'id="stage-help"' in html
    assert 'id="local-chip"' in html
    assert ">LOCAL<" in html
    assert 'id="runtime-chip"' in html
    assert 'id="console" data-stage="before-bed"' in html
    assert "function setConsoleStage" in script
    assert "dataset.stage" in script
    assert "runtime-chip" in script
    assert "scrollIntoView" in script[
        script.find("async function submitJob") : script.find(
            'document.getElementById("load-example")'
        )
    ]
    assert "setConsoleStage" in script[
        script.find("async function submitJob") : script.find(
            'document.getElementById("load-example")'
        )
    ]
    assert "#stage-nav" in css
    assert 'data-stage="help"' in css
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()
```

In `tests/e2e/test_morning_console.py`, change `test_help_visible_without_opening_a_job` so it opens Help via stage nav, and add a narrow-viewport stage test after it:

```python
def test_help_visible_without_opening_a_job(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.click("#stage-help")
    assert page.locator("#help-no-alpha").inner_text() == (
        "This console does not claim alpha or future profitability."
    )
    assert HOST_CONSTRAINT in page.locator("#help-host").inner_text()
    assert page.locator("#help-status").inner_text() == (
        "Job status (queued, running, completed, failed, cancelled) is not the research conclusion."
    )
    assert page.locator("#help-found").inner_text() == (
        "FOUND means every required hard gate is present and passed. It is not a promise of alpha."
    )
    assert "target found" not in page.content()


def test_stage_nav_hides_help_until_selected(real_daemon, browser_page):
    page = browser_page
    page.set_viewport_size({"width": 480, "height": 900})
    _open_morning(page, real_daemon["base_url"])
    assert page.locator("#local-chip").inner_text() == "LOCAL"
    assert page.locator("#before-bed").is_visible()
    assert page.locator("#morning").is_hidden()
    assert page.locator("#help").is_hidden()
    page.click("#stage-morning")
    assert page.locator("#morning").is_visible()
    assert page.locator("#before-bed").is_hidden()
    assert page.locator("#empty-morning").is_visible()
    page.click("#stage-help")
    assert page.locator("#help").is_visible()
    assert page.locator("#help-no-alpha").is_visible()
    assert page.locator("#before-bed").is_hidden()
```

Also in `test_home_shows_promise_and_submit_form`, after the `#morning` count assertion, add:

```python
    assert page.locator("#stage-nav").count() == 1
    assert page.locator("#local-chip").inner_text() == "LOCAL"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_stage_nav_and_instruments -v
```

Expected: FAIL (`id="stage-nav"` missing).

- [ ] **Step 3: Commit tests**

```bash
git add tests/runtime/test_static_console.py tests/e2e/test_morning_console.py
git commit -m "test: require console stage nav and LOCAL instruments"
```

---

### Task 2: Stage nav and instruments (implementation)

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`

**Interfaces:**
- Consumes: Task 1 failing tests
- Produces: `setConsoleStage(stage)` where `stage` is `"before-bed" | "morning" | "help"`; `#console.dataset.stage`; `#runtime-chip` text `idle` or `N running`

- [ ] **Step 1: HTML**

Inside `#masthead`, wrap the kicker + `h1` and add instruments **without** changing existing copy:

```html
    <header id="masthead">
      <div class="masthead-row">
        <div class="masthead-brand">
          <p class="kicker">local overnight lab</p>
          <h1>alphaloop</h1>
        </div>
        <p class="instruments" aria-label="Runtime instruments">
          <span class="chip" id="local-chip">LOCAL</span>
          <span class="chip" id="runtime-chip">idle</span>
        </p>
      </div>
      <p class="promise">
```

Insert stage nav **between** `</header>` and `<main id="console">`. Change the main opening tag to `data-stage="before-bed"`:

```html
    <nav id="stage-nav" aria-label="Console stages">
      <button type="button" id="stage-before-bed" data-stage="before-bed" aria-current="page">Before bed</button>
      <button type="button" id="stage-morning" data-stage="morning">Morning</button>
      <button type="button" id="stage-help" data-stage="help">Help</button>
    </nav>
    <main id="console" data-stage="before-bed">
```

Do not edit Help paragraph text. Do not edit `#host-constraint`.

- [ ] **Step 2: JavaScript**

Add these functions above `document.getElementById("load-example")`:

```javascript
function setConsoleStage(stage) {
  const root = document.getElementById("console");
  const names = ["before-bed", "morning", "help"];
  if (names.indexOf(stage) === -1) {
    return;
  }
  root.dataset.stage = stage;
  names.forEach(function (name) {
    const button = document.getElementById("stage-" + name);
    if (!button) {
      return;
    }
    if (name === stage) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
  });
}

function refreshInstruments(jobs) {
  const chip = document.getElementById("runtime-chip");
  if (!chip) {
    return;
  }
  const running = (jobs || []).filter(function (job) {
    return job.status === "running";
  }).length;
  chip.textContent = running > 0 ? running + " running" : "idle";
  chip.dataset.status = running > 0 ? "running" : "idle";
}
```

In `loadJobs`, after `const jobs = data.jobs || [];` call `refreshInstruments(jobs);`.

In `submitJob`, after `currentRunId = body.run_id;` call `setConsoleStage("morning");` **before** `await loadJobs();`. Keep the existing `scrollIntoView({ block: "nearest" ...})` on the selected job.

Bind nav clicks and 1/2/3 (when not typing) at the bottom with the other listeners:

```javascript
document.getElementById("stage-nav").addEventListener("click", function (ev) {
  const button = ev.target.closest("button[data-stage]");
  if (!button) {
    return;
  }
  setConsoleStage(button.getAttribute("data-stage"));
});
```

Inside the existing `keydown` handler, after the typingInField early return, before ArrowDown:

```javascript
  if (ev.key === "1") {
    ev.preventDefault();
    setConsoleStage("before-bed");
    return;
  }
  if (ev.key === "2") {
    ev.preventDefault();
    setConsoleStage("morning");
    return;
  }
  if (ev.key === "3") {
    ev.preventDefault();
    setConsoleStage("help");
    return;
  }
```

- [ ] **Step 3: Run the static test**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_stage_nav_and_instruments -v
```

Expected: PASS once CSS Task 3 also adds `#stage-nav` and `data-stage="help"` (if this run fails on CSS selectors, continue to Task 3 immediately).

- [ ] **Step 4: Commit**

```bash
git add src/alphaloop/webui/static/index.html src/alphaloop/webui/static/app.js
git commit -m "feat: add Before bed / Morning / Help stage nav"
```

---

### Task 3: Graphite surfaces and stage CSS

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`

**Interfaces:**
- Consumes: `#stage-nav`, `.masthead-row`, `.chip`, `#console[data-stage]`
- Produces: no full-page body scan; instrument hairline still contains `repeating-linear-gradient`; 160ms transitions; stage visibility rules

- [ ] **Step 1: Failing surface assertion**

Add:

```python
def test_packaged_console_futuristic_surfaces():
    root = files("alphaloop.webui.static")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    body = css[css.find("html,") : css.find("#console {")]
    assert "radial-gradient" in body
    assert "repeating-linear-gradient" not in body
    assert "repeating-linear-gradient" in css
    assert "#stage-nav" in css
    assert "160ms" in css
    assert "prefers-reduced-motion" in css
    assert "transition: none" in css
    assert "animation: none" in css
    morning = css.find("#morning {")
    block = css[morning : css.find("}", morning)]
    assert "sticky" in block
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html
```

Run:

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_futuristic_surfaces -v
```

Expected: FAIL (`repeating-linear-gradient` still in the body background, or `160ms` / `transition: none` missing).

- [ ] **Step 2: CSS**

Keep `:root` token hex values unchanged. Change `html, body` background to atmosphere without a scan grid:

```css
html,
body {
  margin: 0;
  min-height: 100%;
  background:
    radial-gradient(1100px 480px at 8% -18%, rgba(126, 184, 255, 0.09), transparent 58%),
    radial-gradient(900px 420px at 92% -12%, rgba(62, 224, 160, 0.07), transparent 54%),
    linear-gradient(180deg, #070a11 0%, var(--bg) 42%);
  color: var(--fg);
  font-family: ui-sans-serif, "Segoe UI", system-ui, sans-serif;
  font-variant-numeric: tabular-nums;
}
```

Add after `#masthead`:

```css
.masthead-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.85rem 1.25rem;
}

.instruments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0;
}

.chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0.28rem 0.7rem;
  color: var(--muted);
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 0.68rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

#local-chip {
  color: var(--accent);
  border-color: rgba(62, 224, 160, 0.45);
}

#runtime-chip[data-status="running"] {
  color: var(--focus);
  border-color: rgba(126, 184, 255, 0.5);
  animation: overnight-pulse 2.4s ease-in-out infinite;
}

#stage-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  max-width: 92rem;
  margin: 0 auto;
  padding: 0.15rem 1.25rem 0.85rem;
  background:
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 23px,
      rgba(243, 239, 230, 0.035) 24px
    );
}

#stage-nav button {
  background: transparent;
  color: var(--muted);
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 0.42rem 0.95rem;
  margin: 0;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.72rem;
  transition: color 160ms ease, border-color 160ms ease, background 160ms ease;
}

#stage-nav button[aria-current="page"] {
  color: var(--fg);
  border-color: var(--line);
  background: var(--card);
}

#console[data-stage="before-bed"] #help,
#console[data-stage="morning"] #help {
  display: none;
}

@media (max-width: 55.99rem) {
  #console[data-stage="before-bed"] #morning,
  #console[data-stage="morning"] #before-bed,
  #console[data-stage="help"] #before-bed,
  #console[data-stage="help"] #morning {
    display: none;
  }
}

@media (min-width: 56rem) {
  #console[data-stage="help"] #before-bed,
  #console[data-stage="help"] #morning {
    display: none;
  }

  #console[data-stage="help"] {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

Do **not** add a second `#morning {` before the existing sticky rule.

Refine panels (keep IDs): add a 160ms transition on `#job-list button`, `#verdict`, and form groups. Expand `prefers-reduced-motion` to also set `transition: none` on `#stage-nav button` and `#job-list button`.

Optional polish that must not change locked button RGB: inner top highlight on `#submit`, `#detail`, `#protocol-preview`:

```css
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 38%),
    var(--card);
```

- [ ] **Step 3: Docs**

In `docs/webui.md` first-release paragraph, after “Load example uses designed secondary chrome”, add:

```
The masthead shows LOCAL and worker idle/running instruments. Stage
nav switches Before bed, Morning, and Help. On a narrow console only
the active stage is shown. On a wide console Before bed and Morning
stay side by side; Help replaces them. Freeze selects the Morning
stage. The canvas is graphite with restrained glows, not a full-page
scan overlay.
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_stage_nav_and_instruments tests/runtime/test_static_console.py::test_packaged_console_futuristic_surfaces tests/runtime/test_static_console.py::test_packaged_console_morning_verdict_stage tests/runtime/test_static_console.py::test_packaged_console_overnight_liveness tests/runtime/test_static_console.py::test_packaged_console_freeze_reveals_morning_job -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/webui/static/styles.css docs/webui.md tests/runtime/test_static_console.py
git commit -m "feat: restyle packaged console as a graphite handoff desk"
```

---

### Task 4: Full verification

**Files:** none beyond fixes if a test fails

- [ ] **Step 1: Unit**

```bash
python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration
```

Expected: PASS (existing count; no new failures).

- [ ] **Step 2: E2E**

```bash
python3 -m pytest tests/e2e -m e2e
```

Expected: PASS including Help-via-stage-nav and narrow stage switching.

- [ ] **Step 3: Visual check**

Start `alphaloop start` on loopback, open Before bed, Morning, and Help, and confirm the canvas is graphite, Help is auxiliary, locked button colors still match, and there is no full-page scan grid.
