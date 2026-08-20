---
title: "Sealed morning report on the packaged console"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §10.1"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
  - docs/requirements/2026-08-20-console-asb-export.md
---

# Sealed morning report on the packaged console

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Show the sealed `report.md` on the packaged morning page
and keep Before bed and Morning visible together on a wide viewport.
Not a new hard gate. Not inventing `FOUND`. Not unfreezing `webui/`.
Not textbook `S=16`.

## 1. Why this cycle exists

PRD §3.4: a first-release reader must identify the conclusion,
primary evidence, and stop reason from the morning home page in five
minutes. PRD §10.1: the Web console is the primary surface because it
supports review **and artifact navigation**.

`report.md` is already the sealed written artifact: locked no-alpha
sentence, outcome, stop reason, frozen hypothesis, gates, funnel,
qualifying candidates. Export can now hand a `FOUND` survivor to
AlphaStrategy from the same page. The five-minute reader still has to
leave the console and open a file to read the report the overnight
lab actually wrote.

Nielsen: recognition rather than recall, visibility of system status.
A local lab that asks the user to `cat report.md` is not one-minute /
five-minute UX, and it is not an interface that can be used from
intuition.

## 2. Best-practice basis

1. **CONSORT / pre-registration:** the written report is a view of
   sealed artifacts, not a second outcome channel. The page MUST
   display the file bytes (as text), not a regenerated narrative that
   could drift from disk.
2. **Do not invent `FOUND`:** `research_outcome` stays the Job API
   field. Missing `report.md` is an empty `#report`, not a guessed
   conclusion.
3. **Simultaneous submit and review (Nielsen visibility):** on a wide
   viewport, Before bed and Morning MUST sit side by side so a running
   job remains visible while the next spec is edited. Help stays full
   width. Help / `HOST_CONSTRAINT` / example YAML unchanged.

## 3. In-scope requirements

### R1. Payload

`morning_view` MUST include `report_markdown`: the UTF-8 text of
`report.md` when that file exists, otherwise `""`. Do not parse the
report to set `research_outcome`. Do not invent missing sections.

### R2. Console

Packaged detail MUST include `#report` **after** `#stop-reason` and
**before** `#qualifying`. Render with `textContent` (not HTML). After
a terminal worker write, `#report` MUST contain the locked sentence
`This report does not claim alpha or future profitability.`

On viewports ≥ 960px, `#console` is a two-column grid: `#before-bed`
then `#morning`; `#help` spans both columns.

### R3. Locks

`HOST_CONSTRAINT` unchanged. Help sentences unchanged. Example YAML
unchanged. No `FakeWorker` in morning e2e. No gate override. No
Python in `.asb`.

## 4. Out of scope

- Textbook `S=16`. Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Markdown-to-HTML rendering. Unfreezing `webui/`. Changing report
  schema beyond displaying the existing file.

## 5. Acceptance

- Unit: missing `report.md` → `report_markdown == ""`; after
  `write_report`, payload equals file text and still does not claim
  alpha.
- Packaged assets: `id="report"`, `report_markdown`,
  `grid-template-columns`.
- E2E: job detail includes `#report`; after a terminal run that wrote
  `report.md`, `#report` contains the locked no-alpha sentence.
  `python3 -m pytest` unit + e2e as usual.

## 6. Loop exit

Remaining product after this cycle shipped: preview a queued
follow-up without auto-submitting
(`docs/requirements/2026-08-20-queued-preview.md`). Remaining
validation: textbook `S=16` CPCV, soak / 95% overnight (not CI),
correlation-adjusted \(N_{\mathrm{eff}}\). Later: MCP / cloud workers.
