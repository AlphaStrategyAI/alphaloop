---
title: "CLI dataset accepts a wide close-only CSV"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-cli-dataset.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cli-dataset.md
  - docs/requirements/2026-08-20-require-dataset.md
---

# CLI dataset accepts a wide close-only CSV

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `alphaloop dataset PATH` converting a wide CSV into the
same content-addressed parquet cache. Not a new hard gate. Not
inventing `FOUND`. Not auto-submit. Not changing `POST /v1/datasets`
(console picker stays parquet). Not unfreezing `webui/`. Not soak.
Not \(N_{\mathrm{eff}}\). Not heritage `alphaloop fetch` network I/O.

## 1. Why this cycle exists

PRD §4.1 / §7: one-minute submit against a content-addressed snapshot.
`alphaloop dataset PATH` now caches parquet without a daemon. Heritage
`alphaloop fetch` and spreadsheet exports write **CSV**. Those files
fail with `dataset snapshot must be parquet`. CLI researchers still
convert by hand.

The overnight worker reads a wide close-only table: DatetimeIndex,
columns = asset ids (the same shape as packaged `ds_example`). A CSV
in that shape is the same snapshot, not a second research schema.

## 2. Best-practice basis

1. **Same writer after conversion.** Convert CSV → parquet bytes, then
   `put_dataset_bytes`. Identity is the parquet hash, not the CSV
   hash. Receipt lines stay the locked four-line form.
2. **Fail closed on junk.** Unreadable CSV is not a snapshot. Do not
   invent columns. Do not call a network fetch.
3. **Do not freeze by caching.** MUST NOT create a job. MUST NOT print
   `FOUND`. Console `POST /v1/datasets` stays parquet-magic only.
4. **Do not claim alpha.**

## 3. In-scope requirements

### R1. Conversion helper

`cache_dataset_file(data_dir: Path, path: Path) -> DatasetRef`

- Regular file required (the CLI still prints
  `error: dataset file not found: {PATH}` when it is not).
- If bytes start with parquet magic `PAR1`, call `put_dataset_bytes`
  unchanged.
- If `path.suffix` is `.csv` (case-insensitive): parse as a wide
  close-only table (first column = date index, remaining columns =
  asset close prices), write parquet bytes, then `put_dataset_bytes`.
- Otherwise raise `DatasetRejected` whose message contains
  `parquet or csv`.

CSV parse failures raise `DatasetRejected` whose message contains
`csv`. Empty frame (no rows or no asset columns) raises
`DatasetRejected` whose message contains `empty`.

### R2. CLI

`alphaloop dataset PATH` calls `cache_dataset_file`. Human receipt and
`--json` unchanged from
`docs/requirements/2026-08-20-cli-dataset.md`. Same file twice is
idempotent (same parquet bytes → same identity).

### R3. Docs

`docs/cli.md` dataset section: PATH may be parquet or a wide
close-only CSV. Skill MAY say the same. Help / `HOST_CONSTRAINT` /
EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Changing `POST /v1/datasets`. Auto-submit. Fetching Yahoo in this
  command. OHLCV-per-symbol reshape. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling chrome.

## 5. Acceptance

- Parquet path still exit 0 without a daemon (existing tests).
- Wide CSV with date index + `AAPL`,`MSFT`,`SPY` closes: exit 0, cache
  parquet readable with those columns, stdout has no `FOUND`.
- `.txt` still exit 2 with `parquet` in stderr.
- Unreadable `.csv` exit 2 with `csv` in stderr.
- `POST /v1/datasets` still rejects non-parquet.
