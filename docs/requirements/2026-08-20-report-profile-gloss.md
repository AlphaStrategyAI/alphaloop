---
title: "Sealed report frozen profile uses the form market-profile gloss"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-report-signal-gloss.md / 2026-08-20-profile-glosses.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-report-signal-gloss.md
  - docs/requirements/2026-08-20-profile-glosses.md
---

# Sealed report frozen profile uses the form market-profile gloss

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Canonical `MARKET_PROFILE_GLOSS` / `gloss_market_profile`,
and the `report.md` `## Frozen hypothesis` `market_profile:` line
(and `#report`, which is that file). Not a new profile. Not inventing
`FOUND`. Not changing YAML / EXAMPLE_SPEC /
`morning_view["hypothesis"].market_profile`. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\). Not restyling chrome. Not adding
`market_profile` to the protocol-preview summary this cycle.

## 1. Why this cycle exists

PRD §4.1 / §5.5: freeze an independent market profile (calendar,
costs, default benchmark). The one-minute form already shows
`us-equity-daily — US equities, NYSE, 5 bps, default SPY`. The sealed
report still writes `market_profile: us-equity-daily`. Bailey / López
de Prado: disclose costs and the sampling calendar before treating a
Sharpe as evidence. Nielsen: the five-minute artifact must name the
same frozen economics the form taught.

Those labels lived only in HTML. This cycle lifts them onto
`protocol.profiles` so report formatting cannot drift from the form.

YAML, Load example, and the Job API hypothesis token stay raw.

## 2. Best-practice basis

1. **Same locked gloss as the form.** Labels MUST match
   `2026-08-20-profile-glosses.md` R2 exactly, and MUST keep matching
   `US_EQUITY_DAILY` / `CRYPTO_DAILY` (`cost_bps`, calendar,
   `default_benchmark`).
2. **Keep the token first.** Gloss text still starts with the
   profile name.
3. **Unknown names stay raw.** A name not in `ALLOWED_PROFILES` MUST
   be printed unchanged (no invented em dash).
4. **Do not rewrite YAML.** EXAMPLE_SPEC stays
   `market_profile: us-equity-daily`.
5. **Do not claim alpha.** A glossed profile line is not `FOUND`.
6. **No JS gloss table.** `#report` still renders sealed file bytes.

## 3. In-scope requirements

### R1. Shared map

`alphaloop.protocol.profiles` MUST export `MARKET_PROFILE_GLOSS`
mapping every `ALLOWED_PROFILES` name to the locked label, and
`gloss_market_profile(name)` returning that label or the raw name.

### R2. Report line

When `write_report` prints the frozen hypothesis,
`market_profile:` MUST be `gloss_market_profile(hyp.market_profile)`.
Other frozen fields stay as today (signal already glossed).

### R3. Console and form

`#report` still renders `report_markdown`. Packaged
`#field-market-profile` option text MUST contain every
`MARKET_PROFILE_GLOSS` value. Option `value`s stay tokens.

### R4. Docs

`docs/webui.md` MUST say the sealed report names the frozen market
profile with the same gloss as the form. Help / `HOST_CONSTRAINT` /
EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Protocol-preview `market_profile` line. Gloss revision lines. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Third profile.
  Auto-fill benchmark.

## 5. Acceptance

- Unit: `gloss_market_profile("us-equity-daily")` is the locked
  label; unknown name unchanged.
- Unit: `write_report` contains
  `market_profile: us-equity-daily — US equities, NYSE, 5 bps, default SPY`
  and MUST NOT contain a bare `market_profile: us-equity-daily` line.
- Packaged select contains every `MARKET_PROFILE_GLOSS` value.
- EXAMPLE_SPEC / Load example still contain
  `market_profile: us-equity-daily`.
- E2E replay: sealed `report.md` and `#report` contain `NYSE`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
