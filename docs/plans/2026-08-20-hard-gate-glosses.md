# Hard-gate checkbox glosses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `#field-hard-gates` labels keep `HardGateName` tokens plus locked human glosses.

**Architecture:** HTML label text only. Checkbox `value`s unchanged. Form JS still reads `.value`.

**Tech Stack:** packaged `index.html`, pytest static + existing e2e Load example.

**Spec:** `docs/requirements/2026-08-20-hard-gate-glosses.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not add a seventh gate.

---

### Task 1: Gloss labels

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_static_console.py`

- [x] **Step 1: Failing tests**

Add to `tests/runtime/test_static_console.py`:

```python
def test_packaged_hard_gates_keep_token_and_human_gloss():
    from alphaloop.contracts.gates import HardGateName

    html = files("alphaloop.webui.static").joinpath("index.html").read_text(
        encoding="utf-8"
    )
    start = html.find('id="field-hard-gates"')
    fieldset = html[start : html.find("</fieldset>", start)]
    for gate in HardGateName:
        assert f'value="{gate.value}"' in fieldset
    assert "dsr — Deflated Sharpe Ratio" in fieldset
    assert "walk_forward — walk-forward OOS" in fieldset
    assert "vs_random — versus random" in fieldset
    assert "vs_buy_hold — versus buy-and-hold" in fieldset
    assert "vs_benchmark — versus benchmark" in fieldset
    assert "data_consistency — data consistency" in fieldset
    assert fieldset.count('type="checkbox"') == len(HardGateName)
```

Keep `test_packaged_guided_form_preview_grid_and_job_cards` value loop.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_hard_gates_keep_token_and_human_gloss -v
```

Expected: FAIL (token-only labels, no em dash).

- [x] **Step 3: Implement** HTML labels with locked glosses. `docs/webui.md` one sentence after the signal-family sentence.

- [x] **Step 4: PASS** plus `test_packaged_guided_form_preview_grid_and_job_cards`

- [x] **Step 5: Commit**

```bash
git commit -m "feat(webui): gloss hard-gate checkboxes with locked names"
```
