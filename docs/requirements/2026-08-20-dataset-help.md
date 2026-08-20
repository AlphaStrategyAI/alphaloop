---
title: "Dataset help and getting-started name parquet or CSV"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-dataset-csv.md / 2026-08-20-dataset-yaml.md / 2026-08-20-published-dataset.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-dataset-csv.md
  - docs/requirements/2026-08-20-dataset-yaml.md
  - docs/requirements/2026-08-20-published-dataset.md
---

# Dataset help and getting-started name parquet or CSV

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `alphaloop dataset --help`, `README.md`, and `docs/index.md`.
Not a new hard gate. Not inventing `FOUND`. Not changing cache
identity. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\). Not heritage `alphaloop fetch`. Not restyling
console chrome.

## 1. Why this cycle exists

`alphaloop dataset PATH` already caches parquet **or** a wide
close-only CSV and prints pasteable `dataset:` YAML. `docs/cli.md` and
the overnight-lab Skill say so.

The live parser (cli.md: source of truth) still advertises
`cache a local parquet snapshot` and `local parquet file`.
`README.md` still says "Cache any other parquet". `docs/index.md`
still says "custom parquet". A researcher who runs `--help` or copies
the getting-started list never learns CSV or that stdout is pasteable
YAML. Nielsen: recognition rather than recall. The documented
one-minute path must match the product.

## 2. Best-practice basis

1. **Help matches behavior.** `--help` MUST name parquet or wide
   close-only CSV and MUST NOT imply parquet-only.
2. **Published path matches CLI.** README and `docs/index.md` MUST
   name the same two input shapes and that stdout is pasteable
   `dataset:` YAML (`dataset_id` / `sha256`).
3. **No job, no alpha.** Help and getting-started MUST keep "does not
   create a job" (or equivalent) and MUST NOT claim alpha.
4. **Example YAML unchanged.** Packaged `ds_example` identity stays.
   `EXAMPLE_SPEC`, Help, and `HOST_CONSTRAINT` are not this cycle.

## 3. In-scope requirements

### R1. Argparse help

`alphaloop dataset --help` MUST include:

- `csv` (case-insensitive)
- `parquet` (case-insensitive)
- that the command does not create a job

The positional `path` help MUST NOT be only `local parquet file`.
Parent `alphaloop --help` dataset one-liner MUST NOT say parquet-only.

### R2. Published getting-started

`README.md` and `docs/index.md` MUST each contain:

- `wide close-only CSV` (or the same phrase already used in
  `docs/cli.md`)
- pasteable `dataset:` (the words `pasteable` and `dataset:` in the
  dataset-command prose, not only the example YAML fence)

They MUST NOT tell the operator that custom snapshots are parquet-only
("Cache any other parquet", "custom parquet;" as the only shape).

The getting-started bash list that already shows `alphaloop dataset`
MAY keep `PATH` or a `.parquet` example filename. Surrounding prose
MUST name CSV.

### R3. Docs/cli already shipped

Do not rewrite `docs/cli.md` unless a sentence still says parquet-only.
This cycle is the live parser plus published home/README.

## 4. Out of scope

- Auto-submit. Changing cache hashing. Console picker. Heritage
  `alphaloop fetch`. Soak. \(N_{\mathrm{eff}}\). FakeWorker in
  morning e2e. Unfreezing `webui/`. Restyling chrome.

## 5. Acceptance

- `alphaloop dataset --help` mentions csv, parquet, and does not
  create a job.
- README and `docs/index.md` mention wide close-only CSV and
  pasteable `dataset:`.
- Example YAML still declares `ds_example` with the locked sha256.
- Caching behavior and `--json` keys unchanged. No `FOUND`.
