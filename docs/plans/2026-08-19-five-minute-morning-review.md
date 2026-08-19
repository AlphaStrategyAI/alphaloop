# Five-minute morning review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the morning Job API, packaged Web console, and `report.md` sufficient for a five-minute trustworthy review, and align first-release docs with the overnight-lab positioning.

**Architecture:** Extend `morning_view` with `seed` and unique-ledger `n_trials`. The packaged static page lists `run_id — status — research_outcome` and renders hypothesis, job status, and spec meta. `write_report` becomes a paper view of the same fields plus a locked no-alpha sentence. Docs (`ROADMAP.md`, `docs/webui.md`, package/MkDocs descriptions) stop selling a different product.

**Tech Stack:** Existing `alphaloop` runtime, packaged `src/alphaloop/webui/static/`, pytest, Playwright e2e against a real daemon.

**Spec:** `docs/requirements/2026-08-19-five-minute-morning-review.md`

## Global Constraints

- Local-first overnight research lab; not a trading bot; do not promise alpha.
- `FOUND` only from complete `GateEvidence`. Do not invent `FOUND`.
- Packaged morning page is the first-release UI; frozen Vite SPA and `alphaloop.live` stay frozen.
- Morning e2e: real Chromium + real daemon; no `FakeWorker`. Supervisor isolation tests that already use `FakeWorker` stay.
- `HOST_CONSTRAINT` text is locked.
- Unique `n_trials` = `len(dict.fromkeys(trial_id))` from `trial-ledger.jsonl`.
- List separator is exactly ` — ` (space-em-dash-space). Research outcome is the **last** segment.
- Locked report sentence, verbatim: `This report does not claim alpha or future profitability.`
- Plans live under `docs/plans/` (repo convention).

---

### Task 1: Morning payload — seed and n_trials

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `tests/runtime/test_morning.py`
- Modify: `tests/runtime/test_api.py`

**Interfaces:**
- Consumes: `JobRecord.spec.seed`, `RunLayout.trial_ledger` via existing `_load_revisions`
- Produces: `morning_view(...) -> dict` gains `seed: int` and `n_trials: int`

- [ ] **Step 1: Write the failing tests**

Append to `tests/runtime/test_morning.py`:

```python
def test_morning_view_exposes_seed_and_unique_n_trials(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    run_dir = tmp_path / job.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trial-ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"trial_id": "c_1", "revision": "none"}),
                json.dumps({"trial_id": "c_1", "revision": "method"}),
                json.dumps({"trial_id": "c_2", "revision": "none"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["seed"] == job.spec.seed
    assert view["n_trials"] == 2
    assert view["spec_id"] == job.spec.spec_id


def test_morning_view_n_trials_zero_without_ledger(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(store.get(job.run_id), tmp_path)
    assert view["n_trials"] == 0
    assert view["seed"] == 7
```

In `tests/runtime/test_api.py`, extend `test_list_jobs_includes_research_outcome`:

```python
    assert listed["jobs"][0]["seed"] == created["seed"]
    assert listed["jobs"][0]["n_trials"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/runtime/test_morning.py::test_morning_view_exposes_seed_and_unique_n_trials tests/runtime/test_morning.py::test_morning_view_n_trials_zero_without_ledger tests/runtime/test_api.py::test_list_jobs_includes_research_outcome -v`

Expected: FAIL — `seed` / `n_trials` missing from `morning_view`.

- [ ] **Step 3: Minimal implementation**

In `src/alphaloop/runtime/morning.py`, add:

```python
def _n_trials(layout: RunLayout) -> int:
    ids: list[str] = []
    for row in _load_revisions(layout):
        trial_id = row.get("trial_id")
        if trial_id:
            ids.append(str(trial_id))
    return len(dict.fromkeys(ids))
```

Add to the `morning_view` return dict:

```python
        "seed": job.spec.seed,
        "n_trials": _n_trials(layout),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/runtime/test_morning.py tests/runtime/test_api.py::test_list_jobs_includes_research_outcome -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/morning.py tests/runtime/test_morning.py tests/runtime/test_api.py
git commit -m "feat(morning): expose seed and unique-ledger n_trials"
```

---

### Task 2: report.md as a five-minute paper artifact

**Files:**
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `src/alphaloop/runtime/worker.py`
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `tests/runtime/test_artifacts_io.py`

**Interfaces:**
- Consumes: `RunLayout`, optional `ResearchSpec`, optional `n_trials`
- Produces:

```python
NO_ALPHA_CLAIM = "This report does not claim alpha or future profitability."

def write_report(
    layout: RunLayout,
    *,
    research_outcome: str,
    stop_reason: str | None,
    spec: ResearchSpec | None = None,
    n_trials: int | None = None,
) -> Path:
```

