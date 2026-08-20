---
title: "CLI caches a local parquet snapshot without creating a job"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-dataset-upload.md / require-dataset.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-dataset-upload.md
  - docs/requirements/2026-08-20-require-dataset.md
---

# CLI caches a local parquet snapshot without creating a job

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `alphaloop dataset PATH` writes the same content-addressed
cache as `POST /v1/datasets`. Not a new hard gate. Not inventing
`FOUND`. Not auto-submit. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\). Not changing the console file picker.

## 1. Why this cycle exists

PRD §4.1 is one-minute submit. PRD §7 requires a content-addressed
snapshot. The packaged console already POSTs parquet bytes to
`/v1/datasets` and fills `dataset_id` / `sha256`. CLI researchers
who `alphaloop preview` / `alphaloop submit --spec` still copy files
into `{data_dir}/datasets/…` and hash by hand. That is recall, not
recognition, and it is a different ingest path than the console.

The target user is terminal-first (PRD §3.2). Replay already works
offline against the filesystem. Dataset cache is the same class of
local artifact: bytes on disk, not a Job API mutation.

## 2. Best-practice basis

1. **Same writer as the console.** Call `put_dataset_bytes`. Do not
   invent a second hash rule or a second directory layout.
2. **No daemon required.** Like `alphaloop replay`, this is a local
   filesystem write. Preview/submit still need the daemon.
3. **Do not freeze by caching.** MUST NOT create a job. MUST NOT
   print `FOUND`. MUST NOT contain `target found`.
4. **Nielsen recognition.** Print identity lines a human can paste
   into `ResearchSpec` YAML.

## 3. In-scope requirements

### R1. Command

```
alphaloop dataset PATH [--data-dir DIR] [--json]
```

`PATH` is required and is a local parquet file. `--data-dir` defaults
to `./runs`, the same default as submit/preview.

On success, the command MUST call `put_dataset_bytes(data_dir, blob)`
and MUST NOT contact the daemon.

### R2. Human receipt

Default stdout is exactly four lines plus a trailing newline:

```
dataset_id: {dataset_id}
sha256: {sha256}
Cached: {cached_path}
This cache does not claim alpha or future profitability.
```

`cached_path` is `dataset_parquet_path(data_dir, dataset_id)` as a
string (the file that was written). The first line MUST NOT be
`FOUND`.

`--json` prints `json.dumps` with sorted keys:

`{"cached_path": "…", "dataset_id": "…", "sha256": "…"}`

No `research_outcome` key.

Idempotent: posting the same bytes again overwrites the same path and
prints the same identity.

### R3. Fail closed

Exit 2. Stderr only. MUST NOT print `FOUND` on stdout.

| Case | stderr (exact, plus newline) |
| --- | --- |
| `PATH` missing or not a file | `error: dataset file not found: {PATH}` |
| `DatasetRejected` | `error: {str(exc)}` |
| Other unreadable file (`OSError`) | `error: unable to read dataset file: {exc}` |

`DatasetRejected` messages already contain `empty`, `too large`, or
`parquet`. Keep them.

### R4. Docs

`docs/cli.md` overnight-lab command list includes `dataset`. Skill MAY
say: cache a parquet with `alphaloop dataset PATH` before preview.
Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Auto-submit after cache. Changing `POST /v1/datasets`. Heritage
  `alphaloop fetch` CSV. Soak. \(N_{\mathrm{eff}}\). FakeWorker in
  morning e2e. Unfreezing `webui/`. Restyling console chrome.

## 5. Acceptance

- Parser lists `dataset`. Missing `PATH` is argparse usage (nonzero).
- Valid example parquet without a daemon: exit 0, four-line receipt,
  cache file bytes match, stdout has no `FOUND`.
- `--json` keys are `cached_path`, `dataset_id`, `sha256`.
- Missing file: stderr `error: dataset file not found: …`, exit 2.
- Non-parquet: stderr contains `parquet`, exit 2.
- Docs: `docs/cli.md` documents the command.
