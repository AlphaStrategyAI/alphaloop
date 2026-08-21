---
title: "Sealed report is not clipped to 22rem"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-21"
supersedes: "none — additive to 2026-08-20-report-chrome.md / 2026-08-21-freeze-reveal.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-report-chrome.md
  - docs/requirements/2026-08-21-freeze-reveal.md
---

# Sealed report is not clipped to 22rem

**Date:** 2026-08-21
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#report` box sizing. Not changing sealed
`report.md` bytes, outcome chrome, or `textContent` rendering. Not
inventing `FOUND`. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

PRD §3.4 / §4.3: a five-minute reader identifies the conclusion,
then qualifying evidence, funnel, revisions, and queued hypotheses
from the morning home page. The sealed document (`report.md` shown
as `#report`) is that paper view.

`#report` still sets `max-height: 22rem` with `overflow: auto`.
Freeze-reveal made `#morning` the wide-layout scrollport
(`position: sticky` + viewport `max-height`). A 22rem inner clip
nests a second scrollbar inside Morning and hides funnel /
revisions / queued sections that the sealed file already contains.
Nielsen: recognition rather than recall — do not make the reader
scroll a nested pane to see the document they came to read.

Outcome border chrome from report-chrome stays. Bytes stay
`textContent`.

## 2. Best-practice basis

1. **One scrollport.** On the two-column grid, `#morning` scrolls.
   `#report` MUST NOT clip itself to `22rem`.
2. **Size to content.** The sealed document grows with
   `report.md`. Keep `overflow: auto` as a safety; do not set a
   `max-height` on `#report`.
3. **Do not claim alpha.** No new FOUND copy. Help /
   `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 3. In-scope requirements

### R1. No 22rem clip

Packaged `#report { ... }` MUST NOT contain `max-height` or
`22rem`. Color stays `var(--fg)`. Outcome selectors
`#report[data-outcome="FOUND"|"NO_EVIDENCE"|"INCONCLUSIVE"]` stay.

### R2. Filled report is taller than the old clip

After a terminal job whose `#report` contains the locked no-alpha
sentence, Playwright MUST observe computed `max-height: none` and
`clientHeight` strictly greater than `22rem` (352px at a 16px root).

### R3. Docs

`docs/webui.md` MUST say the sealed report sizes to its content
instead of a 22rem clip.

## 4. Out of scope

- Changing `write_report` / gloss lines. Restyling Load / Preview /
  Freeze. Soak. \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Changing
  `HOST_CONSTRAINT`. Markdown-to-HTML.

## 5. Acceptance

- Static: `#report {` block has no `max-height` / `22rem`; outcome
  chrome selectors remain.
- E2E replay: filled `#report` computed `max-height` is `none` and
  `clientHeight > 352`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
