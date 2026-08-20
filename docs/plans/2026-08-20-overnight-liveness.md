# Overnight liveness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show overnight worker liveness on the packaged console: `heartbeat_at` on `morning_view`, a running pulse that is not FOUND green, and an honest heartbeat line.

**Architecture:** Add `heartbeat_at` to `morning_view`. `showJob` fills `#worker-heartbeat` and sets `#verdict[data-status]`. CSS animates running cards/verdict with `--focus`, disabled under `prefers-reduced-motion`.

**Tech Stack:** Python 3.9+, packaged static HTML/CSS/JS, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-overnight-liveness.md`

## Global Constraints

- Do not invent `FOUND` or a heartbeat. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `format_status_verdict`. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs.

---

### Task 1: Heartbeat payload + running pulse

**Files:**
- Modify: `src/alphaloop/runtime/morning.py`
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_morning.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

In `tests/runtime/test_morning.py`:

```python
def test_morning_view_exposes_heartbeat_at(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    job = store.create(_spec())
    view = morning_view(job, tmp_path)
    assert view["heartbeat_at"] is None
    beat = store.set_heartbeat(job.run_id, pid=7, at="2026-08-20T00:00:00+00:00")
    view = morning_view(beat, tmp_path)
    assert view["heartbeat_at"] == "2026-08-20T00:00:00+00:00"
```

In `tests/runtime/test_static_console.py`:

```python
def test_packaged_console_overnight_liveness():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="worker-heartbeat"' in html
    assert html.find('id="job-status"') < html.find('id="worker-heartbeat"')
    assert "Worker heartbeat:" in script
    assert "verdict.dataset.status" in script or 'verdict.dataset.status =' in script
    assert "overnight-pulse" in css
    assert 'data-status="running"' in css
    assert "prefers-reduced-motion" in css
    assert "animation: none" in css
    assert "http" not in css
    assert "override" not in script.lower()
```

E2E `test_home_shows_promise_and_submit_form`: `#worker-heartbeat` count is 1.

E2E `test_job_detail_while_running_or_later_legal_outcome`: `#verdict` has `data-status`; `#job-list button` has `data-status`; `#worker-heartbeat` is present.

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python3 -m pytest tests/runtime/test_morning.py::test_morning_view_exposes_heartbeat_at tests/runtime/test_static_console.py::test_packaged_console_overnight_liveness -v
```

Expected: FAIL (no `heartbeat_at` / no `#worker-heartbeat`).

- [ ] **Step 3: Implement**

`morning_view`: `"heartbeat_at": job.heartbeat_at`.

HTML: `<p id="worker-heartbeat"></p>` after `#job-status`.

`showJob`: `verdict.dataset.status = job.status`; fill `#worker-heartbeat` as specified.

CSS: `@keyframes overnight-pulse` using `--focus`; running selectors; reduced-motion none. Do not use `--accent` in the running pulse.

`docs/webui.md`: one sentence that running jobs pulse and show `Worker heartbeat:` when the timestamp exists.

Register requirements + plan in `mkdocs.yml`.

- [ ] **Step 4: Tests pass**

```bash
python3 -m pytest tests/runtime/test_morning.py tests/runtime/test_static_console.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): show overnight worker liveness on the morning console"
```
