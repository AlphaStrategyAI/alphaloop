---
title: "Local parquet picker caches a content-addressed dataset"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-form-dataset.md and require-dataset.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-form-dataset.md
  - docs/requirements/2026-08-20-require-dataset.md
---

# Local parquet picker caches a content-addressed dataset

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Local Job API dataset cache + packaged console file picker.
Not SaaS upload. Not auto-submit. Not inventing `FOUND`. Not
\(N_{\mathrm{eff}}\). Not soak execution. Not unfreezing `webui/`.

## 1. Why this cycle exists

PRD §4.1 is one-minute submit. PRD §7 requires a content-addressed
snapshot. The guided form now has `dataset_id` and `sha256` fields, but
a researcher still has to hash a parquet and copy files into
`{data_dir}/datasets/…` by hand. That is recall, not recognition.
The product is local-first: the snapshot stays on the user's machine.

## 2. Best-practice basis

1. **Pick a file, see the identity.** Nielsen recognition. The hash is
   computed from bytes, not typed.
2. **Cache locally, never a third-party host.** PRD §3.2: unwilling to
   upload datasets to SaaS by default. `POST /v1/datasets` is the local
   daemon only.
3. **Do not freeze by picking a file.** Preview and Freeze stay explicit.
   Empty picker does not attach `ds_example`.

## 3. In-scope requirements

### R1. `POST /v1/datasets`

Body: raw parquet bytes (`Content-Type: application/octet-stream` or
unspecified). The handler MUST NOT parse the body as JSON/YAML job
payload.

Rules:

- Empty body → 400, error contains `dataset snapshot is empty`.
- Body larger than 64 MiB → 400, error contains `too large`.
- Bytes that do not start with parquet magic `PAR1` → 400, error
  contains `parquet`.
- Otherwise write `{data_dir}/datasets/{dataset_id}/prices.parquet`
  where `dataset_id` is `ds_` plus the first 16 hex characters of
  SHA-256 of the body, and `sha256` is the full hex digest.
- Response 201 JSON: `{"dataset_id": "…", "sha256": "…"}`.
- Idempotent: posting the same bytes again overwrites the same path and
  returns the same identity.
- MUST NOT create a job. MUST NOT return `FOUND`.

### R2. Console picker

`#hypothesis-form` MUST include `#field-dataset-file` (`type="file"`,
`accept` includes `.parquet`) after `#field-dataset-sha256`.

On file selection the page POSTs the bytes to `/v1/datasets`, then
sets `#field-dataset-id` and `#field-dataset-sha256` from the JSON
and rewrites `#spec-yaml` through `formToYaml`. Freeze stays disabled
until Preview succeeds on the current YAML. Failure text goes to
`#preflight-errors`. The picker MUST NOT call `submitJob`.

Help / `HOST_CONSTRAINT` unchanged. No control labelled override.

### R3. Locks

No FakeWorker in morning e2e. Loopback bind unchanged. No gate
override endpoint.

## 4. Out of scope

- Fetching prices from the network. Browser-side hash without caching.
- Multipart forms. Changing DSR `N`. MCP / cloud workers.

## 5. Acceptance

- Unit/HTTP: parquet POST writes cache and returns matching hash; empty /
  non-parquet rejected; job list unchanged.
- Static: `#field-dataset-file` and `/v1/datasets` in packaged assets.
- E2E: set input files to a local parquet; fields fill; Preview can
  succeed; no job until Freeze.
- Unit + e2e pytest as usual.

## 6. Loop exit

Remaining: human overnight soak; \(N_{\mathrm{eff}}\) must not shrink
DSR `N`; later MCP / cloud workers.
