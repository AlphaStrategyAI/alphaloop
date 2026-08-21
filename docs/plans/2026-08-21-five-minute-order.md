# Five-minute lists above the sealed report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged morning detail shows qualifying / evidence / funnel / revisions / queued above the sealed `#report`.

**Architecture:** Reorder the existing nodes in `index.html`. No JS fill changes. Update the superseded static order assertion.

**Tech Stack:** Packaged `index.html`, pytest static + morning e2e.

**Spec:** `docs/requirements/2026-08-21-five-minute-order.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not change `write_report` bytes or list payloads.
- Do not restyle Load / Preview / Freeze tokens.

---

### Task 1: Reorder the five-minute cluster

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `docs/webui.md`
- Modify: `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Write the failing tests**

In `test_packaged_console_morning_report`, replace:

```python
    assert html.find('id="report"') < html.find('id="qualifying"')
```

with:

```python
    assert html.find('id="search-progress"') < html.find('id="qualifying"')
    assert html.find('id="qualifying"') < html.find('id="evidence"')
    assert html.find('id="evidence"') < html.find('id="funnel"')
    assert html.find('id="funnel"') < html.find('id="revisions"')
    assert html.find('id="revisions"') < html.find('id="queued"')
    assert html.find('id="queued"') < html.find('id="report"')
    assert html.find('id="replay-job"') < html.find('id="qualifying"')
```

In e2e `test_replay_rewrites_report_without_changing_page_outcome`, after the uncramp metrics:

```python
    qual_box = page.locator("#qualifying").bounding_box()
    report_box = page.locator("#report").bounding_box()
    assert qual_box is not None and report_box is not None
    assert qual_box["y"] < report_box["y"]
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_report -v
```

Expected: FAIL (`#report` still before `#qualifying`).

- [x] **Step 3: Write minimal implementation**

In `index.html` `#detail`, move the five-minute headings and lists to sit after `#search-progress` and before `#report`:

```html
          <div id="search-progress"></div>
          <h3>Qualifying candidates</h3>
          <ul id="qualifying"></ul>
          <h3>Evidence</h3>
          <ul id="evidence"></ul>
          <h3>Elimination funnel</h3>
          <p id="funnel-summary"></p>
          <div id="funnel-bars"></div>
          <ul id="funnel"></ul>
          <h3>Methodological revisions</h3>
          <ul id="revisions"></ul>
          <h3>Queued hypotheses</h3>
          <ul id="queued"></ul>
          <pre id="report"></pre>
```

Keep verdict, status, lifecycle `.actions`, hypothesis, and spec-meta where they are.

`docs/webui.md`: the five-minute lists sit above the sealed report.

`mkdocs.yml`: register this requirements file and plan after Report uncramp.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_morning_report tests/runtime/test_static_console.py::test_packaged_console_replay_report tests/runtime/test_static_console.py::test_packaged_console_report_is_not_clipped -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git commit -m "feat: put five-minute lists above the sealed morning report"
```
