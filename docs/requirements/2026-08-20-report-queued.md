---
title: "Sealed report lists queued hypotheses"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-queued-followup.md / 2026-08-20-revision-kind-gloss.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-queued-followup.md
  - docs/requirements/2026-08-20-preview-followup-gloss.md
  - docs/requirements/2026-08-20-morning-report.md
  - docs/requirements/2026-08-20-revision-kind-gloss.md
---

# Sealed report lists queued hypotheses

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `report.md` `## Queued hypotheses` after methodological
revisions, via `format_queued_line` / `build_queued_hypotheses`. Not
auto-executing the follow-up. Not inventing `FOUND`. Not rewriting
`recommendations.json`. Not shrinking DSR `N`. Not unfreezing
`webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not restyling chrome.

## 1. Why this cycle exists

PRD §4.3: after methodological revisions, present **evidence-backed
suggestions for a future hypothesis**. Packaged `#queued` already
prints the statement and Load into editor. CLI status already prints
`Next run:`. The sealed five-minute document (`report.md` / `#report`)
stops after methodological revisions, so a reader of the written
artifact cannot see what the overnight lab queued.

Nielsen: recognition rather than recall. CONSORT: name the next
pre-registered experiment in the same report as the analysed method.
The statement already interpolates `gloss_signal` / `gloss_hard_gate`
and `This is not a claim of alpha.`

YAML / EXAMPLE_SPEC / Help / `HOST_CONSTRAINT` unchanged.

## 2. Best-practice basis

1. **Same heading as the morning list.** `## Queued hypotheses`
   matches packaged `#queued`.
2. **Print the sealed statement.** Do not invent a second narrative.
   `format_queued_line` is the `statement` field, trimmed.
3. **Empty is honest.** Missing file, empty list, or blank statements
   → `none`. MUST NOT print `FOUND`.
4. **Do not rewrite `recommendations.json`.** Additive report view
   only.
5. **Do not execute the follow-up.** `signal_mechanism` on the queued
   object stays the DSL kind. Human Load + Freeze still required.

## 3. In-scope requirements

### R1. Read queued rows

`build_queued_hypotheses(layout)` MUST return each dict in
`recommendations.json` `queued_hypotheses`, or `[]` when the file is
missing, unreadable, or not a mapping.

### R2. Line format

`format_queued_line(row)` MUST return the trimmed `statement` string,
or `""` when missing.

`write_report` MUST include `## Queued hypotheses` after
`## Methodological revisions`, with non-empty statements or `none`.
Locked no-alpha sentence unchanged.

### R3. Docs

`docs/webui.md` MUST say the sealed report lists queued hypotheses
(or `none`). Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Auto-submit after Load. Changing follow-up copy. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. New revision kinds.
  Changing `trial-ledger.jsonl`.

## 5. Acceptance

- Unit: missing recommendations → report contains
  `## Queued hypotheses` and `none`.
- Unit: one queued statement appears verbatim after the heading;
  method-revision rows stay in `## Methodological revisions`.
- E2E replay / sealed `#report` contains `## Queued hypotheses`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
