---
title: "Published getting-started YAML declares the example dataset"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-require-dataset.md / 2026-08-20-cli-dataset.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-require-dataset.md
  - docs/requirements/2026-08-20-cli-dataset.md
---

# Published getting-started YAML declares the example dataset

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `README.md` and `docs/index.md` example YAML plus the
getting-started CLI list. Not a new hard gate. Not inventing
`FOUND`. Not changing `EXAMPLE_SPEC`. Not unfreezing `webui/`. Not
soak. Not \(N_{\mathrm{eff}}\). Not restyling console chrome.

## 1. Why this cycle exists

Preflight requires a content-addressed `dataset` (`dataset snapshot is
required`). Packaged Load example YAML already declares `ds_example`
and the locked parquet SHA-256. `alphaloop start` copies that snapshot
into the local cache.

The published home (`docs/index.md`) and `README.md` still show the
hypothesis YAML **without** `dataset:`. A researcher who copy-pastes
that block into `spec.yaml` and runs `alphaloop preview` gets a
preflight error. Nielsen: the documented one-minute path must match
the product. Bailey / López de Prado: name the evaluated series
before the result.

`alphaloop dataset PATH` now caches custom parquet, but the
getting-started CLI list does not mention it, so CLI users still copy
files by hand.

## 2. Best-practice basis

1. **Same example as Load example.** Published YAML MUST include the
   same `dataset_id: ds_example` and `sha256` as packaged
   `EXAMPLE_SPEC` (hash of the wheel parquet). Do not invent a second
   example identity.
2. **Dataset is required, not optional.** README MUST NOT say the spec
   declares a dataset only "if" the user chooses. Preflight requires
   it.
3. **Recognition for custom parquet.** Getting-started CLI lists
   `alphaloop dataset PATH` before preview. It does not create a job
   and does not claim alpha.
4. **`alphaloop start` still installs `ds_example`.** The published
   example YAML MUST remain previewable after start without a manual
   `dataset` command.

## 3. In-scope requirements

### R1. Example YAML

The fenced YAML examples in `README.md` and `docs/index.md` that
begin with `statement: 12-1 momentum works in US large caps net of
costs` MUST include:

```yaml
dataset:
  dataset_id: ds_example
  sha256: <sha256 of the packaged example parquet bytes>
```

The digest MUST equal `hash_bytes` of
`alphaloop.runtime.example_dataset` `prices.parquet` (the same lock as
`EXAMPLE_SPEC`). Do not change `EXAMPLE_SPEC`, Help, or
`HOST_CONSTRAINT`.

### R2. Getting-started CLI

`docs/index.md` and `README.md` getting-started bash lists that already
show `alphaloop preview --spec spec.yaml` MUST also contain
`alphaloop dataset` (custom parquet; does not create a job). Place it
before preview.

### R3. Required snapshot copy

The README paragraph that currently says the spec declares a dataset
only "if" MUST instead say a spec **must** declare a content-addressed
`dataset`, that `alphaloop start` installs `ds_example`, and that
other parquet files are cached with `alphaloop dataset PATH`. Missing
or mismatched snapshots still do not synthesize prices or `FOUND`.

## 4. Out of scope

- Changing `EXAMPLE_SPEC` bytes or hash. Auto-submit. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e. Unfreezing
  `webui/`. Restyling console chrome. Heritage `alphaloop fetch`.

## 5. Acceptance

- Static: `README.md` and `docs/index.md` contain `dataset_id: ds_example`,
  the packaged parquet SHA-256, and `alphaloop dataset`.
- README does not use the optional-dataset sentence `If the spec
  declares a dataset`.
- Locks: no invented `FOUND`. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC
  unchanged.
