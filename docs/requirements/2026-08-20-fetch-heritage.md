---
title: "alphaloop fetch help is heritage, not overnight ingest"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-ohlcv-csv.md / honest-docs-morning-help.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-ohlcv-csv.md
  - docs/requirements/2026-08-20-honest-docs-morning-help.md
---

# alphaloop fetch help is heritage, not overnight ingest

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `alphaloop fetch --help`, parent `--help` one-liner, and
`docs/cli.md`. Not a new hard gate. Not inventing `FOUND`. Not
changing `fetch_data` I/O. Not converting OHLCV to wide close-only.
Not unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not
restyling chrome.

## 1. Why this cycle exists

Overnight snapshots are parquet or wide close-only CSV via
`alphaloop dataset`. Dataset ingest now rejects per-symbol OHLCV.
`alphaloop loop --help` already says heritage. `alphaloop fetch --help`
still says `获取数据` — the live parser looks like the one-minute
data path. Nielsen: recognition rather than recall. An operator who
fetches then `alphaloop dataset aapl.csv` hits the OHLCV rejection
without having been told fetch is heritage.

## 2. Best-practice basis

1. **Same pattern as `loop`.** Subparser `help` and `description` MUST
   say heritage. MUST NOT sell fetch as overnight ingest.
2. **Name the shape.** `--help` MUST contain `ohlcv` so it matches the
   dataset rejection reason.
3. **Point at `alphaloop dataset`.** Description MUST name parquet or
   wide close-only CSV as the overnight snapshot path.
4. **Do not claim alpha.** Description MUST say it does not claim alpha
   (or the locked no-alpha sentence). MUST NOT print `FOUND` in help.
5. **Do not change bytes.** `fetch_data` still writes per-symbol OHLCV
   when `--output` is set. This cycle is help and docs.

## 3. In-scope requirements

### R1. Argparse

`alphaloop fetch --help` MUST include (case-insensitive):

- `heritage`
- `ohlcv`
- `dataset`

Parent `alphaloop --help` fetch one-liner MUST include `heritage`.
MUST NOT be only `获取数据`.

### R2. Docs

`docs/cli.md` MUST have a short heritage `alphaloop fetch` section:
per-symbol OHLCV, not overnight snapshots; use `alphaloop dataset`.
Overnight-lab command list at the top stays without promoting fetch.

### R3. Unchanged

`HOST_CONSTRAINT`, Help, EXAMPLE_SPEC, `fetch_data` network I/O,
dataset cache identity.

## 4. Out of scope

- Rewriting fetch to emit wide close-only CSV. Auto-submit. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Restyling chrome. Translating every fetch flag.

## 5. Acceptance

- `alphaloop fetch --help` contains heritage, ohlcv, and dataset.
- Parent help fetch line contains heritage.
- `docs/cli.md` marks fetch heritage.
- Existing `test_cli_fetch_calls_yahoo` still passes (I/O unchanged).