When `n_trials` is `None`, count unique ledger `trial_id`s the same way as `_n_trials`.

- [ ] **Step 1: Write the failing test**

Replace `test_report_is_a_view_of_sealed_evidence` body and add a spec-aware test in `tests/runtime/test_artifacts_io.py`:

```python
def test_report_is_a_view_of_sealed_evidence(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    evidence = evaluate_hard_gates(
        (HardGateName.DSR,),
        (GateResult(name=HardGateName.DSR, passed=True, detail={}),),
    )
    layout.evidence.mkdir()
    (layout.evidence / "gates.json").write_text(json.dumps(evidence_to_dict(evidence)))
    write_report(layout, research_outcome="FOUND", stop_reason="all_gates_passed")
    text = layout.report.read_text(encoding="utf-8")
    assert "# Research conclusion" in text
    assert "This report does not claim alpha or future profitability." in text
    assert "FOUND" in text
    assert "all_gates_passed" in text
    assert "dsr" in text.lower()


def test_report_includes_frozen_hypothesis_and_n_trials(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir()
    spec = _spec()
    layout.trial_ledger.write_text(
        json.dumps({"trial_id": "c_1", "revision": "none"}) + "\n"
        + json.dumps({"trial_id": "c_1", "revision": "method"}) + "\n"
        + json.dumps({"trial_id": "c_2", "revision": "none"}) + "\n",
        encoding="utf-8",
    )
    write_report(
        layout,
        research_outcome="NO_EVIDENCE",
        stop_reason="hard_gate_failed",
        spec=spec,
    )
    text = layout.report.read_text(encoding="utf-8")
    assert "This report does not claim alpha or future profitability." in text
    assert f"spec_id: {spec.spec_id}" in text
    assert f"seed: {spec.seed}" in text
    assert "n_trials: 2" in text
    assert spec.hypothesis.statement in text
    assert "signal_mechanism: momentum_12_1" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/runtime/test_artifacts_io.py::test_report_is_a_view_of_sealed_evidence tests/runtime/test_artifacts_io.py::test_report_includes_frozen_hypothesis_and_n_trials -v`

Expected: FAIL — locked sentence / hypothesis fields missing.

- [ ] **Step 3: Implement write_report and callers**

In `src/alphaloop/runtime/artifacts_io.py`:

```python
NO_ALPHA_CLAIM = "This report does not claim alpha or future profitability."


def _unique_trial_count(layout: RunLayout) -> int:
    ids: list[str] = []
    for row in _ledger_rows(layout):
        trial_id = row.get("trial_id")
        if trial_id:
            ids.append(str(trial_id))
    return len(dict.fromkeys(ids))


def write_report(
    layout: RunLayout,
    *,
    research_outcome: str,
    stop_reason: str | None,
    spec: ResearchSpec | None = None,
    n_trials: int | None = None,
) -> Path:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
    if n_trials is None:
        n_trials = _unique_trial_count(layout)
    lines = ["# Research conclusion", "", NO_ALPHA_CLAIM, ""]
    lines.append(f"research_outcome: {research_outcome}")
    if stop_reason is not None:
        lines.append(f"stop_reason: {stop_reason}")
    if spec is not None:
        lines.append(f"spec_id: {spec.spec_id}")
        lines.append(f"seed: {spec.seed}")
        lines.append(f"n_trials: {n_trials}")
        hyp = spec.hypothesis
        lines.extend(
            [
                "",
                "## Frozen hypothesis",
                "",
                f"statement: {hyp.statement}",
                f"economic_logic: {hyp.economic_logic}",
                f"signal_mechanism: {hyp.signal_mechanism}",
                f"market_scope: {hyp.market_scope}",
                f"market_profile: {hyp.market_profile}",
                f"benchmark: {hyp.benchmark}",
            ]
        )
    gate_lines = _gate_result_lines(layout)
    if gate_lines:
        lines.extend(["", "## Gates", ""])
        lines.extend(gate_lines)
    layout.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return layout.report
```

Worker `_write_artifacts` must pass `spec=spec`.

In `src/alphaloop/cli/jobs.py` `run_replay`, keep the loaded spec:

```python
    spec = None
    spec_path = layout.research_spec
    if spec_path.is_file():
        try:
            payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("research spec must be a mapping")
            spec = ResearchSpec.from_dict(payload)
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
            print(f"error: unable to read research spec: {exc}", file=sys.stderr)
            return 2

    # ... existing evidence / outcome derivation ...

    write_report(
        layout,
        research_outcome=outcome.value,
        stop_reason=stop_reason,
        spec=spec,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/runtime/test_artifacts_io.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/artifacts_io.py src/alphaloop/runtime/worker.py src/alphaloop/cli/jobs.py tests/runtime/test_artifacts_io.py
git commit -m "feat(report): disclose hypothesis, n_trials, and no-alpha claim"
```

