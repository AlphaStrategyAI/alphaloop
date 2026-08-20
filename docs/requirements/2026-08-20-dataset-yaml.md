---
title: "CLI dataset receipt is pasteable ResearchSpec YAML"
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

# CLI dataset receipt is pasteable ResearchSpec YAML

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Human stdout of `alphaloop dataset PATH`. Not a new hard
gate. Not inventing `FOUND`. Not auto-submit. Not changing
`--json` keys. Not unfreezing `webui/`. Not soak. Not
\(N_{\mathrm{eff}}\). Not changing the console picker.

## 1. Why this cycle exists

Preflight requires a content-addressed `dataset` block. Console picker
fills `#field-dataset-id` / `#field-dataset-sha256` and rewrites YAML.
CLI `alphaloop dataset` prints top-level `dataset_id:` and `sha256:`
lines that are **not** valid `ResearchSpec` YAML. A researcher still
re-indents by hand before `alphaloop preview`. Nielsen: recognition
rather than recall.

## 2. Best-practice basis

1. **Same mapping as `ResearchSpec.to_dict`.** The paste block is
   `dataset: { dataset_id, sha256 }` with two-space indent.
2. **Keep Cached + no-alpha.** Path and the locked sentence stay after
   the YAML so a human can see where bytes landed. First line MUST NOT
   be `FOUND`.
3. **`--json` unchanged.** Agents already get identity keys. Do not
   add `research_outcome`.
4. **Do not freeze by caching.** MUST NOT create a job.

## 3. In-scope requirements

### R1. Human receipt

`format_dataset_receipt` default stdout is exactly:

```
dataset:
  dataset_id: {dataset_id}
  sha256: {sha256}
Cached: {cached_path}
This cache does not claim alpha or future profitability.
```

plus a trailing newline. Five content lines (six including the
`dataset:` key line — six lines total in `splitlines()`).

### R2. JSON

`--json` remains `json.dumps` sorted keys
`{cached_path, dataset_id, sha256}`. No `research_outcome`.

### R3. Docs

`docs/cli.md` describes the pasteable `dataset:` block. Skill MAY say
paste the YAML into the spec. Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC
unchanged.

## 4. Out of scope

- Auto-submit. Changing console picker. Soak. \(N_{\mathrm{eff}}\).
  FakeWorker in morning e2e. Unfreezing `webui/`. Restyling chrome.

## 5. Acceptance

- Parquet cache without daemon: stdout `splitlines()` matches the six
  lines above; no `FOUND`.
- `--json` keys unchanged.
- CSV cache still exit 0 and contains `dataset_id:`.
- Docs: `docs/cli.md` mentions pasteable `dataset:`.
