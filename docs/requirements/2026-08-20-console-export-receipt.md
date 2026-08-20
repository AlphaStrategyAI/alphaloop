---
title: "Morning console export shows the same FOUND receipt as CLI"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §8.2 / §5.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-console-asb-export.md
  - docs/requirements/2026-08-20-export-handoff.md
  - docs/requirements/2026-08-20-found-handoff.md
---

# Morning console export shows the same FOUND receipt as CLI

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Successful packaged-console `.asb` export receipt.
Not a new hard gate. Not inventing `FOUND`. Not auto-export.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\).
Not changing `assert_exportable`.

## 1. Why this cycle exists

PRD §5.2: the Web console is the primary product surface.
PRD §8.2: export of a `FOUND` candidate is a **human** handoff.
CLI `alphaloop export` now prints a four-line FOUND receipt.
The morning page still puts only the pathname in `#export-status`.

A five-minute reader who clicked **Export .asb** cannot see the
outcome token or the qualifying id without parsing a path.
Nielsen: recognition rather than recall. Tufte: do not hide the
claim in a pathname. CLI and console must say the same thing.

The writer stays `export_found_asb` / `assert_exportable`. Success
is already `FOUND` only. This cycle is the receipt, not a new gate.

## 2. Best-practice basis

1. **Same copy as CLI.** Reuse `format_export_handoff`. Do not
   duplicate the no-alpha sentence in JS.
2. **Preserve newlines.** `#export-status` MUST show four lines,
   not a collapsed string.
3. **Do not invent FOUND.** Only render the receipt after a 200
   from `POST /v1/jobs/{run_id}/export`. Failures stay the error
   string in `#export-status`.
4. **Keep the `.asb` path.** Existing e2e that `#export-status`
   contains `.asb` remains true because line 3 is `Exported: {path}`.

## 3. In-scope requirements

### R1. API receipt field

Successful `JobAPI.export_run` MUST include `export_handoff` equal
to `format_export_handoff(candidate_id=..., exported_path=...)`.
Keep `exported_path` and `exported_candidate_id`. HTTP 200 body
MUST include the same field. 409 / 404 / 400 stay unchanged.

### R2. Console

After a successful export POST, `#export-status` MUST show
`export_handoff` verbatim (four lines, trailing newline allowed):

1. `FOUND`
2. `Qualifying: {candidate_id}`
3. `Exported: {path}`
4. `This export does not claim alpha or future profitability.`

MUST NOT contain `target found`. CSS MUST keep newlines visible
(`white-space: pre-wrap` or equivalent). No webfont `http` in CSS.
Help / `HOST_CONSTRAINT` unchanged.

### R3. Docs

`docs/webui.md` MAY mention that console export shows the FOUND
receipt. Overnight-lab Skill unchanged unless it already describes
the console export status node.

## 4. Out of scope

- Auto-export on `FOUND`. Changing `.asb` contents. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Changing CLI stdout (already shipped).

## 5. Acceptance

- Unit: `export_run` payload `export_handoff` matches
  `format_export_handoff`; HTTP 200 includes it.
- Static: script assigns `export_handoff` to `#export-status`;
  CSS preserves whitespace; no `http` webfont.
- E2E: when the page outcome is `FOUND` and the human clicks
  Export, `#export-status` starts with `FOUND` and includes the
  no-alpha sentence and `.asb`.
- Locks: no `target found`; no Python in `.asb`; no invented
  `FOUND`; `gates.json` still not exportable.
