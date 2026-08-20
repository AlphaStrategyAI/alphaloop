# Replay five-minute verdict and honest PRD remaining work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop replay` prints the five-minute verdict from sealed artifacts, and PRD §13 stops listing shipped Phases 8–11 as remaining work.

**Architecture:** After `write_report`, build a small view from artifacts (outcome from `gates.json`, status from the job store when present) and reuse `format_status_verdict`. `--json` dumps that view. PRD §13 and the refactor pointer match `ROADMAP.md`.

**Tech Stack:** Python 3.9+, argparse, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-replay-verdict.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Replay stays offline (no daemon required). Do not re-run gates.
- No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs.
- Do not rewrite the body of `docs/plans/2026-08-19-overnight-lab-remaining-work.md`.

---

### Task 1: Replay verdict + honest PRD §13

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `docs/requirements/product-positioning-requirements.md`
- Modify: `docs/plans/overnight-research-lab-refactor.md`
- Modify: `docs/cli.md`, `README.md`, `docs/index.md`
- Modify: `src/alphaloop/skills/overnight-lab/SKILL.md`
- Modify: `mkdocs.yml`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`
- Test: `tests/skills/test_overnight_lab_skill.py`

**Interfaces:**
- Consumes: sealed `gates.json`, optional `{data_dir}/.alphaloop/state.db`
- Produces: `replay_view(...)` dict → `format_status_verdict` / `--json`

- [ ] **Step 1: Failing tests**

In `tests/runtime/test_morning.py`:

```python
def test_replay_view_uses_artifact_outcome_not_store_token():
    from alphaloop.runtime.morning import replay_view

    layout = RunLayout(tmp_path / "j_replay")
    # write FOUND gates.json as in test_replay_rewrites_report_without_looprunner
    view = replay_view(layout, research_outcome="FOUND", status="completed")
    assert view["research_outcome"] == "FOUND"
    assert view["status"] == "completed"
    assert view["stop_reason"] == "all_gates_passed"
    assert view["primary_evidence"] == "all required hard gates passed"
```

In `tests/runtime/test_cli_jobs.py`, extend
`test_replay_rewrites_report_without_looprunner`:

```python
assert captured.out.splitlines()[0] == "FOUND"
assert "FOUND means every required hard gate is present and passed." in captured.out
assert "Primary evidence:" in captured.out
assert "Stop reason: all_gates_passed" in captured.out
assert "Job status:" in captured.out
assert STATUS_NO_ALPHA in captured.out
assert "research_outcome:" not in captured.out
with pytest.raises(json.JSONDecodeError):
    json.loads(captured.out)
```

Add:

```python
def test_replay_parser_has_json_flag():
    parser = create_parser()
    assert parser.parse_args(["replay", "j_x", "--json"]).json is True
    assert parser.parse_args(["replay", "j_x"]).json is False


def test_replay_json_is_artifact_view(tmp_path, capsys):
    # same FOUND fixture
    rc = main(["replay", "j_replay", "--json", "--data-dir", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["research_outcome"] == "FOUND"
    assert payload["stop_reason"] == "all_gates_passed"
```

Optional store-backed: create `JobStore`, `store.create`, write FOUND
gates, replay default includes `Job status:` from the record.

In `tests/runtime/test_static_console.py`:

```python
def test_prd_section_13_does_not_list_phases_8_11_as_remaining():
    text = Path("docs/requirements/product-positioning-requirements.md").read_text(
        encoding="utf-8"
    )
    section = text.split("## 13. Implementation decomposition")[1]
    assert "Remaining first-release gaps are protocol gate returns" not in section
    assert "Phases 8–11 shipped" in section
    assert "soak" in section.lower()
    assert "N_{\\mathrm{eff}}" in section
    assert "n_trials" in section
    assert "MCP" in section
    assert "historical" in section.lower()


def test_refactor_remaining_work_pointer_is_historical():
    text = Path("docs/plans/overnight-research-lab-refactor.md").read_text(
        encoding="utf-8"
    )
    # the Phase 7 → Phase 8 join
    assert "Remaining first-release work is specified in" not in text
    assert "those phases shipped" in text.lower() or "Phases 8–11 shipped" in text
```

E2E `test_replay_rewrites_report_without_changing_page_outcome`:

```python
assert replayed.stdout.splitlines()[0] == outcome
assert "This status does not claim alpha or future profitability." in replayed.stdout
```

Skill (if SKILL mentions replay): `alphaloop replay` present.

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_replay_rewrites_report_without_looprunner tests/runtime/test_cli_jobs.py::test_replay_parser_has_json_flag tests/runtime/test_static_console.py::test_prd_section_13_does_not_list_phases_8_11_as_remaining -v
```

Expected: FAIL (`research_outcome:` still printed; PRD still has the
remaining-gaps sentence).

- [ ] **Step 3: Implement**

`replay_view(layout, *, research_outcome: str, status: str = "")` in
`morning.py`. Map outcome → `_STOP_REASONS` / `format_primary_evidence`
/ `_load_queued` / `build_qualifying_candidates` / `build_funnel`.

In `run_replay`, after `write_report`:

```python
status = ""
db = Path(args.data_dir) / ".alphaloop" / "state.db"
if db.is_file():
    from alphaloop.runtime.store import JobStore
    try:
        status = JobStore(db, Path(args.data_dir)).get(args.run_id).status.value
    except KeyError:
        status = ""
view = replay_view(layout, research_outcome=outcome.value, status=status)
if args.json:
    print(json.dumps(view, sort_keys=True))
else:
    print(format_status_verdict(view), end="")
```

Add `--json` on the replay parser.

PRD §13: replace the “Remaining first-release gaps are … (Phases 8–11)”
paragraph so Phases 8–11 shipped; remaining = soak execution, do not
shrink DSR `N` with \(N_{\mathrm{eff}}\), later MCP/cloud. Label the
remaining-work plan link historical.

Refactor: replace the Phase 7 closer with “Phases 8–11 shipped; the
remaining-work design is historical.”

`docs/cli.md` replay: default verdict, `--json`, rewrite `report.md`.
README / index one-liners. Skill: replay uses the same verdict as
status. Register the requirements and plan in `mkdocs.yml`.

- [ ] **Step 4: Tests pass**

```bash
python3 -m pytest tests/runtime/test_morning.py tests/runtime/test_cli_jobs.py tests/runtime/test_static_console.py tests/skills/test_overnight_lab_skill.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/runtime/morning.py src/alphaloop/cli/jobs.py src/alphaloop/skills/overnight-lab/SKILL.md docs tests/runtime/test_morning.py tests/runtime/test_cli_jobs.py tests/runtime/test_static_console.py tests/skills/test_overnight_lab_skill.py tests/e2e/test_morning_console.py README.md mkdocs.yml
git commit -m "feat(cli): print the five-minute verdict on replay"
```
