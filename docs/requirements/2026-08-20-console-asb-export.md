---
title: "Human-triggered .asb export from the morning console"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §8.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-qualifying-candidates.md
---

# Human-triggered .asb export from the morning console

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Reuse the existing FOUND-only `.asb` writer from the
packaged morning console via the local Job API. Not a new hard gate.
Not inventing `FOUND`. Not unfreezing `webui/`. Not auto-export.

## 1. Why this cycle exists

PRD §8.2: only a `FOUND` candidate can be exported, and export
requires a **human action**. PRD §5.2: the Web console is the primary
product interface. Today `alphaloop export` is CLI-only. A five-minute
reader who sees a qualifying `c_*` id still has to leave the page and
remember flags. That is not one-minute / five-minute local-lab UX.

`docs/requirements/2026-08-20-qualifying-candidates.md` named who
passed. This cycle lets a human hand that survivor to AlphaStrategy
from the same page, with the same `assert_exportable` lock.

## 2. Best-practice basis

1. **Human in the loop:** no silent bundle write on `FOUND`.
2. **Same gate as CLI:** `research_outcome is FOUND` and `candidate_id`
   is a sealed ledger id. The fallback label `gates.json` is not
   exportable.
3. **Local-first:** write `{run_dir}/exports/{candidate_id}.asb` and
   show the path. No registry. No Python inside `.asb`.

## 3. In-scope requirements

### R1. Shared writer

Extract the CLI payload/write path into a helper used by CLI and
`JobAPI.export_run(run_id, candidate_id)`. Output path for the API is
`{data_dir}/{run_id}/exports/{candidate_id}.asb`. Reject `candidate_id`
values containing `/`, `\\`, or `..`. Raise `ExportNotAllowed` when
`assert_exportable` fails. Return JSON including `exported_path` and
`exported_candidate_id`.

### R2. HTTP

`POST /v1/jobs/{run_id}/export` with JSON `{"candidate_id": "..."}`.
200 on success. 409 on `ExportNotAllowed`. 404 if the job is missing.
400 on bad body. Do not add a gates override route.

### R3. Console

When `research_outcome` is `FOUND`, each `#qualifying` row whose
`trial_id` starts with `c_` MUST include a button `export-asb` that
POSTs that id. Other outcomes MUST NOT show the button. After a
successful export, `#export-status` shows the returned path (must
contain `.asb`). Help / `HOST_CONSTRAINT` unchanged. No invented
`FOUND`.

## 4. Out of scope

- Textbook `S=16`. Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Auto-export on seal. Unfreezing `webui/`. Changing bundle schema.

## 5. Acceptance

- Unit: FOUND + ledger id writes a zip `.asb`; NONE/NO_EVIDENCE raises
  `ExportNotAllowed`; CLI still writes the same archive.
- HTTP: POST export 409 when not FOUND; 200 writes `exports/`.
- Packaged assets: `export-asb`, `/export`, `#export-status`.
- E2E: no export button when outcome is not FOUND; when FOUND, click
  writes `.asb` and `#export-status` contains `.asb`.
  `python3 -m pytest` unit + e2e as usual.

## 6. Loop exit

Remaining validation: textbook `S=16` CPCV, soak / 95% overnight
(not CI), correlation-adjusted \(N_{\mathrm{eff}}\). Later: MCP /
cloud workers.
