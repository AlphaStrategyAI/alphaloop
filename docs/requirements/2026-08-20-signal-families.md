---
title: "Signal select is grouped by economic family"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-guided-spec-form.md / frozen-grid-honest-kinds.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-guided-spec-form.md
  - docs/requirements/2026-08-20-frozen-grid-honest-kinds.md
  - docs/requirements/2026-08-20-queued-followup.md
---

# Signal select is grouped by economic family

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#field-signal-mechanism` option labels and
`<optgroup>`s. Not a new hard gate. Not inventing `FOUND`. Not new
DSL kinds. Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not restyling chrome.

## 1. Why this cycle exists

The overnight lab searches a **constrained** directional DSL. Follow-up
queueing already maps trend kinds to a mean-reversion counterpart and
the reverse. The one-minute form still lists `rsi`, `macd`,
`momentum_12_1` as a flat token list. A researcher cannot see the
economic family they are freezing. Nielsen: recognition rather than
recall. PRD §4.1: choose a hypothesis, not remember YAML kinds.

`value` stays the DSL kind. YAML, preview, and Load example stay
unchanged. This cycle is the visible grouping.

## 2. Best-practice basis

1. **Same families as `counterpart_kind`.** Trend =
   `momentum_12_1`, `roc`, `macd`, `atr_breakout`. Mean reversion =
   `rsi`, `bollinger_zscore`, `ohlr_4_pct`. Relative value =
   `pairs_spread`.
2. **Keep the kind in the label.** Visible text MUST contain the
   `value` so YAML authors still recognize it.
3. **Do not expose features.** MUST NOT add `parkinson_hist_vol` or
   `obv_slope`.
4. **Do not claim alpha.** Labels MUST NOT say the kind finds alpha.

## 3. In-scope requirements

### R1. Optgroups

`#field-signal-mechanism` MUST contain three `<optgroup>` elements,
labels exactly:

- `Trend`
- `Mean reversion`
- `Relative value`

Empty placeholder `choose a signal` stays first, not inside a group.

### R2. Values

Option `value`s remain exactly the empty placeholder plus every
`DIRECTIONAL_SIGNAL_KINDS` entry. Each trend kind is inside Trend;
each reversion kind inside Mean reversion; `pairs_spread` inside
Relative value.

### R3. Human gloss

Each non-empty option's text MUST contain an em dash ` — ` after the
kind. Locked glosses:

| value | visible text |
| --- | --- |
| `momentum_12_1` | `momentum_12_1 — 12-1 momentum` |
| `roc` | `roc — rate of change` |
| `macd` | `macd — MACD` |
| `atr_breakout` | `atr_breakout — ATR breakout` |
| `rsi` | `rsi — RSI` |
| `bollinger_zscore` | `bollinger_zscore — Bollinger z-score` |
| `ohlr_4_pct` | `ohlr_4_pct — opening range` |
| `pairs_spread` | `pairs_spread — pairs spread` |

### R4. Docs

`docs/webui.md` MAY note the signal list is grouped by family. Help /
EXAMPLE_SPEC / `HOST_CONSTRAINT` unchanged.

## 4. Out of scope

- Changing YAML keys. Auto-submit. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling chrome.
  New DSL kinds.

## 5. Acceptance

- Static: three optgroups; values match `DIRECTIONAL_SIGNAL_KINDS`;
  gloss strings present; no Parkinson/OBV.
- E2E: Load example still sets `momentum_12_1`. Queued follow-up still
  loads `rsi` by value.
