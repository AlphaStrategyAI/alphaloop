# Protocol preview market-profile gloss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI and packaged protocol preview name the frozen market profile with the same locked economics gloss as the guided form.

**Architecture:** `preview_run` adds `market_profile` (token) and `market_profile_label` via `gloss_market_profile`. CLI formatter and packaged `renderPreview` print that label with a raw-token fallback. No JS gloss table.

**Tech Stack:** Python 3.9+, packaged `app.js`, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-preview-profile-gloss.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not require preview before CLI submit. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not add a third profile.

---

### Task 1: Preview payload + CLI + packaged card

**Files:**
- Modify: `src/alphaloop/runtime/api.py`
- Modify: `src/alphaloop/cli/jobs.py`
- Modify: `src/alphaloop/webui/static/app.js`
- Modify: `docs/webui.md`, `docs/cli.md`
- Test: `tests/runtime/test_api.py`
- Test: `tests/runtime/test_cli_jobs.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `gloss_market_profile(name: str) -> str`
- Produces: `preview_run(...)["market_profile_label"]: str`

- [x] **Step 1: Write the failing tests**

In `tests/runtime/test_api.py` `test_preview_run_does_not_create_a_job`:

```python
    assert preview["market_profile"] == spec.hypothesis.market_profile
    assert preview["market_profile_label"] == (
        "us-equity-daily — US equities, NYSE, 5 bps, default SPY"
    )
```

In `tests/runtime/test_cli_jobs.py`
`test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets`,
add `market_profile` / `market_profile_label` to the fixture and:

```python
    assert "us-equity-daily — US equities, NYSE, 5 bps, default SPY" in text
    assert text.index("signal_mechanism:") < text.index("market_profile:")
    assert text.index("market_profile:") < text.index("hard_gates:")
```

In `test_packaged_console_preview_card`:

```python
    assert "market_profile_label" in script
    assert "MARKET_PROFILE_GLOSS" not in script
```

In e2e `test_preview_does_not_create_a_job`:

```python
    assert "NYSE" in text
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime/test_api.py::test_preview_run_does_not_create_a_job tests/runtime/test_cli_jobs.py::test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets tests/runtime/test_static_console.py::test_packaged_console_preview_card -v
```

Expected: FAIL (`market_profile_label` missing).

- [x] **Step 3: Write minimal implementation**

`preview_run` return dict, after `signal_label`:

```python
from alphaloop.protocol.profiles import gloss_market_profile
            "market_profile": spec.hypothesis.market_profile,
            "market_profile_label": gloss_market_profile(
                spec.hypothesis.market_profile
            ),
```

`format_protocol_preview`:

```python
    from alphaloop.protocol.profiles import gloss_market_profile
    profile = body.get("market_profile_label") or gloss_market_profile(
        str(body.get("market_profile") or "")
    )
            f"signal_mechanism: {signal}",
            f"market_profile: {profile}",
            f"hard_gates: {gates_text}",
```

`renderPreview` summary array, after signal_mechanism:

```javascript
    "market_profile: " + (body.market_profile_label || body.market_profile || ""),
```

`docs/webui.md` / `docs/cli.md`: preview names the market profile gloss.

- [x] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime/test_api.py::test_preview_run_does_not_create_a_job tests/runtime/test_cli_jobs.py::test_format_protocol_preview_leads_with_n_and_discloses_seed_budgets tests/runtime/test_static_console.py::test_packaged_console_preview_card -v
```

Expected: PASS

- [x] **Step 5: Commit**

```bash
git commit -m "feat: gloss frozen market_profile on protocol preview"
```