---

### Task 3: Packaged morning page

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `tests/runtime/test_static_console.py`
- Modify: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `morning_view` keys from Task 1
- Produces: list text `{run_id} — {status} — {research_outcome}`; detail ids `#job-status`, `#hypothesis-statement`, `#spec-meta`

- [ ] **Step 1: Write the failing static and e2e assertions**

In `test_packaged_assets_are_read_only_morning_copy` add:

```python
    assert 'id="job-status"' in html
    assert 'id="hypothesis-statement"' in html
    assert 'id="spec-meta"' in html
    assert 'job.run_id + " — " + job.status + " — " + job.research_outcome' in script
```

In `tests/e2e/test_morning_console.py` change helpers:

```python
def _list_research_outcome(text: str) -> str:
    return text.split(" — ")[-1].strip()


def _first_run_id(page) -> str:
    page.wait_for_selector("#job-list button", timeout=15000)
    text = page.locator("#job-list button").first.inner_text()
    return text.split(" — ")[0].strip()


def _wait_list_outcome(page, timeout_ms: int = 60000) -> str:
    page.wait_for_function(
        """() => [...document.querySelectorAll('#job-list button')].some((button) =>
            /FOUND|NO_EVIDENCE|INCONCLUSIVE/.test((button.textContent || '').split(' — ').pop() || ''))""",
        timeout=timeout_ms,
    )
    text = page.locator("#job-list button").first.inner_text()
    return _list_research_outcome(text)
```

In `test_job_detail_while_running_or_later_legal_outcome` after opening detail, add:

```python
    assert page.locator("#job-status").inner_text().startswith("Job status:")
    assert "12-1 momentum works in US large caps net of costs" in page.locator(
        "#hypothesis-statement"
    ).inner_text()
    meta = page.locator("#spec-meta").inner_text()
    assert "spec_id:" in meta
    assert "seed:" in meta
    assert "n_trials:" in meta
```

- [ ] **Step 2: Run static test to verify it fails**

Run: `python -m pytest tests/runtime/test_static_console.py::test_packaged_assets_are_read_only_morning_copy -v`

Expected: FAIL — new ids / list format missing.

- [ ] **Step 3: Implement HTML, JS, CSS**

`index.html` detail section:

```html
      <section id="detail" hidden>
        <p id="outcome" data-outcome></p>
        <p id="job-status"></p>
        <p id="hypothesis-statement"></p>
        <p id="spec-meta"></p>
        <p id="stop-reason"></p>
        ...
```

Legend spans:

```html
        <span data-outcome="FOUND">FOUND</span>
        ·
        <span data-outcome="NO_EVIDENCE">NO_EVIDENCE</span>
        ·
        <span data-outcome="INCONCLUSIVE">INCONCLUSIVE</span>
```

`app.js` list button:

```javascript
    button.textContent = job.run_id + " — " + job.status + " — " + job.research_outcome;
```

`showJob` after setting `#outcome`:

```javascript
  document.getElementById("job-status").textContent = "Job status: " + job.status;
  const statement =
    job.hypothesis && job.hypothesis.statement ? job.hypothesis.statement : "";
  document.getElementById("hypothesis-statement").textContent = statement;
  document.getElementById("spec-meta").textContent =
    "spec_id: " +
    job.spec_id +
    " · seed: " +
    job.seed +
    " · n_trials: " +
    job.n_trials;
```

`styles.css` — add distinct colors; `FOUND` keeps `--accent`:

```css
:root {
  --warn: #e8b86d;
  --inconclusive: #c9a0dc;
}

.legend span[data-outcome="FOUND"],
#outcome[data-outcome="FOUND"] {
  color: var(--accent);
}

.legend span[data-outcome="NO_EVIDENCE"],
#outcome[data-outcome="NO_EVIDENCE"] {
  color: var(--warn);
}

.legend span[data-outcome="INCONCLUSIVE"],
#outcome[data-outcome="INCONCLUSIVE"] {
  color: var(--inconclusive);
}

#outcome[data-outcome="NONE"] {
  color: var(--muted);
}
```

Remove the old `.legend span { color: var(--accent); }` rule so legend colors are per-outcome.

- [ ] **Step 4: Run static tests**

Run: `python -m pytest tests/runtime/test_static_console.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/webui/static tests/runtime/test_static_console.py tests/e2e/test_morning_console.py
git commit -m "feat(web): five-minute morning list and detail fields"
```

