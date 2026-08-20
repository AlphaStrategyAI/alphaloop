---
title: "Morning verdict stage with locked outcome gloss"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §5.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-console-ui.md
  - docs/requirements/2026-08-20-textbook-pbo.md
---

# Morning verdict stage with locked outcome gloss

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning console visual system and in-place
interpretation of the three research outcomes. Not a new hard gate.
Not inventing `FOUND`. Not unfreezing `webui/`. Not soak.
Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

The product goal names a console that is **visually striking** and
**usable from intuition**. PRD §3.4 / §4.3: a five-minute reader
must identify the conclusion first. Nielsen: recognition rather than
recall; visibility of system status. Tufte: the display must not
imply a claim the evidence does not support.

Validation (textbook CPCV/PBO, qualifying list, `.asb` export, sealed
report) is on the page. The conclusion is still a colored word above a
form. A morning reader has to remember Help to know that `FOUND` is
not alpha. That is not one-glance overnight-lab UX.

## 2. Best-practice basis

1. **Outcome as the visual lead (PRD §4.3):** `#outcome` stays the
   token only (`FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE` / `NONE`) so
   existing tests keep reading one word. A `#verdict` stage around it
   is the five-minute hero.
2. **Gloss from locked Help copy:** `#outcome-gloss` copies the
   matching Help paragraph. Do not invent a second narrative. Source
   ids: `help-found`, `help-no-evidence`, `help-inconclusive`,
   `help-status` (for `NONE`).
3. **No webfont fetch:** system UI + monospace, tabular numbers, CSS
   grid overlay. `FOUND` green is not reused for the other outcomes.
4. **Existing ids stay.** `HOST_CONSTRAINT` and current Help sentences
   unchanged. Additive Help paragraphs only.

## 3. In-scope requirements

### R1. Verdict stage

Packaged detail MUST wrap `#outcome` in `#verdict` **before**
`#job-status`. `#verdict` carries `data-outcome`. `#outcome` text is
exactly the research outcome token.

### R2. Locked gloss

`#outcome-gloss` sits inside `#verdict` after `#outcome`. After
`showJob`, its `textContent` equals the matching Help paragraph:

| outcome | source | locked sentence |
| --- | --- | --- |
| `FOUND` | `#help-found` | `FOUND means every required hard gate is present and passed. It is not a promise of alpha.` |
| `NO_EVIDENCE` | `#help-no-evidence` | `NO_EVIDENCE means a required hard gate failed. It is not a promise that alpha does not exist.` |
| `INCONCLUSIVE` | `#help-inconclusive` | `INCONCLUSIVE means the evidence set is incomplete. Missing diagnostics cannot produce FOUND.` |
| `NONE` | `#help-status` | existing job-status sentence |

### R3. Visual system

`styles.css` MUST include a CSS grid overlay (`repeating-linear-gradient`),
`#verdict` stage styling, `font-variant-numeric: tabular-nums`, and an
`#outcome` size using `clamp(`. No webfont URL. No Node. No gate override.

## 4. Out of scope

- Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers. Unfreezing `webui/`.
- Changing example YAML or `HOST_CONSTRAINT`.

## 5. Acceptance

- Packaged assets: `#verdict`, `#outcome-gloss`, additive Help ids,
  grid overlay, `clamp(`.
- E2E: `#outcome` is still exactly the token; `#outcome-gloss` is
  non-empty; `INCONCLUSIVE` gloss mentions incomplete evidence;
  `FOUND` gloss (when the shortened run seals) contains
  `not a promise of alpha`.
  `python3 -m pytest` unit + e2e as usual.

## 6. Loop exit

Remaining validation: soak / 95% overnight (not CI),
correlation-adjusted \(N_{\mathrm{eff}}\). Later: MCP / cloud workers.
Autonomous iteration stays inside the human-freeze lock.
