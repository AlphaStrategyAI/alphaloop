# Before bed folds Run, Dataset, and Hard gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** First paint of Before bed shows Hypothesis and Market; Run, Dataset, and Hard gates start folded like YAML.

**Architecture:** Wrap the three existing fieldsets in closed `<details>`. Style folds like `#spec-yaml-fold`. Open `#fold-dataset` in e2e before fill / file picker.

**Tech Stack:** Packaged `index.html` / `styles.css`, pytest static + morning e2e.

**Spec:** `docs/requirements/2026-08-21-before-bed-folds.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not remove fieldset or input ids. Do not auto-submit.
- Do not restyle Load / Preview / Freeze tokens.

---

### Task 1: Fold secondary Before bed groups

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`
- Modify: `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Write the failing tests**

In `test_packaged_before_bed_groups_and_yaml_fold` add:

```python
    assert '<details id="fold-run">' in html
    assert '<details id="fold-dataset">' in html
    assert '<details id="fold-gates">' in html
    assert ">Run<" in html
    assert ">Dataset<" in html
    assert ">Hard gates<" in html
    assert html.find('id="group-market"') < html.find('id="fold-run"')
    assert html.find('id="fold-run"') < html.find('id="group-run"')
    assert html.find('id="fold-dataset"') < html.find('id="group-dataset"')
    assert html.find('id="fold-gates"') < html.find('id="field-hard-gates"')
    assert '<details id="fold-run" open' not in html
    assert '<details id="fold-dataset" open' not in html
    assert '<details id="fold-gates" open' not in html
    assert ".form-fold" in css
```

In `tests/e2e/test_morning_console.py` add helper and tests. Next to `_preview_yaml`:

```python
def _open_form_fold(page, fold_id: str) -> None:
    page.locator("#" + fold_id).evaluate("el => { el.open = true; }")
```

New e2e after `test_home_shows_promise_and_submit_form` (or after load-example):

```python
def test_before_bed_folds_run_dataset_and_gates(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    assert page.locator("#group-hypothesis").is_visible()
    assert page.locator("#group-market").is_visible()
    assert not page.locator("#group-run").is_visible()
    assert not page.locator("#group-dataset").is_visible()
    assert not page.locator("#field-hard-gates").is_visible()
    assert page.locator("#fold-run").is_visible()
    assert page.locator("#fold-dataset").is_visible()
    assert page.locator("#fold-gates").is_visible()
    _open_form_fold(page, "fold-dataset")
    assert page.locator("#field-dataset-file").is_visible()
```

In `test_dataset_file_picker_fills_identity_without_creating_a_job`,
`test_dataset_csv_picker_fills_identity_without_creating_a_job`, and
`test_empty_dataset_fields_preview_requires_snapshot`, call
`_open_form_fold(page, "fold-dataset")` before `set_input_files` /
`fill` on dataset controls.

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_before_bed_groups_and_yaml_fold -v
```

Expected: FAIL (`fold-run` missing).

- [x] **Step 3: Write minimal implementation**

Wrap `#group-run`, `#group-dataset`, and `#field-hard-gates` in closed details with class `form-fold` and the summaries above. Keep fieldset ids.

CSS: `.form-fold` matches `#spec-yaml-fold` chrome. Hide nested `legend` (clip). Strip inner fieldset border/padding so the details is the card.

`docs/webui.md`: Run, Dataset, and Hard gates start folded; Hypothesis and Market lead.

`mkdocs.yml`: register this requirements file and plan after Five-minute order.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_before_bed_groups_and_yaml_fold tests/runtime/test_static_console.py::test_packaged_guided_form_preview_grid_and_job_cards -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git commit -m "feat: fold Run, Dataset, and Hard gates on first paint"
```