---

### Task 4: Align ROADMAP, WebUI docs, and package copy

**Files:**
- Modify: `ROADMAP.md`
- Modify: `docs/webui.md` (lead only; keep heritage SPA notes below a freeze banner)
- Modify: `pyproject.toml` `[project].description`
- Modify: `mkdocs.yml` `site_description` and nav entries for this spec/plan

**Interfaces:**
- Consumes: PRD positioning and this spec §R6
- Produces: docs that do not claim the loop finds alpha

- [ ] **Step 1: Rewrite ROADMAP.md**

Replace the file with an overnight-lab roadmap. Required statements:

- alphaloop is a local-first overnight research lab.
- Promise: submit in one minute; run overnight; understand a trustworthy conclusion in five minutes.
- Does not promise alpha or future profitability.
- First-release UI is the packaged morning page via `alphaloop start`.
- Remaining work: soak benchmark (not CI), protocol preview before freeze, optional later MCP for short job-control, cloud workers for hosts that cannot stay awake.
- Explicitly not first-release: trading, broker live path, unfreezing the Vite SPA, "find a strategy that beats SPY" as a command.

- [ ] **Step 2: Point docs/webui.md at the packaged page**

Open `docs/webui.md` with:

```markdown
# WebUI

The **first-release** morning UI is the packaged static page at
`src/alphaloop/webui/static/`, served by `alphaloop start` on loopback.
Submit a YAML research spec, leave the host awake, and review
`FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE` in the morning. Job status and
research outcome stay separate.

The Vite + React + TypeScript Quant Lab SPA under `webui/` is **frozen
heritage**. It is not the overnight-lab product UI. The notes below
document that frozen tree only.
```

Keep the rest of the file under a `## Frozen Quant Lab SPA (heritage)` heading.

- [ ] **Step 3: Package and MkDocs descriptions**

`pyproject.toml`:

```toml
description = "Local-first overnight research lab for constrained investment hypotheses. Submit before bed; review a trustworthy conclusion in the morning. Does not promise alpha."
```

`mkdocs.yml`:

```yaml
site_description: >-
  Local-first overnight research lab. Submit a constrained hypothesis
  before bed; review FOUND / NO_EVIDENCE / INCONCLUSIVE in the morning.
  Does not promise alpha.
```

Add nav:

```yaml
    - Five-minute morning review: requirements/2026-08-19-five-minute-morning-review.md
```

under Requirements, and under Plans:

```yaml
    - Five-minute morning review plan: plans/2026-08-19-five-minute-morning-review.md
```

- [ ] **Step 4: Grep the three files for forbidden copy**

Run: `rg -n "finds alpha|find a strategy that beats|MCP server" ROADMAP.md pyproject.toml mkdocs.yml docs/webui.md | head`

Expected: no "finds alpha" / "find a strategy that beats" in ROADMAP or package description. `docs/webui.md` may still mention heritage share URLs under the freeze banner.

- [ ] **Step 5: Commit**

```bash
git add ROADMAP.md docs/webui.md pyproject.toml mkdocs.yml docs/requirements/2026-08-19-five-minute-morning-review.md docs/plans/2026-08-19-five-minute-morning-review.md
git commit -m "docs: align roadmap and WebUI with overnight-lab morning review"
```

---

### Task 5: Full unit, integration, and e2e verification

**Files:**
- Test only (fix regressions if any)

- [ ] **Step 1: Unit + integration (exclude e2e/llm)**

Run: `python -m pytest -m "not e2e and not llm" -q`

Expected: PASS (existing skips for FastAPI extras allowed).

- [ ] **Step 2: E2E against real daemon + Chromium**

Run: `python -m pytest tests/e2e -m e2e -q`

Expected: existing matrix still passes; list outcome is last ` — ` segment; detail shows hypothesis and job status. Skip `FOUND`-after-cancel if the shortened worker did not seal `FOUND`.

- [ ] **Step 3: Fix any failures, re-run the failing command, then commit if needed**

Do not invent `FOUND`. Do not add `FakeWorker` to e2e.

---

## Spec coverage

| Requirement | Task |
| --- | --- |
| R1 seed + n_trials | Task 1 |
| R2 list format | Task 3 |
| R3 detail fields | Task 3 |
| R4 distinct colors | Task 3 |
| R5 report.md | Task 2 |
| R6 docs | Task 4 |
| Acceptance tests | Tasks 1–3, 5 |

## Placeholder scan

No TBD / later / "add tests for the above." Callers of `write_report` are named: `worker._write_artifacts`, `cli.jobs.run_replay`.
