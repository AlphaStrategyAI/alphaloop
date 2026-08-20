---
title: "Market profile select discloses frozen calendar, costs, and default benchmark"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-guided-spec-form.md / 2026-08-20-signal-families.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-guided-spec-form.md
  - docs/requirements/2026-08-20-signal-families.md
  - docs/requirements/2026-08-20-hard-gate-glosses.md
---

# Market profile select discloses frozen calendar, costs, and default benchmark

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#field-market-profile` option labels. Not a new
profile. Not inventing `FOUND`. Not changing option `value`s or YAML.
Not auto-filling `#field-benchmark`. Not unfreezing `webui/`. Not soak.
Not \(N_{\mathrm{eff}}\). Not restyling chrome.

## 1. Why this cycle exists

PRD §4.1: choose a **market profile** in one minute, then freeze.
PRD §5.5: `us-equity-daily` and `crypto-daily` are independent. They
separately freeze calendar, costs, and default benchmark. Candidates
from the two profiles are not ranked together.

Signal kinds and hard gates now keep the token plus a human gloss.
`#field-market-profile` still shows only the YAML token. A researcher
cannot see NYSE vs 24/7 or 5 bps vs 10 bps before Freeze. Bailey /
López de Prado: disclose costs and the sampling calendar before
treating a later Sharpe as evidence. Nielsen: recognition rather than
recall.

`value` stays `ALLOWED_PROFILES`. YAML, preview, Load example, and
the benchmark text field stay unchanged. This cycle is the visible
frozen economics.

## 2. Best-practice basis

1. **Keep the token in the label.** Visible text MUST contain the
   option `value`.
2. **Same em-dash pattern as signals and gates.**
3. **Disclose the independent-profile facts** already on
   `MarketProfile`: calendar, `cost_bps`, `default_benchmark`.
4. **Do not claim alpha.** Labels MUST NOT say a profile finds alpha.
5. **Do not add a third profile.**

## 3. In-scope requirements

### R1. Values

`#field-market-profile` option `value`s remain exactly the empty
placeholder plus every `ALLOWED_PROFILES` entry
(`us-equity-daily`, `crypto-daily`). Form JS still reads `.value`.

### R2. Human gloss

Empty placeholder stays `choose a profile`. Non-empty options MUST
be:

| value | visible text |
| --- | --- |
| `us-equity-daily` | `us-equity-daily — US equities, NYSE, 5 bps, default SPY` |
| `crypto-daily` | `crypto-daily — crypto, 24/7, 10 bps, default BTC-USD` |

Those numbers match `US_EQUITY_DAILY` / `CRYPTO_DAILY` (`cost_bps`
5.0 / 10.0, calendars `nyse` / `247`, defaults `SPY` / `BTC-USD`).

### R3. Docs

`docs/webui.md` MUST name that the market profile list discloses
calendar, costs, and default benchmark. Help / `HOST_CONSTRAINT` /
EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Auto-filling the benchmark field. Mixing the two profiles into one
  ranking. Soak. \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Evidence-line
  glosses.

## 5. Acceptance

- Static: both `ALLOWED_PROFILES` values; locked gloss strings;
  placeholder first; no extra profile values.
- Existing guided-form value loop and Load example still assert by
  `value`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
