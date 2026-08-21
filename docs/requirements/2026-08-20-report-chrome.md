---
title: "Sealed report uses the same outcome chrome as the verdict"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-morning-report.md / 2026-08-20-lifecycle-chrome.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-report.md
  - docs/requirements/2026-08-20-lifecycle-chrome.md
---

# Sealed report uses the same outcome chrome as the verdict

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#report` `data-outcome` plus CSS outcome-token
border/glow. Not markdown-to-HTML. Not inventing `FOUND`. Not
unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not changing
`report.md` bytes. Not restyling Help / `HOST_CONSTRAINT`.

## 1. Why this cycle exists

PRD §3.4 / §10.1: the five-minute read is the morning home page,
including artifact navigation. `#verdict` already uses `--accent` /
`--warn` / `--inconclusive` so the conclusion is visible at a glance.
`#report` still sits in the muted metadata group (`--muted`) with a
generic `--line` border, so the sealed document looks like a log dump
under the designed verdict.

Nielsen: visibility of system status, consistency and standards.
Tufte: visual weight should match the cluster. The written artifact
must share the same outcome language as the lead conclusion. Do not
render markdown as HTML (CONSORT: the page displays file bytes).

YAML / EXAMPLE_SPEC / Help / `HOST_CONSTRAINT` unchanged.

## 2. Best-practice basis

1. **Same outcome token as `#verdict`.** `fillReport` MUST set
   `#report` `data-outcome` to `job.research_outcome`. Do not infer
   `FOUND` from report text.
2. **Readable document, not muted chrome.** Base `#report` color MUST
   be `var(--fg)`. It MUST NOT remain only in the muted metadata
   grouping with `#job-status`.
3. **Outcome border language.** `#report[data-outcome="FOUND"]` uses
   `--accent` family (green rgba, not FOUND copy). `NO_EVIDENCE` uses
   `--warn`. `INCONCLUSIVE` uses `--inconclusive`. `NONE` keeps the
   generic `--line` border (no outcome glow).
4. **Do not claim alpha.** No new copy. No `target found`.

## 3. In-scope requirements

### R1. Payload wiring

`fillReport(job)` MUST set `node.dataset.outcome` to
`job.research_outcome` (empty string if missing) and still assign
`textContent` from `report_markdown`.

### R2. CSS

Packaged `styles.css` MUST include `#report[data-outcome="FOUND"]`,
`#report[data-outcome="NO_EVIDENCE"]`, and
`#report[data-outcome="INCONCLUSIVE"]` rules that set `border-color`
(and MAY set `box-shadow`) using the same token families as
`#verdict[data-outcome=...]`. Base `#report` `color` MUST be
`var(--fg)`.

### R3. Docs

`docs/webui.md` MUST say the sealed report uses the same outcome
chrome as the verdict. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC stay
locked.

## 4. Out of scope

- Markdown-to-HTML. Changing report schema. Soak. \(N_{\mathrm{eff}}\).
  Unfreezing `webui/`. New buttons.

## 5. Acceptance

- Static: `fillReport` writes `dataset.outcome`; CSS has the three
  outcome selectors; FOUND rule uses accent-family color and does not
  contain `target found`.
- E2E: after opening a terminal job, `#report` `data-outcome` equals
  the list outcome.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
