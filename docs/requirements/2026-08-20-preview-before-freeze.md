---
title: "Protocol preview sits above Freeze and submit"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-preview-card.md / 2026-08-20-keyboard-freeze.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-preview-card.md
  - docs/requirements/2026-08-20-keyboard-freeze.md
---

# Protocol preview sits above Freeze and submit

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged Before bed DOM order so `#protocol-preview` is
between Preview protocol and Freeze and submit. Not changing preview
payload, chrome tokens, or auto-submit. Not inventing `FOUND`. Not
unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

PRD §4.1: the user **reviews** the compiled protocol, then freezes it.
Bailey / López de Prado: disclose **N** and the frozen seed before
treating a later Sharpe as evidence. Nielsen: match between system
and the real world — review, then commit.

`#protocol-preview` currently sits **below** Freeze and submit. After
Preview protocol, the card appears under the freeze control. A
one-minute user can freeze without looking at planned trial count.
Ctrl/Cmd+Enter still previews then freezes; the visual order must
match that sequence.

YAML / EXAMPLE_SPEC / Help / `HOST_CONSTRAINT` unchanged. Load /
Preview / Freeze chrome tokens unchanged.

## 2. Best-practice basis

1. **Review before commit.** DOM order MUST be
   `#preview-protocol` < `#protocol-preview` < `#submit-job`.
2. **Keep Load with Preview.** Those two produce or reset the card.
   Freeze is the later commit.
3. **Empty card is honest.** `#protocol-preview:empty` still has no
   chrome. Do not invent a filled card.
4. **Do not claim alpha.** No new FOUND copy. Keyboard hint stays
   `Ctrl/Cmd+Enter: Preview, then Freeze.`

## 3. In-scope requirements

### R1. DOM order

Packaged `index.html` MUST place `#protocol-preview` after
`#preview-protocol` and before `#submit-job`. `#preflight-errors`
MUST remain immediately after `#protocol-preview` and before
`#submit-job`. `#host-constraint` MAY stay after Freeze.

`#load-example` and `#preview-protocol` stay together above the
preview card. `#submit-job` and `#keyboard-hint` stay together below
errors. `html.find('id="submit-job"') < html.find('id="keyboard-hint"')`
stays true.

### R2. Geometry

After a successful example preview, Playwright MUST find
`#protocol-preview` bounding-box `y` strictly less than `#submit-job`
bounding-box `y`.

### R3. Docs

`docs/webui.md` MUST say the preview card sits above Freeze and
submit. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Auto-submit. Changing `preview_run`. Restyling buttons. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Markdown-to-HTML.

## 5. Acceptance

- Static: `preview-protocol` < `protocol-preview` < `submit-job` in
  `index.html`.
- E2E: after example preview, preview card is above Freeze; no job
  created by preview alone.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
