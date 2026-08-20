# Honest published docs, in-console help, and five-minute gate evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the published site, CLI help, morning page, and `report.md` tell the overnight-lab story and show sealed hard-gate detail a five-minute reader can trust.

**Architecture:** One pure formatter (`format_gate_line`) turns a sealed `gates.json` row into a single evidence line. `morning_view` exposes `evidence_lines`; `write_report` and the packaged page consume that same string. Help copy is static HTML with locked sentences. Docs/CLI copy changes are tests against file and `--help` text.

**Tech Stack:** Python 3.9+, existing Job API, packaged static HTML/JS, pytest, Playwright e2e.

## Global Constraints

- Local-first overnight research lab. Not a trading bot. Do not promise alpha.
- `FOUND` only from complete `GateEvidence`. Do not invent `FOUND`.
- No Python in `.asb`. Frozen `alphaloop.live`. `alphaloop.protocol` must not import `live`, `webui`, or `runtime`.
- No `FakeWorker` in morning e2e.
- Do not change locked `HOST_CONSTRAINT` text.
- Use `python3`, not `python`.
- Repo plans live under `docs/plans/`, not `docs/superpowers/plans/`.

---

### Task 1: Gate-line formatter

**Files:**
- Create: (none)
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Test: `tests/runtime/test_artifacts_io.py`

**Interfaces:**
- Consumes: a `gates.json` result mapping with `name`, `passed`, optional `detail`
- Produces: `format_gate_line(row: Mapping[str, Any]) -> str`

- [ ] **Step 1: Write the failing test**

Add to `tests/runtime/test_artifacts_io.py`:

```python
from alphaloop.runtime.artifacts_io import format_gate_line


def test_format_gate_line_empty_detail():
    assert format_gate_line({"name": "dsr", "passed": True, "detail": {}}) == "dsr: pass"


def test_format_gate_line_walk_forward_order_and_bools():
    line = format_gate_line(
        {
            "name": "walk_forward",
            "passed": False,
            "detail": {
                "regime_stable": False,
                "oos_sharpe_median": 0.1234567,
                "first_half_sharpe": 1.0,
                "second_half_sharpe": -0.5,
                "returns_scope": "oos_walk_forward",
                "oos_sharpe_mean": 0.25,
                "ignored": "nope",
            },
        }
    )
    assert line.startswith("walk_forward: fail · ")
    assert "ignored=" not in line
    assert line == (
        "walk_forward: fail · returns_scope=oos_walk_forward · "
        "oos_sharpe_mean=0.25 · oos_sharpe_median=0.123457 · "
        "first_half_sharpe=1 · second_half_sharpe=-0.5 · regime_stable=false"
    )


def test_format_gate_line_dsr_n_trials():
    line = format_gate_line(
        {
            "name": "dsr",
            "passed": True,
            "detail": {"n_trials": 3, "dsr": 0.9, "returns_scope": "oos_walk_forward"},
        }
    )
    assert line == (
        "dsr: pass · returns_scope=oos_walk_forward · n_trials=3 · dsr=0.9"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/runtime/test_artifacts_io.py::test_format_gate_line_empty_detail tests/runtime/test_artifacts_io.py::test_format_gate_line_walk_forward_order_and_bools tests/runtime/test_artifacts_io.py::test_format_gate_line_dsr_n_trials -v`

Expected: FAIL — `format_gate_line` is not defined.

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/runtime/artifacts_io.py`, add `from typing import Any, Mapping` (keep existing imports) and:

```python
MORNING_DETAIL_KEYS = (
    "returns_scope",
    "n_trials",
    "dsr",
    "oos_sharpe_mean",
    "oos_sharpe_median",
    "first_half_sharpe",
    "second_half_sharpe",
    "regime_stable",
)


def _format_detail_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def format_gate_line(row: Mapping[str, Any]) -> str:
    name = str(row.get("name") or "")
    verdict = "pass" if row.get("passed") else "fail"
    parts = [f"{name}: {verdict}"]
    detail = row.get("detail") or {}
    if isinstance(detail, Mapping):
        for key in MORNING_DETAIL_KEYS:
            if key in detail:
                parts.append(f"{key}={_format_detail_value(detail[key])}")
    return " · ".join(parts)
```

Change `_gate_result_lines` to append `format_gate_line(row)` instead of building `{name}: {verdict}` itself. Keep the skip when `name` is missing.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/runtime/test_artifacts_io.py -v`

