---
title: "Preflight requires a content-addressed dataset snapshot"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.1 / §7"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-empty-morning.md
---

# Preflight requires a content-addressed dataset snapshot

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Preflight, packaged example snapshot, Load example YAML.
Not \(N_{\mathrm{eff}}\). Not soak execution. Not MCP / cloud. Not
unfreezing `webui/` or `alphaloop.live`.

## 1. Why this cycle exists

PRD §7: every run references an immutable dataset snapshot through a
content-addressed dataset ID and hash; replay must fail closed if the
bytes are missing or the hash differs. PRD §4.1 step 3: preflight the
data before freeze.

The worker already raises if no snapshot exists. Preflight still treats
`dataset` as optional. A guided form or Load example spec with no
`dataset:` block can Preview as `ok`, Freeze, and only then fail
overnight as `INCONCLUSIVE`. That is not one-minute submit. Empty-morning
copy names Load example → Preview → Freeze; that path must remain
honest.

## 2. Best-practice basis

1. **Fail closed at the gate the user can still edit.** Bailey / López
   de Prado: the evaluated series must be the declared data. Discovering
   a missing snapshot after Freeze hides the protocol.
2. **Do not silently attach prices.** Auto-binding undeclared jobs to
   example data would mint research on fixture series. The example
   snapshot exists only so the declared example spec can Preview.
3. **Content-addressed bytes, not a regenerated frame.** Parquet written
   at runtime is not bit-stable. The packaged snapshot is committed
   bytes; its `sha256` is locked in Load example YAML.

## 3. In-scope requirements

### R1. Missing `dataset` is a preflight error

`preflight` MUST append the locked error, verbatim, when
`spec.dataset` is `None`:

`dataset snapshot is required`

Declared snapshots that are missing or hash-mismatched keep today's
errors (`dataset snapshot is unavailable`, hash mismatch). `HOST_CONSTRAINT`
is unchanged. Preflight MUST NOT invent `FOUND`.

`POST /v1/jobs` and `POST /v1/jobs/preview` continue to use `preflight`.
A spec without `dataset` MUST NOT create a job.

### R2. Packaged example snapshot

The wheel MUST ship a close-only `prices.parquet` for `AAPL`, `MSFT`,
and `SPY`. Dataset id is `ds_example`. `JobAPI` MUST copy those bytes
into `{data_dir}/datasets/ds_example/prices.parquet` so Preview of the
example spec can hash-match. Copying MUST NOT attach `dataset` to specs
that omitted it.

### R3. Load example declares that snapshot

`EXAMPLE_SPEC` MUST include:

```yaml
dataset:
  dataset_id: ds_example
  sha256: <sha256 of the packaged parquet bytes>
```

The `sha256` value MUST equal `hash_bytes` of the packaged file.
Load example still MUST NOT POST a job. After Load example, Preview
MUST succeed when the daemon has copied the snapshot (e2e). Help
sentences and `HOST_CONSTRAINT` stay unchanged.

### R4. Locks

No FakeWorker in morning e2e. No gate override. No synthetic RNG prices
when `dataset` is omitted. `N_{\mathrm{eff}}` stays out of DSR `N`.

## 4. Out of scope

- Guided form dataset fields (YAML / Load example remain the path).
- Fetching market data. Overnight soak execution. MCP / cloud workers.

## 5. Acceptance

- `preflight` of a spec with `dataset is None` is not ok and includes
  the locked required-snapshot sentence.
- `test_ok_spec_includes_host_constraint` uses the packaged example
  snapshot.
- Static: `EXAMPLE_SPEC` contains `ds_example` and the packaged hash.
- E2E: Load example then Preview enables Freeze and creates no job.
- YAML without `dataset` shows the locked error and creates no job.
- Unit + e2e pytest as usual.

## 6. Loop exit

Remaining: human overnight soak; \(N_{\mathrm{eff}}\) must not shrink
DSR `N`; later MCP / cloud workers.
