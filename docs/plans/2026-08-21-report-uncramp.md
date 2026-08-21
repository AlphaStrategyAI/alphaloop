# Sealed report is not clipped to 22rem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged `#report` sizes to sealed `report.md` instead of a nested 22rem clip now that Morning is the wide scrollport.

**Architecture:** Remove `max-height: 22rem` from `#report`. Keep overflow, type, and outcome chrome. No JS change.

**Tech Stack:** Packaged `styles.css`, pytest static + morning e2e.

**Spec:** `docs/requirements/2026-08-21-report-uncramp.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not change `write_report` bytes or `#report` `textContent` rendering.
- Do not restyle Load / Preview / Freeze tokens.

---

### Task 1: Drop the 22rem clip

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`
- Modify: `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_static_console.py` add:

```python
def test_packaged_console_report_is_not_clipped():
    root = files("alphaloop.webui.static")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    rule = css.find("#report {")
    assert rule != -1
    block = css[rule : css.find("}", rule)]
    assert "max-height" not in block
    assert "22rem" not in block
    assert "var(--fg)" in block
    assert '#report[data-outcome="FOUND"]' in css
    assert '#report[data-outcome="NO_EVIDENCE"]' in css
    assert '#report[data-outcome="INCONCLUSIVE"]' in css
    assert "http" not in css
```

In e2e `test_replay_rewrites_report_without_changing_page_outcome`, after the `data-outcome` assertion:

```python
    metrics = page.locator("#report").evaluate(
        """el => {
            const s = getComputedStyle(el);
            return { maxHeight: s.maxHeight, clientHeight: el.clientHeight };
        }"""
    )
    assert metrics["maxHeight"] == "none"
    assert metrics["clientHeight"] > 352
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_report_is_not_clipped -v
```

Expected: FAIL (`max-height` still in the `#report {` block).

- [x] **Step 3: Write minimal implementation**

In `styles.css` `#report` block, delete the `max-height: 22rem;` line. Keep `overflow: auto`.

`docs/webui.md`: the sealed report sizes to its content instead of a 22rem clip.

`mkdocs.yml`: register this requirements file and plan after Freeze reveal.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_report_is_not_clipped tests/runtime/test_static_console.py::test_packaged_console_freeze_reveals_morning_job -v
```

Expected: PASS (`#morning` still has `max-height`; `#report` does not).

- [x] **Step 5: Commit**

```bash
git commit -m "feat: let the sealed morning report size to its content"
```
