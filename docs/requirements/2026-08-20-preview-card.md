---
title: "Protocol preview discloses N, seed, and budgets in designed chrome"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-protocol-preview.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-protocol-preview.md
  - docs/requirements/2026-08-20-preview-chrome.md
---

# Protocol preview discloses N, seed, and budgets in designed chrome

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#protocol-preview` after a successful parse.
Not a new hard gate. Not inventing `FOUND`. Not auto-submit. Not
changing `preview_run` keys. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\). Not restyling Preview/Freeze buttons.

## 1. Why this cycle exists

Protocol-preview R3 already required the compiled protocol to show
grid, `planned_n_trials`, `spec_id`, statement, gates, **budgets**,
and host constraint before Freeze. `preview_run` already returns
`seed`, `time_budget_s`, and `cost_budget_usd`. The page still dumps
unlabeled keys and **omits seed and budgets**. Bailey / López de Prado:
disclose **N** and the frozen seed before treating a later Sharpe as
evidence. Nielsen: recognition. Tufte: visual weight on the trial
count, not a YAML blob. Preview chrome is `--focus`; the card must
not wear FOUND `--accent`.

`#host-constraint` already shows `HOST_CONSTRAINT`. Do not duplicate
that locked sentence inside the card.

## 2. Best-practice basis

1. **Lead with N.** `#preview-n-trials` is the first child and its
   text MUST contain `planned_n_trials:`. Color is `--focus`, not
   `--accent`.
2. **Disclose seed and budgets.** The card MUST contain `seed:`,
   `time_budget_s:`, and `cost_budget_usd:` from the preview payload.
3. **Designed family.** When not `:empty`, `#protocol-preview` uses
   `--ink` background and `--focus` border (same family as Preview
   protocol). MUST NOT use `--accent` or `--warn` on that rule.
4. **Do not freeze by previewing.** Grid remains `#protocol-grid`.
   Click behavior unchanged. MUST NOT print `FOUND`.

## 3. In-scope requirements

### R1. Lead N

`renderPreview` MUST create `#preview-n-trials` as the first child of
`#protocol-preview`. Text is `planned_n_trials: {n}`.

### R2. Seed and budgets

The preview card text MUST include `seed:`, `time_budget_s:`, and
`cost_budget_usd:` matching the API payload. `#protocol-grid` stays.

### R3. Chrome

`styles.css` MUST style `#protocol-preview:not(:empty)` with
`background: var(--ink)` and a `--focus` border. `#preview-n-trials`
MUST set `color: var(--focus)`. Those rules MUST NOT contain
`var(--accent)`.

### R4. E2E

After a successful example preview, Playwright MUST
`wait_for_function` until `#preview-n-trials` color is
`rgb(126, 184, 255)`. Existing `planned_n_trials` substring waits
stay valid. Do not one-shot computed style.

## 4. Out of scope

- Auto-submit. Changing `preview_run`. Editing the grid. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Restyling Load/Preview/Freeze buttons.

## 5. Acceptance

- Static: `#preview-n-trials` in `app.js`; CSS `--ink` / `--focus` on
  the preview card; `seed:` and `time_budget_s:` in `renderPreview`.
- E2E: successful preview shows `planned_n_trials`, `seed:`, and
  focus-blue N. No job created. No `FOUND`.