Expected: PASS. `0.1234567` formats as `0.123457` under `.6g`.

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/test_artifacts_io.py src/alphaloop/runtime/artifacts_io.py
git commit -m "feat: format sealed hard-gate detail for morning evidence lines"
```

---

### Task 2: `morning_view` evidence_lines

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Test: `tests/runtime/test_morning.py`

**Interfaces:**
- Consumes: `format_gate_line`
- Produces: `morning_view(...)["evidence_lines"]: list[str]`

- [ ] **Step 1: Write the failing test**

Add to `tests/runtime/test_morning.py`:

```python
def test_morning_view_evidence_lines_include_walk_forward_detail(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    required = (HardGateName.WALK_FORWARD,)
    evidence = evaluate_hard_gates(
        required,
        (
            GateResult(
                name=HardGateName.WALK_FORWARD,
                passed=False,
                detail={
                    "regime_stable": False,
                    "returns_scope": "oos_walk_forward",
                    "oos_sharpe_median": -0.2,
                },
            ),
        ),
    )
    evidence_dir = tmp_path / job.run_id / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    view = morning_view(store.complete_from_artifacts(job.run_id), tmp_path)
    assert view["evidence_lines"]
    line = view["evidence_lines"][0]
    assert line.startswith("walk_forward: fail")
    assert "regime_stable=false" in line
    assert "returns_scope=oos_walk_forward" in line
    assert "oos_sharpe_median=-0.2" in line


def test_morning_view_missing_evidence_has_empty_lines(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(store.complete_from_artifacts(job.run_id), tmp_path)
    assert view["evidence_lines"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/runtime/test_morning.py::test_morning_view_evidence_lines_include_walk_forward_detail tests/runtime/test_morning.py::test_morning_view_missing_evidence_has_empty_lines -v`

Expected: FAIL — KeyError `evidence_lines`.

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/runtime/morning.py`:

```python
from alphaloop.runtime.artifacts_io import format_gate_line
```

In `morning_view`, after loading `evidence`:

```python
    results = (evidence or {}).get("results") or []
    evidence_lines = [
        format_gate_line(row) for row in results if isinstance(row, dict)
    ]
```

Include `"evidence_lines": evidence_lines` in the returned dict.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/runtime/test_morning.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/test_morning.py src/alphaloop/runtime/morning.py
git commit -m "feat: expose formatted evidence_lines on the morning Job API"
```

---

### Task 3: Packaged help and evidence list

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Test: `tests/runtime/test_static_console.py`

**Interfaces:**
- Consumes: `job.evidence_lines`, `HOST_CONSTRAINT` text
- Produces: `#help` section; evidence `<li>` text from `evidence_lines`

- [ ] **Step 1: Write the failing test**

In `tests/runtime/test_static_console.py`, extend `test_packaged_assets_are_read_only_morning_copy` (or add a sibling) and import `HOST_CONSTRAINT`:

```python
from alphaloop.runtime.preflight import HOST_CONSTRAINT


def test_packaged_help_and_evidence_lines():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert 'id="help"' in html
    assert 'id="help-no-alpha"' in html
    assert "This console does not claim alpha or future profitability." in html
    assert 'id="help-status"' in html
    assert "Job status (queued, running, completed, failed, cancelled) is not the research conclusion." in html
    assert 'id="help-host"' in html
    assert HOST_CONSTRAINT in html
    assert 'id="help-found"' in html
    assert "FOUND means every required hard gate is present and passed. It is not a promise of alpha." in html
    assert "job.evidence_lines" in script
    assert "override" not in script.lower()
```

Also assert `#help` in `test_root_serves_packaged_html`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/runtime/test_static_console.py::test_packaged_help_and_evidence_lines -v`

Expected: FAIL — `#help` missing.

- [ ] **Step 3: Write minimal implementation**

Add before `</main>` in `src/alphaloop/webui/static/index.html`:

```html
      <section id="help">
        <h2>Help</h2>
        <p id="help-no-alpha">This console does not claim alpha or future profitability.</p>
        <p id="help-status">Job status (queued, running, completed, failed, cancelled) is not the research conclusion.</p>
        <p id="help-host">The host must remain awake while a local worker is running. Closing the browser or terminal does not stop a job, but suspending or powering off the host stops computation.</p>
        <p id="help-found">FOUND means every required hard gate is present and passed. It is not a promise of alpha.</p>
      </section>
```

The `#help-host` paragraph MUST equal `HOST_CONSTRAINT` exactly.

In `src/alphaloop/webui/static/app.js`, replace the evidence `fillList` call:

```javascript
  const evidenceItems =
    job.evidence_lines && job.evidence_lines.length
      ? job.evidence_lines
      : results;
  fillList(document.getElementById("evidence"), evidenceItems, function (row) {
    if (typeof row === "string") {
      return row;
    }
    return row.name + ": " + (row.passed ? "pass" : "fail");
  });
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/runtime/test_static_console.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/webui/static/index.html src/alphaloop/webui/static/app.js tests/runtime/test_static_console.py
git commit -m "feat(webui): in-console help and sealed gate evidence lines"
```

---

### Task 4: Published docs and CLI heritage copy

**Files:**
- Modify: `docs/index.md`
- Modify: `docs/cli.md`
- Modify: `docs/plans/2026-08-19-overnight-lab-remaining-work.md`
- Modify: `docs-site/index.md` (one-line heritage banner only)
- Modify: `mkdocs.yml`
- Modify: `src/alphaloop/cli/main.py` (`loop` help + goal example)
- Test: `tests/test_package_identity.py`

**Interfaces:**
- Consumes: README overnight-lab promise
- Produces: published home + `--help` that do not say `find alpha with DSR > 1.0`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_package_identity.py`:

```python
def test_published_home_is_overnight_lab():
    text = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert "find alpha with DSR > 1.0" not in text
    assert "does not promise alpha" in text.lower() or "does **not** promise alpha" in text
    assert "FOUND" in text
    assert "NO_EVIDENCE" in text
    assert "INCONCLUSIVE" in text
    assert "alphaloop start" in text


def test_loop_help_is_heritage_not_find_alpha():
    parser = create_parser()
    loop = [action for action in parser._subparsers._group_actions[0].choices["loop"]._actions]
    help_text = parser._subparsers._group_actions[0].choices["loop"].format_help()
    assert "find alpha with DSR > 1.0" not in help_text
    assert "heritage" in help_text.lower()
```

A simpler, more stable check:

```python
def test_loop_help_is_heritage_not_find_alpha(capsys):
    parser = create_parser()
    try:
        parser.parse_args(["loop", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "find alpha with DSR > 1.0" not in out
    assert "heritage" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_package_identity.py::test_published_home_is_overnight_lab tests/test_package_identity.py::test_loop_help_is_heritage_not_find_alpha -v`

Expected: FAIL — `docs/index.md` still contains `find alpha with DSR > 1.0`.

- [ ] **Step 3: Write minimal implementation**

Replace `docs/index.md` with overnight-lab copy aligned to README: promise, three outcomes, `alphaloop start`, YAML example, honest disclosure, links. Mention `alphaloop loop` only as heritage v0.7 DAG.

Update `docs/cli.md` lead: overnight-lab commands first; mark the `loop` section heritage and remove `find alpha with DSR > 1.0` from examples.

Prepend to `docs/plans/2026-08-19-overnight-lab-remaining-work.md`:

```markdown
> **Status (2026-08-20):** Historical design for Phases 8–11. Those
> phases shipped. Section 1 is **not** a current gap list.
```

Prepend to `docs-site/index.md`:

```markdown
> Heritage v0.7.2 copy. The published product site is MkDocs `docs/`.
```

`mkdocs.yml` nav: add this requirements doc and this plan under Requirements / Plans.

In `src/alphaloop/cli/main.py`:

```python
    loop_p = subparsers.add_parser(
        "loop",
        help="heritage v0.7 hybrid DAG (not the overnight lab)",
    )
    run_p.add_argument("goal", help="research goal (heritage DAG; not overnight-lab submit)")
```

Remove the `find alpha with DSR > 1.0` example from the `goal` help.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_package_identity.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/index.md docs/cli.md docs/plans/2026-08-19-overnight-lab-remaining-work.md docs-site/index.md mkdocs.yml src/alphaloop/cli/main.py tests/test_package_identity.py
git commit -m "docs: publish overnight-lab home and mark the DAG loop as heritage"
```

---

### Task 5: Overnight e2e and morning Chromium

**Files:**
- Modify: `tests/e2e/test_morning_console.py`
- Modify: `tests/runtime/test_overnight_e2e.py` (assert `report.md` contains `regime_stable=` when walk_forward ran)

**Interfaces:**
- Consumes: packaged `#help`, `evidence_lines` on GET `/v1/jobs/{id}`
- Produces: e2e coverage that a five-minute reader sees help and walk-forward detail

- [ ] **Step 1: Write the failing tests** (they may already pass for help after Task 3; walk-forward detail needs a completed job)

In `tests/e2e/test_morning_console.py`:

```python
from alphaloop.runtime.preflight import HOST_CONSTRAINT


def test_help_visible_without_opening_a_job(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    assert page.locator("#help-no-alpha").inner_text() == (
        "This console does not claim alpha or future profitability."
    )
    assert HOST_CONSTRAINT in page.locator("#help-host").inner_text()
    assert "target found" not in page.content()


def test_walk_forward_detail_visible_on_morning_page(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_wf_help")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.fill(
        "#spec-yaml",
        _spec_yaml(
            dataset,
            statement="MACD crossover works in US large caps net of costs",
            signal_mechanism="macd",
            hard_gates=["walk_forward"],
            time_budget_s=60,
        ),
    )
    page.click("#submit-job")
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    page.locator("#job-list button").first.click()
    page.wait_for_selector("#evidence li")
    text = page.locator("#evidence").inner_text()
    assert "walk_forward:" in text
    assert "regime_stable=" in text
```

Extend `tests/runtime/test_overnight_e2e.py` `test_macd_walk_forward_records_regime_stable` to read `report.md` and assert `regime_stable=` appears.

- [ ] **Step 2: Run unit/integration first, then e2e**

Run: `python3 -m pytest -m "not e2e and not llm"`

Then: `python3 -m pytest tests/e2e -m e2e`

Expected: PASS. If `#help-host` whitespace mismatches, fix HTML to match `HOST_CONSTRAINT` exactly.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_morning_console.py tests/runtime/test_overnight_e2e.py
git commit -m "test: assert morning help and walk-forward evidence on real daemon"
```

---

## Self-review

1. Spec coverage: R1 Task 1; R2 Task 2; R3 Task 3; R4 Task 1 `_gate_result_lines`; R5–R7 Task 4; e2e Task 5.
2. No TBD / later placeholders.
3. `format_gate_line` name is stable across tasks. `HOST_CONSTRAINT` is not rewritten.
