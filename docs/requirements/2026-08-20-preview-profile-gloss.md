---
title: "Protocol preview names the frozen market-profile gloss"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-preview-followup-gloss.md / 2026-08-20-report-profile-gloss.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-preview-followup-gloss.md
  - docs/requirements/2026-08-20-cli-preview-seed.md
  - docs/requirements/2026-08-20-report-profile-gloss.md
  - docs/requirements/2026-08-20-profile-glosses.md
---

# Protocol preview names the frozen market-profile gloss

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Additive `market_profile` / `market_profile_label` on
`preview_run`; human CLI `format_protocol_preview`; packaged
`renderPreview`. Not a new profile. Not inventing `FOUND`. Not
requiring preview before CLI submit. Not unfreezing `webui/`. Not
soak. Not \(N_{\mathrm{eff}}\). Not restyling chrome. Not changing
YAML `market_profile` values.

## 1. Why this cycle exists

PRD §4.1: review the compiled protocol before Freeze. The form and
the sealed report already disclose
`us-equity-daily — US equities, NYSE, 5 bps, default SPY`. Preview
(CLI + `#protocol-preview`) still omits the profile entirely, so a
researcher can freeze without seeing calendar or costs on the
compiled card. Bailey / López de Prado: disclose costs and the
sampling calendar before treating a later Sharpe as evidence.
Nielsen: the freeze card must name the same frozen economics the
form already taught.

YAML, Load example, and `morning_view` hypothesis tokens stay raw.

## 2. Best-practice basis

1. **Same locked gloss as the form** (`MARKET_PROFILE_GLOSS` /
   `gloss_market_profile`).
2. **Keep the token first.** The line still starts `market_profile:`.
3. **Do not invent keys on YAML.** Additive preview keys only.
4. **Unknown names stay raw.** `gloss_market_profile` already returns
   the raw name when missing from the map.
5. **Do not claim alpha.** Preview still contains the locked no-alpha
   sentence. No `run_id`. No `FOUND`.
6. **No JS gloss table.** Packaged JS MUST render
   `market_profile_label` when present, else the raw
   `market_profile` token.

## 3. In-scope requirements

### R1. Preview payload

`preview_run` MUST add:

- `market_profile`: `spec.hypothesis.market_profile` (token)
- `market_profile_label`: `gloss_market_profile(market_profile)`

Existing keys unchanged. No `run_id`.

### R2. Human preview

`format_protocol_preview` MUST print
`market_profile: {label}` after `signal_mechanism:` and before
`hard_gates:`. Label is `market_profile_label` when present, else
`gloss_market_profile(market_profile)`.

Packaged `renderPreview` MUST include the same line in
`#preview-summary` with the same fallback.

### R3. Docs

`docs/webui.md` / `docs/cli.md` MUST note preview names the market
profile gloss. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Require preview before CLI submit. Gloss revision lines. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Third profile.

## 5. Acceptance

- Unit: `preview_run` keeps `market_profile == "us-equity-daily"` and
  `market_profile_label` is the locked form gloss.
- Unit: `format_protocol_preview` contains `NYSE` / `5 bps`.
- Packaged JS reads `market_profile_label`. No `MARKET_PROFILE_GLOSS`
  in `app.js`.
- E2E preview card contains `NYSE`.
- EXAMPLE_SPEC still `market_profile: us-equity-daily`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
