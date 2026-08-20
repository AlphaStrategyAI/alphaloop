---
title: "Morning console — guided hypothesis form, structured preview, scannable job cards"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "docs/requirements/2026-08-20-morning-console-ui.md §R3 job-list textContent format only"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-protocol-preview.md
  - docs/requirements/2026-08-20-morning-console-ui.md
---

# Morning console — guided hypothesis form, structured preview, scannable job cards

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged static morning page (`src/alphaloop/webui/static/`)
interaction. Not the frozen Vite SPA. Not CPCV. Not a trading UI. Not
new DSL kinds.

## 1. Why this cycle exists

The product goal is a **verifiable, explorable, easy, visually
distinct, intuitively interactive** overnight research lab that
autonomously searches a **constrained** DSL. PRD §4.1 requires a
one-minute submit: state a hypothesis and choose a market profile, then
review and freeze the protocol. PRD §4.3 requires a five-minute morning
read of conclusion, evidence, and stop reason. Nielsen **recognition
rather than recall** (heuristic 6) says users should see the allowed
signal kinds and hard gates instead of remembering YAML keys.
Bailey / López de Prado: disclose what will be tried (`planned_n_trials`
and the method grid) before freeze — a JSON blob of the grid is not a
disclosure a human can scan.

Today the page can load an example, preview, freeze, and cancel/resume,
but submit is still a blank YAML editor, `#protocol-preview` dumps the
grid as `JSON.stringify`, and job list buttons show only
`run_id — status — outcome`. That is the largest remaining first-release
gap versus one-minute submit and five-minute scan.

## 2. In-scope requirements

### R1. Guided hypothesis form (recognition)

`#hypothesis-form` is the primary before-bed editor. It MUST contain:

| Control | id / name | Values |
| --- | --- | --- |
| statement | `#field-statement` | text |
| economic_logic | `#field-economic-logic` | text |
| signal_mechanism | `#field-signal-mechanism` | `<select>` whose option `value`s include every `ALLOWED_KINDS` entry |
| market_scope | `#field-market-scope` | text |
| market_profile | `#field-market-profile` | `<select>` whose option `value`s include `us-equity-daily` and `crypto-daily` |
| benchmark | `#field-benchmark` | text |
| hard gates | `#field-hard-gates` | checkbox `value`s for every `HardGateName` (`dsr`, `walk_forward`, `vs_random`, `vs_buy_hold`, `vs_benchmark`, `data_consistency`) |
| seed | `#field-seed` | number |
| time_budget_s | `#field-time-budget` | number |
| cost_budget_usd | `#field-cost-budget` | number |

`#spec-yaml` remains the canonical payload posted to preview and freeze.
Form edits rewrite the known flat keys in `#spec-yaml` and MUST preserve
a top-level `dataset:` block if one is already present. YAML edits fill
the form (flat spec keys only). A sync flag MUST prevent rewrite loops.

`#load-example` still fills `#spec-yaml` with the locked example YAML
(verbatim, trailing newline) and MUST populate the form from that YAML.
It still MUST NOT POST a job and MUST NOT invent `FOUND`. Freeze stays
disabled until Preview succeeds on the current textarea.

The form MUST NOT override gates. No control named or labelled "override".

### R2. Structured protocol preview

After a successful parse, `#protocol-preview` inner text MUST still
contain the substring `planned_n_trials`.

The method grid MUST be rendered as `#protocol-grid` list items, one
trial per line, not as a single `JSON.stringify` of the whole grid.
Empty parameter dicts MAY be shown as `{}`. Non-empty rows are
space-separated `key=value` pairs.

### R3. Scannable job cards

Job list buttons MUST set:

- `data-run-id` = `job.run_id`
- `data-status` = `job.status`
- `data-outcome` = `job.research_outcome`

They MUST show the frozen hypothesis statement and `n_trials` for
five-minute scanning. They MUST NOT concatenate extra fields with
` — ` into a single `textContent` identity string (that format is
superseded; e2e helpers read the data attributes).

`#outcome` remains the visual lead of detail. Distinct outcome colors
stay. `FOUND` stays the existing accent green; the others MUST NOT
share that green.

### R4. Visual system (packaged CSS only)

Form controls sit on the existing before-bed card. Job cards show a
muted statement line and a trials line under the status/outcome.
Focus-visible rings apply to form inputs and selects. No Node. No
unfreezing `webui/`. No webfont fetch.

### R5. Docs

`docs/webui.md` first-release lead mentions: guided form, load example,
preview, freeze, cancel/resume on the page.

## 3. Out of scope

- Vite SPA, live trading, CPCV, PBO, new DSL kinds.
- Changing locked `HOST_CONSTRAINT` or help sentences.
- Changing CLI submit into a wizard.
- FakeWorker in morning e2e.
- Inventing `FOUND`.
- A YAML library in the browser; parse only the flat submit keys plus
  preserving `dataset`.

## 4. Acceptance

- Unit: HTML contains `#hypothesis-form` and every `ALLOWED_KINDS` /
  `HardGateName` value; JS writes `data-run-id`, preserves `dataset`,
  renders `#protocol-grid`; submit starts disabled; no "override".
- Integration: daemon still serves `/`; preview/freeze HTTP unchanged.
- E2E: load example fills form `signal_mechanism` to `momentum_12_1`;
  preview still does not create a job and still shows `planned_n_trials`;
  a submitted job card exposes `data-run-id` / `data-outcome` and shows
  the hypothesis statement; legal outcomes only.
