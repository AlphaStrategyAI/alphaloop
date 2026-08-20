---
title: "Morning dataset picker accepts a wide close-only CSV"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-dataset-upload.md / 2026-08-20-dataset-csv.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-dataset-upload.md
  - docs/requirements/2026-08-20-dataset-csv.md
---

# Morning dataset picker accepts a wide close-only CSV

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `POST /v1/datasets` and packaged `#field-dataset-file`.
Not a new hard gate. Not inventing `FOUND`. Not auto-submit. Not
unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not changing
CLI dataset stdout. Not heritage `alphaloop fetch` network I/O.

## 1. Why this cycle exists

CLI `alphaloop dataset PATH` now converts a wide close-only CSV into
the same parquet cache as a native parquet file. The morning picker
still `accept`s only `.parquet` and `POST /v1/datasets` still requires
parquet magic `PAR1`. A one-minute submitter on the packaged page with
a spreadsheet export cannot attach a snapshot. Nielsen: the console
and CLI must share the same ingest rule.

## 2. Best-practice basis

1. **Same conversion as CLI.** Bytes that are not parquet magic are
   passed through `parquet_bytes_from_csv`, then `put_dataset_bytes`.
   Identity is the parquet hash.
2. **Fail closed on junk.** Unreadable bytes MUST NOT create a job.
   Error text MUST contain `parquet or csv` (or `csv` / `empty` from
   the existing converter).
3. **Do not freeze by picking a file.** Picker still MUST NOT call
   `submitJob`. Freeze stays disabled until Preview succeeds.
4. **Do not claim alpha.** Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC
   unchanged.

## 3. In-scope requirements

### R1. `cache_dataset_bytes`

`cache_dataset_bytes(data_dir, blob) -> DatasetRef`

- If `blob` starts with `PAR1`, call `put_dataset_bytes` unchanged.
- Otherwise convert with `parquet_bytes_from_csv` and
  `put_dataset_bytes`. Converter failures become `DatasetRejected`
  whose message contains `parquet or csv`.
- `JobAPI.put_dataset` MUST use this helper (HTTP POST uses JobAPI).

`put_dataset_bytes` stays parquet-magic only (unit tests for raw
bytes unchanged).

### R2. Console picker

`#field-dataset-file` `accept` MUST include `.csv`. The visible label
MUST mention CSV (not parquet-only). Click path stays
`cacheDatasetFile` → `POST /v1/datasets` → fill id/sha256 → rewrite
YAML. MUST NOT call `submitJob`.

### R3. Docs

`docs/webui.md` MAY note the picker accepts parquet or wide
close-only CSV. Skill / Help / EXAMPLE_SPEC / CLI receipt unchanged.

## 4. Out of scope

- Auto-submit. Changing CLI stdout. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling chrome.
  Fetching Yahoo in the picker.

## 5. Acceptance

- HTTP: POST wide CSV → 201, `dataset_id` / `sha256`, parquet readable
  with those columns, `list_jobs` empty. POST `not parquet` → 400, no
  job.
- Static: `#field-dataset-file` accept includes `.csv`; label mentions
  CSV; `cacheDatasetFile` still has no `submitJob`.
- E2E: `set_input_files` a wide CSV; id/sha256 fill; job count 0.
- Locks: no invented `FOUND`.
