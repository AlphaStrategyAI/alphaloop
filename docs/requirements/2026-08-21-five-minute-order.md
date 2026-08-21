---
title: "Five-minute lists sit above the sealed report"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-21"
supersedes: "2026-08-20-morning-report.md R2 order `#report` before `#qualifying`; 2026-08-20-lifecycle-actions.md `#report` < `#qualifying`"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-report.md
  - docs/requirements/2026-08-20-found-handoff.md
  - docs/requirements/2026-08-21-report-uncramp.md
---

# Five-minute lists sit above the sealed report

**Date:** 2026-08-21
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#detail` DOM order so PRD §4.3 lists sit above
the sealed `#report`. Not changing list payloads, report bytes, or
outcome chrome. Not inventing `FOUND`. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

PRD §4.3: after the conclusion the home page presents (1) qualifying
candidates and evidence, (2) the elimination funnel, (3)
methodological revisions, (4) queued hypotheses. found-handoff
deferred reordering `#report` vs `#qualifying` while `#report` was
still a 22rem clip.

Report-uncramp now sizes `#report` to the full sealed file. The
structured lists remain **below** that document. A five-minute
reader must scroll past the paper archive to reach the scannable
cluster the PRD names. Nielsen: recognition rather than recall —
lists first, sealed paper second.

Cancel / Resume / Replay stay above the report (lifecycle-actions /
console-replay). Verdict handoff stays in `#verdict`. Help /
`HOST_CONSTRAINT` / EXAMPLE_SPEC unchanged.

## 2. Best-practice basis

1. **Match the PRD order.** DOM MUST be qualifying → evidence →
   funnel → revisions → queued → `#report`.
2. **Sealed paper is the archive.** `#report` still renders
   `report.md` with `textContent`. Do not drop it. Do not parse it
   for outcome.
3. **Do not claim alpha.** No new FOUND copy.

## 3. In-scope requirements

### R1. DOM order

Packaged `#detail` MUST place the five-minute lists **after**
`#search-progress` and **before** `#report`:

`#search-progress` < `#qualifying` < `#evidence` < `#funnel` <
`#revisions` < `#queued` < `#report`

`#replay-job` < `#qualifying` stays true. `#cancel-job` <
`#resume-job` < `#replay-job` stays true. `#stop-reason` <
`#report` stays true.

This supersedes morning-report R2 “`#report` before `#qualifying`”
and lifecycle-actions “`#report` < `#qualifying`”.

### R2. Geometry

After a terminal job whose `#report` contains the locked no-alpha
sentence, Playwright MUST find `#qualifying` bounding-box `y`
strictly less than `#report` bounding-box `y`.

### R3. Docs

`docs/webui.md` MUST say the five-minute lists sit above the sealed
report.

## 4. Out of scope

- Changing `write_report` / list fill helpers. Restyling buttons.
  Soak. \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Markdown-to-HTML.
  Moving Cancel / Resume / Replay below the lists.

## 5. Acceptance

- Static: `#queued` < `#report` and `#report` is after `#qualifying`
  (not before). Existing replay/cancel order assertions still pass
  except the superseded `report < qualifying` check.
- E2E replay: `#qualifying` is above `#report` on screen.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
