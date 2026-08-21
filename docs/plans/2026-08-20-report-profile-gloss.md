# Sealed report frozen-profile gloss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `report.md` (and `#report`) names the frozen `market_profile` with the same locked economics gloss as the guided form.

**Architecture:** Canonical `MARKET_PROFILE_GLOSS` / `gloss_market_profile` on `protocol.profiles`. `write_report` interpolates it. Packaged HTML already has the same strings; a static test ties them together. YAML / EXAMPLE_SPEC stay tokens.

**Tech Stack:** Python 3.9+, pytest, existing morning e2e.

**Spec:** `docs/requirements/2026-08-20-report-profile-gloss.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not unfreeze `webui/`. Do not shrink DSR `N`. Do not start soak jobs.
- Do not add a third profile. Do not add preview `market_profile` this cycle.

---

### Task 1: Shared gloss + report line

**Files:**
- Modify: `src/alphaloop/protocol/profiles/__init__.py`
- Modify: `src/alphaloop/runtime/artifacts_io.py`
- Modify: `docs/webui.md`
- Test: `tests/protocol/test_profiles.py`
- Test: `tests/runtime/test_artifacts_io.py`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

**Interfaces:**
- Produces: `gloss_market_profile(name: str) -> str`

- [x] **Step 1: Write the failing tests**

In `tests/protocol/test_profiles.py`:

```python
from alphaloop.protocol.profiles import gloss_market_profile


def test_gloss_market_profile_matches_form_labels():
    assert gloss_market_profile("us-equity-daily") == (
        "us-equity-daily — US equities, NYSE, 5 bps, default SPY"
    )
    assert gloss_market_profile("crypto-daily") == (
        "crypto-daily — crypto, 24/7, 10 bps, default BTC-USD"
    )
    assert gloss_market_profile("fx-hourly") == "fx-hourly"
```

In `tests/runtime/test_artifacts_io.py`
`test_report_includes_frozen_hypothesis_and_n_trials`:

```python
    assert (
        "market_profile: us-equity-daily — US equities, NYSE, 5 bps, default SPY"
        in text
    )
    assert "market_profile: us-equity-daily\n" not in text
```

In `test_packaged_market_profile_discloses_frozen_economics`, also:

```python
    from alphaloop.protocol.profiles import MARKET_PROFILE_GLOSS
    assert set(MARKET_PROFILE_GLOSS) == set(ALLOWED_PROFILES)
    for gloss in MARKET_PROFILE_GLOSS.values():
        assert gloss in select
```

In replay e2e, after reading `report.md`:

```python
    assert "NYSE" in report
```

After `#report` wait:

```python
    assert "NYSE" in page.locator("#report").inner_text()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/protocol/test_profiles.py::test_gloss_market_profile_matches_form_labels tests/runtime/test_artifacts_io.py::test_report_includes_frozen_hypothesis_and_n_trials -v
```

Expected: FAIL (`gloss_market_profile` missing; report still has bare profile token).

- [ ] **Step 3: Write minimal implementation**

In `src/alphaloop/protocol/profiles/__init__.py`:

```python
MARKET_PROFILE_GLOSS = {
    US_EQUITY_DAILY.name: "us-equity-daily — US equities, NYSE, 5 bps, default SPY",
    CRYPTO_DAILY.name: "crypto-daily — crypto, 24/7, 10 bps, default BTC-USD",
}


def gloss_market_profile(name: str) -> str:
    key = str(name)
    return MARKET_PROFILE_GLOSS.get(key, key)
```

Export both from `__all__`.

`write_report`:

```python
from alphaloop.protocol.profiles import gloss_market_profile
                f"market_profile: {gloss_market_profile(hyp.market_profile)}",
```

`docs/webui.md`: the sealed report names the frozen market profile
with the same gloss as the form.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/protocol/test_profiles.py tests/runtime/test_artifacts_io.py::test_report_includes_frozen_hypothesis_and_n_trials tests/runtime/test_static_console.py::test_packaged_market_profile_discloses_frozen_economics -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: gloss frozen market_profile on the sealed report"
```
