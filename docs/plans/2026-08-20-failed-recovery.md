# Failed overnight recovery surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show stored worker `error` and `recovery_attempts` on the packaged morning console, with failed styling that is not FOUND green.

**Architecture:** Render existing `morning_view` fields. No new store columns. Failed CSS uses `--warn` and must not reuse `overnight-pulse`.

**Tech Stack:** Packaged static HTML/CSS/JS, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-failed-recovery.md`

## Global Constraints

- Do not invent `FOUND` or an error string. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `format_status_verdict`. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not auto-resume.

---

### Task 1: Error + recovery on the morning page

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

In `tests/runtime/test_static_console.py`:

```python
def test_packaged_console_failed_recovery_surface():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="job-error"' in html
    assert html.find('id="worker-heartbeat"') < html.find('id="job-error"')
    assert html.find('id="job-error"') < html.find('id="recovery-attempts"')
    assert "Worker error:" in script
    assert "Recovery attempts:" in script
    assert "job-recovery" in script
    assert "recovery: " in script
    assert 'data-status="failed"' in css
    assert "overnight-pulse" in css
    failed = css[css.find('data-status="failed"') :]
    assert "overnight-pulse" not in failed.split("@")[0]
    assert "http" not in css
    assert "override" not in script.lower()
```

E2E `test_home_shows_promise_and_submit_form`: `#job-error` and
`#recovery-attempts` count 1.

E2E `test_job_detail_while_running_or_later_legal_outcome`: those
nodes exist on the open detail.

- [x] **Step 2: Run tests — expect FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_failed_recovery_surface -v
```

Expected: FAIL (no `#job-error`).

- [x] **Step 3: Implement**

HTML: `#job-error` then `#recovery-attempts` after `#worker-heartbeat`.

`showJob`: fill error and recovery as specified. `loadJobs`: append
`.job-recovery` when `recovery_attempts > 0`.

CSS: failed selectors with `--warn` border; not `overnight-pulse`.
Muted color for the new nodes.

`docs/webui.md`: failed jobs show worker error, recovery count, Resume.

Register requirements + plan in `mkdocs.yml`.

- [x] **Step 4: Tests pass**

```bash
python3 -m pytest tests/runtime/test_static_console.py tests/runtime/test_morning.py -q
```

- [x] **Step 5: Commit**

```bash
git commit -m "feat(webui): show failed-job error and recovery attempts"
```
