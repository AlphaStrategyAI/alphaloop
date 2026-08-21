---
title: "Sealed report frozen hypothesis uses the form signal gloss"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-morning-report.md / 2026-08-20-preview-followup-gloss.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-report.md
  - docs/requirements/2026-08-20-preview-followup-gloss.md
  - docs/requirements/2026-08-20-signal-families.md
---

# Sealed report frozen hypothesis uses the form signal gloss

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `report.md` `## Frozen hypothesis` `signal_mechanism:`
line (and `#report`, which is that file). Not a new DSL kind. Not
inventing `FOUND`. Not changing YAML / EXAMPLE_SPEC /
`morning_view["hypothesis"].signal_mechanism`. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not restyling chrome.
Not glossing `market_profile` this cycle.

## 1. Why this cycle exists

PRD §3.4 / §4.3: a five-minute reader identifies the frozen
hypothesis next to the conclusion. Preview, queued follow-ups, and
qualifying rows already print `momentum_12_1 — 12-1 momentum`. The
sealed `report.md` still writes `signal_mechanism: momentum_12_1`.
`#report` is that file. Nielsen: recognition rather than recall.
CONSORT: the written protocol should name the pre-specified
mechanism with the same vocabulary the form taught.

YAML, Load example, and the Job API hypothesis token stay raw.

## 2. Best-practice basis

1. **Same locked signal gloss as the form** (`SIGNAL_GLOSS` /
   `gloss_signal`). Unknown kinds stay raw.
2. **Keep the token first.** The line still starts
   `signal_mechanism:`.
3. **Do not rewrite YAML.** EXAMPLE_SPEC and `#spec-yaml` stay
   tokens.
4. **Do not claim alpha.** A glossed frozen line is not `FOUND`.
5. **Do not shrink N.** `n_trials` in the report stays unique-ledger N.

## 3. In-scope requirements

### R1. Report line

When `write_report` prints the frozen hypothesis,
`signal_mechanism:` MUST be `gloss_signal(hyp.signal_mechanism)`.
Other frozen fields (`statement`, `economic_logic`, `market_scope`,
`market_profile`, `benchmark`) stay as today.

### R2. Console

`#report` still renders `report_markdown` with `textContent`. No JS
gloss table. Replay still rewrites `report.md` from sealed artifacts
and therefore picks up the glossed line.

### R3. Docs

`docs/webui.md` MUST say the sealed report names the frozen signal
with the same gloss as the form. Help / `HOST_CONSTRAINT` /
EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Gloss `market_profile` / revision lines. Soak. \(N_{\mathrm{eff}}\).
  Unfreezing `webui/`. Changing `morning_view` hypothesis tokens.
  New kinds.

## 5. Acceptance

- Unit: `write_report` contains
  `signal_mechanism: momentum_12_1 — 12-1 momentum` and MUST NOT
  contain a bare `signal_mechanism: momentum_12_1` line.
- EXAMPLE_SPEC / Load example still contain
  `signal_mechanism: momentum_12_1`.
- E2E replay: sealed `report.md` and `#report` contain
  `momentum_12_1 — 12-1 momentum`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
