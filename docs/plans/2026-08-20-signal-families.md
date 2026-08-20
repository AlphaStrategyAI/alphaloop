# Signal family optgroups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `#field-signal-mechanism` groups directional kinds by Trend / Mean reversion / Relative value with human glosses.

**Architecture:** HTML only. Option `value`s unchanged. Form JS still reads `.value`.

**Tech Stack:** packaged `index.html`, pytest static + existing e2e Load example.

**Spec:** `docs/requirements/2026-08-20-signal-families.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not add Parkinson/OBV.

---

### Task 1: Optgroups + glosses

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_static_console.py`

- [ ] **Step 1: Failing tests**

Add to `tests/runtime/test_static_console.py`:

```python
def test_packaged_signal_select_groups_economic_families():
    from alphaloop.protocol.recommend import REVERSION_KINDS, TREND_KINDS

    html = files("alphaloop.webui.static").joinpath("index.html").read_text(
        encoding="utf-8"
    )
    select = html[
        html.find('id="field-signal-mechanism"') : html.find(
            "</select>", html.find('id="field-signal-mechanism"')
        )
    ]
    assert '<optgroup label="Trend">' in select
    assert '<optgroup label="Mean reversion">' in select
    assert '<optgroup label="Relative value">' in select
    for kind in TREND_KINDS:
        assert f'value="{kind}"' in select.split('<optgroup label="Trend">')[1].split(
            "</optgroup>"
        )[0]
    for kind in REVERSION_KINDS:
        assert f'value="{kind}"' in select.split(
            '<optgroup label="Mean reversion">'
        )[1].split("</optgroup>")[0]
    assert 'value="pairs_spread"' in select.split(
        '<optgroup label="Relative value">'
    )[1]
    assert "momentum_12_1 — 12-1 momentum" in select
    assert "rsi — RSI" in select
    assert "pairs_spread — pairs spread" in select
    assert 'value="parkinson_hist_vol"' not in select
```

Keep `test_packaged_guided_form_preview_grid_and_job_cards` value loop.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_signal_select_groups_economic_families -v
```

- [ ] **Step 3: Implement** HTML optgroups with locked glosses. `docs/webui.md` one sentence.

- [ ] **Step 4: PASS** plus `test_packaged_guided_form_preview_grid_and_job_cards`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): group overnight signals by economic family"
```
