---
title: "Guided form declares dataset id and sha256"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-require-dataset.md and guided-spec-form.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-require-dataset.md
  - docs/requirements/2026-08-20-guided-spec-form.md
---

# Guided form declares dataset id and sha256

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged `#hypothesis-form` dataset controls. Not fetching
market data. Not auto-binding undeclared jobs to `ds_example`. Not
\(N_{\mathrm{eff}}\). Not soak execution. Not unfreezing `webui/`.

## 1. Why this cycle exists

Preflight now requires a content-addressed dataset. Load example
declares packaged `ds_example`. The guided form still has no dataset
controls, so a researcher who types a hypothesis without Load example
must invent YAML keys. Nielsen: recognition rather than recall. PRD
§4.1 is one-minute submit of a hypothesis and market profile, then
review and freeze — including the data the protocol will hash.

## 2. Best-practice basis

1. **Show the snapshot identity in the same form as the hypothesis.**
   Bailey / López de Prado: the reader must see what series will be
   tried. `dataset_id` and `sha256` are that identity.
2. **Do not silently fill `ds_example` on first paint.** Auto-binding
   empty fields to fixture prices would mint research on example
   bytes. Empty fields omit the `dataset:` block; Preview stays
   `dataset snapshot is required`.
3. **Load example remains the one-minute path.** It fills the new
   fields from locked EXAMPLE_SPEC.

## 3. In-scope requirements

### R1. Form controls

`#hypothesis-form` MUST include:

| Control | id |
| --- | --- |
| dataset id | `#field-dataset-id` |
| dataset sha256 | `#field-dataset-sha256` |

Place them in `#hypothesis-form .form-grid` after cost budget. Labels
MUST NOT contain "override". Help / `HOST_CONSTRAINT` unchanged.

### R2. YAML round-trip

Form edits rewrite a top-level `dataset:` block from the two fields
when both are non-empty (trimmed). If either field is empty, omit
`dataset:`. YAML edits fill the two fields from nested
`dataset.dataset_id` and `dataset.sha256`. A sync flag MUST prevent
rewrite loops (existing `syncingForm`).

`#load-example` MUST populate both fields from EXAMPLE_SPEC. It still
MUST NOT POST a job.

Queued follow-up Load into editor MAY copy `job.dataset` into empty
dataset fields so the same snapshot stays declared. It MUST NOT
auto-submit.

### R3. Locks

No FakeWorker in morning e2e. No gate override. No inventing `FOUND`.
Do not auto-attach `ds_example` when fields are empty.

## 4. Out of scope

- Uploading parquet from the browser. Computing sha256 in the page.
- Guided form file picker. MCP / cloud. Soak execution.

## 5. Acceptance

- Static: both field ids in HTML; `formToYaml` / `yamlToForm` read
  them; EXAMPLE_SPEC still declares `ds_example`.
- E2E: Load example fills both fields; Preview still enables Freeze
  with zero jobs.
- E2E: empty dataset fields + Preview shows `dataset snapshot is
  required` and creates no job.
- Unit + e2e pytest as usual.

## 6. Loop exit

Remaining: human overnight soak; \(N_{\mathrm{eff}}\) must not shrink
DSR `N`; later MCP / cloud workers.
