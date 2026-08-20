---
title: "CLI export without --run-id uses the latest job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-export-handoff.md / status-latest.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-export-handoff.md
  - docs/requirements/2026-08-20-status-latest.md
---

# CLI export without --run-id uses the latest job

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Optional `--run-id` on `alphaloop export`. Not a new hard
gate. Not inventing `FOUND`. Not auto-export. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\). Not changing `assert_exportable`
or the four-line receipt.

## 1. Why this cycle exists

PRD §8.2 / §10.2: export is a human CLI handoff. `alphaloop status`
already reviews the latest job when `RUN_ID` is omitted. `alphaloop
export` still requires `--run-id`. A researcher who just read
`FOUND` on `status` must recall a `j_*` id to write the `.asb`.

Nielsen: recognition rather than recall. Same latest-job rule as
status and the Web home (`JobStore.list_jobs` newest-first).

The writer stays `export_found_asb`. Latest job that is not `FOUND`
still exits 2. This cycle does not skip backward to an older
`FOUND`.

## 2. Best-practice basis

1. **Same latest-job rule as status.** `jobs[0]` from
   `ORDER BY created_at DESC, run_id DESC`.
2. **Do not invent FOUND.** Empty store: stderr + exit 2, no
   receipt. Non-FOUND latest: existing `ExportNotAllowed` path.
3. **Keep the explicit id.** `--run-id RUN_ID` unchanged.
4. **Receipt first line stays `FOUND`.** Do not prepend `run_id:`.
   `--json` payload keys unchanged.

## 3. In-scope requirements

### R1. Optional `--run-id`

`alphaloop export CANDIDATE_ID --output PATH [--run-id RUN_ID]`
`--run-id` is optional.

When present, behavior is unchanged from
`docs/requirements/2026-08-20-export-handoff.md`.

### R2. Latest job

When `--run-id` is omitted and `list_jobs()` is non-empty, export
uses `jobs[0].run_id`. Success still prints `format_export_handoff`.
`--json` still `{candidate_id, exported_path, research_outcome}`.

### R3. Empty store

When `--run-id` is omitted and there are no jobs, stderr is exactly:

`error: no overnight job yet`

plus a newline. Exit 2. MUST NOT print `FOUND` on stdout. MUST NOT
contain `target found`.

### R4. Docs

`docs/cli.md` export section: `--run-id` optional, omit for latest
job. Skill MAY say the same.

## 4. Out of scope

- Auto-export on `FOUND`. Searching older jobs for a `FOUND`. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Changing receipt copy.

## 5. Acceptance

- Unit: omit `--run-id` on a single FOUND job writes `.asb` and
  prints `FOUND`; two jobs export the newest; empty store exit 2
  with locked stderr; explicit `--run-id` still works.
- E2E: existing FOUND export with `--run-id` still passes.
- Locks: no invented `FOUND`; `assert_exportable` unchanged.
