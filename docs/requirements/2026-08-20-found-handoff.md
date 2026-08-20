---
title: "Morning verdict stages the FOUND qualifying handoff"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §8.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-qualifying-candidates.md
  - docs/requirements/2026-08-20-console-asb-export.md
  - docs/requirements/2026-08-20-next-run-cue.md
---

# Morning verdict stages the FOUND qualifying handoff

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning `#verdict` cue for the first sealed
qualifying candidate when the research outcome is `FOUND`. Not a new
hard gate. Not auto-export. Not inventing `FOUND`. Not unfreezing
`webui/`. Not soak.

## 1. Why this cycle exists

PRD §4.3 order after the conclusion is **qualifying candidates and
supporting evidence**, then funnel, revisions, and queued hypotheses.
PRD §8.2: export of a `FOUND` candidate requires a **human action**.

The verdict now clusters conclusion, primary evidence, stop reason,
and the `NO_EVIDENCE` next-run cue. On `FOUND`, the survivor and
**Export .asb** still sit below a long `#report`. A five-minute
reader who just read `all required hard gates passed` has to hunt
for the handoff to AlphaStrategy. Nielsen: recognition rather than
recall. The console is the primary product surface (PRD §5.2).

## 2. Best-practice basis

1. **Same cluster as the five-minute tokens.** `FOUND` → who passed
   → human export. `NO_EVIDENCE` already shows the queued next run.
2. **Do not invent `FOUND`.** `#handoff` renders only when
   `research_outcome === "FOUND"` **and** `qualifying_candidates` is
   non-empty. A non-empty qualifying list must not appear on other
   outcomes.
3. **Same export lock as the list.** `button.export-asb` only if
   `trial_id` starts with `c_`. Fallback label `gates.json` is not
   exportable. Click calls existing `exportCandidate` (human POST).
4. **Do not claim alpha.** Prefix `Qualifying: `. Reuse the same
   `trial_id · kind · parameters` line as `#qualifying`. Existing
   Help / no-alpha sentence unchanged.

## 3. In-scope requirements

### R1. Markup

Packaged detail MUST include `#handoff` inside `#verdict` after
`#next-step` and before `#job-status`. Existing `#qualifying` and
`#export-status` stay the full record.

### R2. Render

`fillHandoff(job)`:

- If `job.research_outcome` is not `FOUND`, or
  `job.qualifying_candidates` is missing/empty, `#handoff` has no
  children.
- Otherwise the **first** qualifying row is shown as
  `Qualifying: {trial_id} · {kind} · {parameters}` using the existing
  grid formatter. If `trial_id` starts with `c_`, append
  `button.export-asb` labelled `Export .asb` that calls
  `exportCandidate(trial_id)`.

`#outcome` text remains the research-outcome token.

### R3. Locks

`HOST_CONSTRAINT` unchanged. Help sentences unchanged. Example YAML
unchanged. No `FakeWorker` in morning e2e. No gate override. No
silent export on `FOUND`.

## 4. Out of scope

- Reordering `#report` vs `#qualifying`.
- Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers. Unfreezing `webui/`.

## 5. Acceptance

- Packaged HTML: `#next-step` < `#handoff` < `#job-status`.
- Packaged JS: `fillHandoff` and `Qualifying:`.
- E2E: when the shortened run seals `FOUND`,
  `#verdict #handoff button.export-asb` writes a `.asb` path into
  `#export-status`. Non-`FOUND` jobs have zero
  `#handoff button.export-asb`.
- Unit + e2e pytest as usual.

## 6. Loop exit

Remaining first-release items: soak / 95% overnight (not CI);
correlation-adjusted \(N_{\mathrm{eff}}\) must not shrink DSR `N`.
Later: MCP / cloud workers.
