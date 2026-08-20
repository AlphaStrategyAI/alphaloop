---
title: "Skill and POST /v1/datasets name OHLCV rejection"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-ohlcv-csv.md / 2026-08-20-fetch-heritage.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-ohlcv-csv.md
  - docs/requirements/2026-08-20-fetch-heritage.md
---

# Skill and POST /v1/datasets name OHLCV rejection

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged overnight-lab Skill and `POST /v1/datasets` error
body. Not a new hard gate. Not inventing `FOUND`. Not changing
`fetch_data` I/O. Not converting OHLCV to wide close-only. Not
unfreezing `webui/`. Not soak. Not \(N_{\mathrm{eff}}\). Not restyling
chrome.

## 1. Why this cycle exists

CLI dataset ingest rejects per-symbol OHLCV. `alphaloop fetch --help`
says heritage. The packaged Skill still tells agents to cache parquet
or wide CSV and never names `fetch` or `ohlcv`, so an agent can still
pipe fetch output into `alphaloop dataset` or the morning picker.
`POST /v1/datasets` already returns `DatasetRejected` as `error`, but
no test locks `ohlcv` on that path. Nielsen: the agent entry and the
console upload must share the CLI fail-closed reason.

## 2. Best-practice basis

1. **Same forbidden as fetch help.** Skill MUST say `alphaloop fetch`
   is heritage OHLCV and MUST NOT be overnight ingest.
2. **Name the rejection.** Skill MUST contain `ohlcv`. HTTP 400 for an
   OHLCV CSV MUST contain `ohlcv` in `error`.
3. **Do not create a job.** POST MUST NOT enqueue a run. MUST NOT
   return `FOUND`.
4. **Do not reshape Close.** No silent ticker invention.

## 3. In-scope requirements

### R1. Skill

Packaged `src/alphaloop/skills/overnight-lab/SKILL.md` MUST contain
(case-insensitive): `alphaloop fetch`, `heritage`, `ohlcv`, and
`alphaloop dataset`. It MUST tell the agent not to use fetch as
overnight snapshot ingest.

### R2. HTTP

`POST /v1/datasets` with an OHLCV CSV (`open`/`high`/`low`/`close`)
MUST return HTTP 400 whose JSON `error` contains `ohlcv`. Job list
MUST stay empty. Wide close-only CSV still 201.

### R3. Docs

`docs/webui.md` MAY note the picker rejects per-symbol OHLCV. Help /
`HOST_CONSTRAINT` / EXAMPLE_SPEC unchanged.

## 4. Out of scope

- Rewriting `alphaloop fetch`. Auto-submit. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling chrome.

## 5. Acceptance

- Skill text contains fetch, heritage, ohlcv, dataset.
- HTTP OHLCV POST: 400, `ohlcv` in error, no jobs, no `FOUND`.
- Existing wide CSV HTTP upload still 201.
