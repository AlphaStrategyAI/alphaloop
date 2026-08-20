# Market profile frozen-economics glosses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `#field-market-profile` keeps `ALLOWED_PROFILES` values and discloses calendar, costs, and default benchmark.

**Architecture:** HTML option labels only. Option `value`s unchanged. Form JS still reads `.value`.

**Tech Stack:** packaged `index.html`, pytest static + existing e2e Load example.

**Spec:** `docs/requirements/2026-08-20-profile-glosses.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not add a third profile. Do not auto-fill benchmark.

---

### Task 1: Gloss labels

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_static_console.py`

- [x] **Step 1: Failing tests**

Add to `tests/runtime/test_static_console.py`:

```python
def test_packaged_market_profile_discloses_frozen_economics():
    from alphaloop.contracts.research_spec import ALLOWED_PROFILES
    from alphaloop.protocol.profiles import CRYPTO_DAILY, US_EQUITY_DAILY

    html = files("alphaloop.webui.static").joinpath("index.html").read_text(
        encoding="utf-8"
    )
    start = html.find('id="field-market-profile"')
    select = html[start : html.find("</select>", start)]
    assert 'value="">choose a profile' in select or 'value="">choose a profile</option>' in select
    for profile in ALLOWED_PROFILES:
        assert f'value="{profile}"' in select
    assert "us-equity-daily — US equities, NYSE, 5 bps, default SPY" in select
    assert "crypto-daily — crypto, 24/7, 10 bps, default BTC-USD" in select
    assert str(int(US_EQUITY_DAILY.cost_bps)) in select
    assert str(int(CRYPTO_DAILY.cost_bps)) in select
    assert US_EQUITY_DAILY.default_benchmark in select
    assert CRYPTO_DAILY.default_benchmark in select
    assert select.count("<option") == 1 + len(ALLOWED_PROFILES)
```

Keep `test_packaged_guided_form_preview_grid_and_job_cards` value loop.

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_market_profile_discloses_frozen_economics -v
```

Expected: FAIL (token-only labels).

- [x] **Step 3: Implement** HTML labels with locked glosses. `docs/webui.md` one sentence after the hard-gate sentence.

- [x] **Step 4: PASS** plus `test_packaged_guided_form_preview_grid_and_job_cards`

- [x] **Step 5: Commit**

```bash
git commit -m "feat(webui): disclose calendar, costs, and default benchmark on market profiles"
```
