# Guided hypothesis form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a researcher state a hypothesis from visible DSL kinds and hard gates, scan the planned trial grid before freeze, and read hypothesis plus `n_trials` on morning job cards — without changing research semantics.

**Architecture:** Packaged static HTML/CSS/JS only. The form is a recognition UI over the existing flat YAML submit payload. Preview still POSTs `/v1/jobs/preview`. Freeze still POSTs the textarea. Job cards use `data-run-id` / `data-status` / `data-outcome`; e2e helpers read those attributes. `list_jobs` already returns `hypothesis` and `n_trials`.

**Tech Stack:** Packaged static assets, existing Job API, pytest, Playwright.

## Global Constraints

- Local-first overnight lab. Do not promise alpha. Do not invent `FOUND`.
- No `FakeWorker` in morning e2e. Frozen Vite SPA. No webfont fetch.
- `HOST_CONSTRAINT` and help sentences stay locked.
- Use `python3`.

---

### Task 1: Failing static + e2e contract tests

**Files:**
- Modify: `tests/runtime/test_static_console.py`
- Modify: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Write the failing tests**

In `tests/runtime/test_static_console.py`, add:

```python
from alphaloop.contracts.gates import HardGateName
from alphaloop.contracts.research_spec import ALLOWED_PROFILES
from alphaloop.protocol.dsl import ALLOWED_KINDS


def test_packaged_guided_form_preview_grid_and_job_cards():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="hypothesis-form"' in html
    assert 'id="field-statement"' in html
    assert 'id="field-economic-logic"' in html
    assert 'id="field-signal-mechanism"' in html
    assert 'id="field-market-scope"' in html
    assert 'id="field-market-profile"' in html
    assert 'id="field-benchmark"' in html
    assert 'id="field-hard-gates"' in html
    assert 'id="field-seed"' in html
    assert 'id="field-time-budget"' in html
    assert 'id="field-cost-budget"' in html
    for kind in ALLOWED_KINDS:
        assert f'value="{kind}"' in html
    for profile in ALLOWED_PROFILES:
        assert f'value="{profile}"' in html
    for gate in HardGateName:
        assert f'value="{gate.value}"' in html
    assert "dataset.runId" in script or 'button.dataset.runId' in script
    assert "data-run-id" in script or "dataset.runId" in script
    assert "protocol-grid" in script
    assert "JSON.stringify(body.method_parameter_grid)" not in script
    assert "job.hypothesis" in script
    assert "n_trials" in script
    assert "override" not in script.lower()
    assert "override" not in html.lower()
    assert "field-statement:focus-visible" in css or "input:focus-visible" in css
```

Update the two assertions that require

```python
'job.run_id + " — " + job.status + " — " + job.research_outcome'
```

to instead require `dataset.runId` (or `data-run-id`) so the superseded list format is no longer locked.

In `tests/e2e/test_morning_console.py`, change helpers to read attributes:

```python
def _first_run_id(page) -> str:
    page.wait_for_selector("#job-list button", timeout=15000)
    run_id = page.locator("#job-list button").first.get_attribute("data-run-id")
    assert run_id
    return run_id


def _wait_list_outcome(page, timeout_ms: int = 60000) -> str:
    page.wait_for_function(
        """() => [...document.querySelectorAll('#job-list button')].some((button) =>
            /FOUND|NO_EVIDENCE|INCONCLUSIVE/.test(button.getAttribute('data-outcome') || ''))""",
        timeout=timeout_ms,
    )
    outcome = page.locator("#job-list button").first.get_attribute("data-outcome")
    assert outcome
    return outcome
```

Replace `textContent` / `inner_text` ` — ` parses and `includes('INCONCLUSIVE')` / `startsWith(runId)` waits with `data-outcome` / `data-run-id`.

Add:

```python
def test_load_example_fills_guided_form(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.click("#load-example")
    assert page.locator("#field-signal-mechanism").input_value() == "momentum_12_1"
    assert page.locator("#field-market-profile").input_value() == "us-equity-daily"
    assert page.locator("#field-statement").input_value().startswith("12-1 momentum")
    assert page.locator("#submit-job").is_disabled()


def test_job_card_shows_hypothesis_and_n_trials(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset))
    page.wait_for_selector("#job-list button[data-run-id]", timeout=15000)
    card = page.locator("#job-list button").first
    assert "12-1 momentum works in US large caps net of costs" in card.inner_text()
    assert "n_trials" in card.inner_text()
    assert card.get_attribute("data-run-id", timeout=1000).startswith("j_")


def test_preview_lists_grid_rows(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_yaml(page, _spec_yaml(dataset))
    assert "planned_n_trials" in page.locator("#protocol-preview").inner_text()
    assert page.locator("#protocol-grid li").count() >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_guided_form_preview_grid_and_job_cards -q
```

Expected: FAIL (`hypothesis-form` missing).

- [ ] **Step 3: Implement HTML form, JS sync, structured preview, job cards, CSS**

HTML inside `#submit`, above the YAML label:

Form fields as in the requirements table. Signal `<select>` options: empty `choose a signal`, then every `ALLOWED_KINDS` value. Profile: empty `choose a profile`, then `us-equity-daily`, `crypto-daily`. Hard-gate checkboxes inside `#field-hard-gates`. `onsubmit="return false"`. Keep `#spec-yaml`, `#load-example`, preview, freeze.

JS:

- `parseSpecYaml` / `extractDatasetYaml` / `formToYaml` / `yamlToForm` as specified in the requirements (flat keys; preserve `dataset:`).
- Form `input`/`change` rewrites textarea and disables freeze unless preview still matches.
- YAML `input` fills the form.
- `load-example` sets `EXAMPLE_SPEC`, fills the form, dispatches `input`.
- `renderPreview(body)` fills `#protocol-preview` with spec_id, statement, signal_mechanism, hard_gates, `planned_n_trials`, and a `#protocol-grid` `<ul>`. `formatGridRow`: `{}` if empty, else space-separated `key=value`.
- `loadJobs`: `button.dataset.runId = job.run_id` (DOM `data-run-id`), plus status/outcome. Child spans: `.job-id`, `.job-status`, `.job-outcome`, `.job-statement` (from `job.hypothesis.statement`), `.job-trials` (`n_trials: ` + job.n_trials). Do not join fields with ` — `.

CSS: form grid; `.job-statement` / `.job-trials` muted; `input:focus-visible, select:focus-visible, textarea:focus-visible`.

- [ ] **Step 4: Run static tests**

```bash
python3 -m pytest tests/runtime/test_static_console.py -q
```

Expected: PASS.

- [ ] **Step 5: Docs + nav**

Update `docs/webui.md` lead to mention the guided form. Register the requirements and this plan in `mkdocs.yml`.

- [ ] **Step 6: Commit**

```bash
git add tests/runtime/test_static_console.py tests/e2e/test_morning_console.py \
  src/alphaloop/webui/static docs/requirements/2026-08-20-guided-spec-form.md \
  docs/plans/2026-08-20-guided-spec-form.md docs/webui.md mkdocs.yml
git commit -m "feat(webui): guided hypothesis form, structured preview, job cards"
```
