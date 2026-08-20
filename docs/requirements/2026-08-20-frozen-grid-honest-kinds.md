---
title: "Walk the frozen method grid; honest close-only signal kinds"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: |
  docs/plans/2026-08-19-overnight-lab-phase7-iterative-protocol.md
  Task 3 step 10 (stop the grid on the first complete hard-gate
  failure). Additive to product-positioning-requirements.md §6.1–6.2.
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-protocol-preview.md
  - docs/requirements/2026-08-20-guided-spec-form.md
---

# Walk the frozen method grid; honest close-only signal kinds

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Finish the **already frozen** `method_parameter_grid` after a
complete hard-gate failure, and stop advertising non-directional or
volume-only kinds as first-release `signal_mechanism` values. Not a new
`HardGateName`. Not `S=16`. Not soak. Not expanding the grid after it
fails. Not inventing `FOUND`.

## 1. Why this cycle exists

PRD §6.1 allows methodological repair of **insufficient but relevant
parameter coverage** inside a frozen hypothesis. PRD §6.2 forbids
further search when improvement is possible **only by expanding an
already failed parameter search**. Those are different sentences.

Today `POST /v1/jobs/preview` discloses `planned_n_trials` (three for
every first-class kind). `run_protocol` still returns `NO_EVIDENCE`
after the **first** complete gate failure (`test_failed_gate_does_not_walk_the_parameter_grid`
expects one call). Incomplete evidence already walks later frozen
points (`method_repair`). Complete failure of `{}` therefore makes
preview a lie: the overnight lab does not search the coverage it
froze.

Separately, Parkinson historical volatility is a **feature**, not a
long-only directional signal (m1/m2 retrospectives). `obv_slope` raises
`UnsupportedDslError` without volume, and first-release parquet is
close-only. The guided form still lists both because a unit test
iterates raw `ALLOWED_KINDS`. That is not one-minute honest submit.

## 2. Best-practice basis

1. **Predeclared search, then stop.** Bailey / López de Prado: freeze
   the trial list before looking at results. Walk every frozen point
   until a complete pass (`FOUND`, then existing PBO/holdout) or the
   list is exhausted (`NO_EVIDENCE`). Do not grow the list after it
   fails (`expand_failed_search` stays forbidden).
2. **Do not continue until profitable by changing the story.** Changing
   kind, universe, benchmark, or hard gates remains an economic
   revision and is queued. Frozen-grid continuation MUST NOT call
   `revision_proposer`.
3. **Recognition rather than recall, honestly.** Nielsen heuristic 6:
   the signal `<select>` shows kinds a close-only overnight job can
   actually interpret as a directional `signal_mechanism`. Features and
   volume-only kinds stay in the interpreter for heritage CLI / tests.

## 3. In-scope requirements

### R1. `should_continue` honors remaining frozen points

Add optional keyword-only `frozen_grid_remaining: int = 0`.

When last evidence is complete, not `all_passed`, `proposed_kind` is
`METHOD`, `stop_reason` is `None`, and `frozen_grid_remaining > 0`:

- `continue_search=True`
- `queue_for_human=False`
- `reason="frozen_grid"`

When `frozen_grid_remaining` is omitted or `0`, today's complete-fail
branch still returns `hard_gate_failed`. Explicit
`stop_reason` values in `FORBIDDEN_CONTINUE_REASONS` still win even if
remaining points exist (do not expand a search the caller already
marked failed). Complete pass still returns `found` before this branch.
Budget exhaustion still stops before walking further frozen points.

### R2. `run_protocol` finishes the frozen grid

`run_protocol` MUST pass `frozen_grid_remaining` equal to the count of
later `method_parameter_grid` points whose candidate ids are not in
`completed_trial_ids`.

- Complete fail + remaining frozen points → continue with
  `reason="frozen_grid"`. Do **not** call `revision_proposer`.
- First complete `all_passed` still stops as `FOUND` (then existing
  PBO attach). PBO failure still returns `NO_EVIDENCE` and MUST NOT
  walk remaining points (selection already happened).
- Last frozen point still complete-fail → `hard_gate_failed` →
  `NO_EVIDENCE`.
- Incomplete evidence is unchanged (`method_repair` may still invoke
  `revision_proposer`).

### R3. Honest first-release signal kinds

Keep `ALLOWED_KINDS` as the ten engineer factor names the DSL
interpreter accepts.

Add:

- `FEATURE_KINDS = ("parkinson_hist_vol",)`
- `VOLUME_KINDS = ("obv_slope",)`
- `DIRECTIONAL_SIGNAL_KINDS` — `ALLOWED_KINDS` minus those two tuples,
  in `ALLOWED_KINDS` order

`preflight` MUST reject `parkinson_hist_vol` as `signal_mechanism` with
a message that it is a volatility feature, not a directional signal.
`preflight` MUST reject `obv_slope` with a message that it requires
volume and first-release snapshots are close-only. Unknown kinds stay
rejected as today. `HOST_CONSTRAINT` text MUST NOT change.

`#field-signal-mechanism` option `value`s MUST be exactly the empty
placeholder plus every `DIRECTIONAL_SIGNAL_KINDS` entry. They MUST NOT
include `parkinson_hist_vol` or `obv_slope`. YAML paste of those kinds
still fails at preview/preflight (fail closed, not a silent rewrite).

README first-release `signal_mechanism` list MUST match
`DIRECTIONAL_SIGNAL_KINDS` (heritage CLI may still name the two
excluded factors elsewhere).

## 4. Out of scope

- New YAML gate. Textbook `S=16` CPCV. Soak / 95% overnight.
- FakeWorker in morning e2e. Inventing `FOUND`. Changing
  `HOST_CONSTRAINT`. Unfreezing `webui/`. Volume parquet.
- Treating Parkinson as a tradable long-only signal.
- Calling `revision_proposer` to invent extra grid points after a
  complete fail.

## 5. Acceptance

- Unit: `should_continue` without remaining → `hard_gate_failed`;
  with remaining → `frozen_grid`.
- Unit: all-fail momentum walks three frozen points and is
  `NO_EVIDENCE`; fail-then-pass can `FOUND` on a later frozen point;
  `revision_proposer` is not invoked on `frozen_grid`.
- Unit: preflight rejects Parkinson and OBV with the honest messages;
  form HTML options match `DIRECTIONAL_SIGNAL_KINDS`.
- E2E: preview of Parkinson YAML is not `ok` and creates no job.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
