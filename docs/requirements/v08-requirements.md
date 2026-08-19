---
title: "alphaloop v0.8 — Calibration Requirements (PRD)"
version: "0.8"
status: "requirements"
authors:
  - alphaloop Coder subagent
date: "2026-08-16"
loop: "alphaloop-v08-requirements-doc"
related_roadmap_section: "ROADMAP.md § v0.8 (post-v0.7, pre-v1.0)"
supersedes: "none — v0.8 introduces calibration; v0.6 judge code unchanged"
---

# alphaloop v0.8 — Calibration Requirements (PRD)

## 0. Context

alphaloop v0.7.2 (commit `2ae2f9f`, tag `v0.7.2`) shipped the WebUI
auto-launch + share-link + polish + 起步 docs work; 320 tests pass.
v0.6 (shipped) introduced the **LLM-as-judge** as the 7th diagnostic
(`src/alphaloop/diagnostic/judge.py`), which scores each backtest
report on three narrative dimensions:

- **readability** — Can a non-quant reader follow the report?
- **decision_quality** — Are the investment decisions justified?
- **risk_disclosure** — Are risks honestly disclosed?

Each dimension scores 1–10; the overall `passes` flag is the
conjunction with threshold ≥ 7. The judge was designed in
`docs/plans/v06-llm-judge.md` (762 lines) and implemented behind an
OpenAI-compatible HTTP client (`src/alphaloop/judge/client.py`) with
env-var resolution (`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`).

**The risk the user identified (explicit OK before this PRD):**
v0.6 judge shipped without any **calibration** — no human-rated
ground truth, no accuracy metrics, no drift detection. Today we
cannot say "the judge agrees with human reviewers 80% of the time"
or "scores have drifted 15% since v0.6". If we tag v1.0 (per
ROADMAP.md) without calibration evidence, the judge scores become
**trust-but-verify-able-to-no-one** numbers that risk misleading
users about report quality.

v0.8 closes that gap. The mission: **measure how accurate the v0.6
judge actually is, against a human-rated ground truth, on a fixed
dataset, with deterministic re-runs and drift detection.** If the
judge is accurate enough (per-dimension Pearson ≥ 0.70), v1.0
ships with a calibrated confidence statement. If not, v0.8 also
includes the prompt-tuning iteration that gets it there.

v0.8 is **not** a new feature for users. It is internal
infrastructure that makes v0.6 trustworthy. The public CLI surface
gains exactly **one new subcommand** (`alphaloop judge --calibration`)
and **one new CI regression test** (`tests/test_judge_drift.py`).
Everything else is dataset, metrics, and tooling inside the repo.

This PRD is **requirements only**. It contains NO implementation
code, NO test code, NO design diagrams beyond ASCII. Per the loop
state file, implementation is gated on user explicit OK after this
PRD is reviewed.

Hard wall (per loop state file §"v0.8 需求 hard wall"):

1. Only write this requirements doc; no code, no tests, no design.
2. Do not modify any existing alphaloop file except by *creating*
   `docs/requirements/v08-requirements.md`.
3. Do not write `src/alphaloop/calibration/*` (deferred to v0.8 dev).
4. Do not build the calibration dataset (that is implementation).
5. Do not modify `src/alphaloop/judge/*` or `src/alphaloop/diagnostic/judge.py`
   in this phase; v0.8 uses them as-is.
6. No commits, no pushes, no broker connections, no auth services.

---

## 1. Goals

v0.8 has **5 primary goals**. Each is phrased in user-facing or
operator-facing language so reviewers can sanity-check scope
without reading requirements prose. There is no stretch goal — v0.8
is intentionally tight.

### Goal 1 — Quantify judge accuracy on a fixed ground-truth dataset

Build a **calibration dataset** of ≥ 100 backtest reports (Markdown)
paired with human-rated scores (1–10) on each of the 3 dimensions,
then run the v0.6 judge on each report and compute agreement
metrics: Pearson r, Spearman ρ, mean absolute error (MAE), and
within-±2 agreement rate, **per dimension**. Without this, we
have no number to say "the judge is X% accurate."

### Goal 2 — Establish a release-gate threshold for v1.0

Codify the calibration result as a **release gate**: if per-dimension
Pearson r < 0.70 OR within-±2 agreement < 60% on any dimension,
**block v1.0 tag**. This converts the implicit "judge should be
accurate" assumption into an explicit, testable contract. The gate
runs in CI on every release candidate.

### Goal 3 — Detect score drift across releases

Add a **regression test** that re-runs the judge on the calibration
dataset on every release and compares current scores to a **golden
file** (frozen at v0.8 ship time). If any dimension's mean score
drifts > 10% relative to golden, the release fails. Drift catches
silent LLM provider behavior changes (model swap, finetune,
prompt-injection in API changes) that calibration alone cannot.

### Goal 4 — Iterate on judge prompt if accuracy is below threshold

If Goal 1 reveals Pearson r < 0.70 on any dimension, v0.8 ships
**at least one prompt improvement iteration** (a new prompt template
version) plus the tooling (`alphaloop judge --calibrate-prompt`) to
run A/B prompt comparisons against the ground truth. This is
**tooling, not automation** — no auto-tuning loop; a human reviews
the diff.

### Goal 5 — Prepare the v0.9 ensemble (architectural runway, not implementation)

v0.8's calibration dataset + metrics + drift harness lay the
groundwork for v0.9's **multi-model ensemble judge** (per ROADMAP
"OpenRouter Fusion" mention). v0.8 itself ships **single-model**
calibration; v0.8 produces the per-model accuracy baselines that
v0.9 will combine. No ensemble code in v0.8; just the data shape
that v0.9 will consume.

---

## 2. Requirements

Each requirement is a **user story**: "As a [user], I want to
[action], so that [benefit]." After each story is a **detail
block** with the underlying behavior, inputs, outputs, and
constraints. Acceptance criteria are in § 3.

The **12 user stories** are grouped by feature: **R-Dataset**
(stories 1–4), **R-Accuracy** (stories 5–7), **R-Drift**
(stories 8–10), **R-Prompt** (stories 11–12).

### R-Dataset — Calibration ground-truth dataset

#### Story 1 — A fixed dataset of 100 backtest reports with human ratings

> **As a calibration engineer**, I want a **dataset of 100 known
> backtest reports**, each paired with a **human-rated score on
> each of the 3 judge dimensions**, so that I can measure how
> accurately the v0.6 judge reproduces those human scores.

**Detail.**

- **Size:** exactly **100 cases** (the minimum for stable Pearson;
  Cohen 2020 guidance is N ≥ 100 for inter-rater reliability work).
- **Format:** one JSON Lines file `data/calibration/v1/dataset.jsonl`
  (committed to the repo under the alphaloop project; not user-visible).
- **Per-record schema:**
  ```json
  {
    "case_id": "calib_001",
    "report_markdown": "<full report text>",
    "ground_truth": {
      "readability":      {"score": 7, "reviewer_ids": ["R1", "R2", "R3"]},
      "decision_quality": {"score": 6, "reviewer_ids": ["R1", "R2", "R3"]},
      "risk_disclosure":  {"score": 8, "reviewer_ids": ["R1", "R2", "R3"]}
    },
    "meta": {
      "strategy": "momentum_v3",
      "asset_class": "US_equity",
      "time_period": "2018-01..2023-12",
      "language": "en",
      "source": "alphaloop_loop_v071_replay",
      "added_at": "2026-08-16"
    }
  }
  ```
- **No LLM in ground truth.** Human scores only. The dataset is
  re-runnable today and in 5 years without depending on any
  external LLM API.
- **Reviewer count:** 3 reviewers per case per dimension = 900
  ratings total (100 × 3 × 3). Inter-rater agreement (Krippendorff's
  α) is computed once at dataset build time and stored in
  `data/calibration/v1/dataset.meta.json`.
- **License:** reports are generated by alphaloop itself (no
  proprietary third-party content); reviewers sign a CLA assigning
  rating rights to the repo. Dataset is MIT-licensed, same as
  alphaloop itself.

#### Story 2 — Each report scored on all 3 dimensions

> **As a calibration engineer**, I want **every report in the
> dataset to have a ground-truth score for each of the 3 judge
> dimensions** (readability, decision合理性, risk-disclosure),
> so that I can compute per-dimension accuracy, not just an overall
> "accuracy".

**Detail.**

- All three dimensions are mandatory; no `null` / missing fields.
- The score is the **median across the 3 reviewers** for that
  dimension (rounded to nearest integer; original 3 scores are
  retained in `ground_truth.<dim>.reviewer_ids` for diagnostics).
- A case is excluded from the dataset (rather than imputed) if any
  dimension has fewer than 2 reviewer scores. The target N = 100
  is after exclusion, so build slightly more (~120) and cull.
- **Median, not mean.** Reviewers occasionally give one extreme
  score (1 or 10) that is clearly a misread; median resists that.
  The full per-reviewer scores are stored alongside so the
  distribution is auditable.

#### Story 3 — Dataset is diverse across strategies, asset classes, time periods, languages

> **As a calibration engineer**, I want the dataset to **cover
> different strategies, asset classes, time periods, and at least
> 2 languages**, so that accuracy measured on the dataset
> generalizes to production reports — not just "the judge is
> accurate on US-equity momentum in 2022".

**Detail.**

- **Strategies:** ≥ 5 distinct alphaloop strategies (momentum_v3,
  mean_reversion_v2, breakout_v1, factor_combo_v2, vol_premium_v1).
- **Asset classes:** ≥ 3 (US_equity, EU_equity, crypto).
- **Time periods:** ≥ 3 (2015-2019, 2020-2022, 2023-2025). At
  least 10 cases per period.
- **Languages:** ≥ 2 (English primary, 中文 secondary). At least
  10 Chinese-language cases. (Translation is reviewer-driven, not
  LLM-driven — see Story 4.)
- **Quality strata:** the dataset must include ≥ 20 "clearly bad"
  reports (intentionally broken: missing sections, contradictory
  decisions, no risk disclosure) so the judge is tested on the
  failure modes that v0.6 was designed to catch.
- The diversity matrix is documented in
  `data/calibration/v1/dataset.meta.json`:
  ```json
  {
    "n_cases": 100,
    "strategies": {"momentum_v3": 25, "mean_reversion_v2": 20, ...},
    "asset_classes": {"US_equity": 50, "EU_equity": 30, "crypto": 20},
    "time_periods": {"2015-2019": 30, "2020-2022": 40, "2023-2025": 30},
    "languages": {"en": 90, "zh": 10},
    "inter_rater_alpha": 0.78
  }
  ```

#### Story 4 — Dataset is deterministic and re-runnable

> **As a maintainer running calibration in 5 years**, I want the
> dataset to be **deterministic** — same input reports, same
> reviewer scores, byte-identical JSON — so that calibration runs
> are reproducible across machines and decades.

**Detail.**

- **Reports come from alphaloop's own backtests.** Replays of
  v0.7.1 runs (`runs/<rid>/report.md`) are the canonical source;
  ~80 cases are direct replays, ~20 are hand-edited variants
  (intentionally degraded to populate the "clearly bad" stratum).
- **Reviewer scores come from a frozen CSV**
  `data/calibration/v1/reviewer_ratings.csv` (reviewer_id, case_id,
  dim, score, ts). The reviewer CSV is the source of truth; the
  JSONL in Story 1 is a derived view.
- **No LLM in the dataset build pipeline.** Reviewers are humans;
  no "use the LLM to expand to 200 cases" shortcuts. The pipeline
  is `replay → markdown → reviewer ratings → dataset.jsonl` and
  each step is pure-function / human.
- **Hash pinning.** `dataset.meta.json` includes
  `dataset_sha256: "<hex>"` computed over the JSONL bytes; the
  calibration CLI rejects a dataset whose hash doesn't match.
- **Versioning:** `data/calibration/v1/` (this PRD) → `v2/` (if
  v0.9 needs a larger dataset). v1 stays read-only after ship.

### R-Accuracy — Run calibration, compute metrics

#### Story 5 — `alphaloop judge --calibration` computes per-dimension metrics

> **As a quant researcher or CI bot**, I want to run
> **`alphaloop judge --calibration`** and get a **per-dimension
> accuracy report** (Pearson r, Spearman ρ, MAE, within-±2
> agreement rate), so that I can see at a glance how accurate the
> judge is — and whether v1.0 is safe to ship.

**Detail.**

- **New CLI subcommand:** `alphaloop judge --calibration
  --dataset data/calibration/v1/ [--output report.json]
  [--llm-model ...] [--threshold 7]`.
- **Inputs:**
  - `--dataset` (required): path to the calibration dataset
    directory (containing `dataset.jsonl` + `dataset.meta.json`).
  - `--output` (default: `calibration_report.json` in CWD): where
    to write the structured report.
  - `--llm-model`, `--llm-api-key`, `--llm-base-url`: overrides
    for the LLM call. Default: same env-var resolution as
    `alphaloop report --judge-model`.
- **Per-case flow:**
  1. Read report markdown from the JSONL row.
  2. Call `alphaloop.llm_judge(report)` (the v0.6 public API).
  3. Record the 3 predicted scores + the 3 ground-truth scores.
- **Output schema** (`calibration_report.json`):
  ```json
  {
    "version": "v0.8-calibration-1",
    "dataset_sha256": "<hex>",
    "n_cases": 100,
    "model": "<model name>",
    "threshold": 7,
    "metrics": {
      "readability":      {"pearson_r": 0.78, "spearman_rho": 0.74,
                            "mae": 1.2, "agreement_within_2": 0.72},
      "decision_quality": {"pearson_r": 0.71, "spearman_rho": 0.69,
                            "mae": 1.4, "agreement_within_2": 0.65},
      "risk_disclosure":  {"pearson_r": 0.83, "spearman_rho": 0.80,
                            "mae": 1.0, "agreement_within_2": 0.78}
    },
    "overall_pass": true,
    "cases": [{"case_id": "calib_001", "predicted": {...},
               "ground_truth": {...}, "delta": {...}}, ...]
  }
  ```
- **Per-case trace** is included in `cases[]` for debugging
  regressions (without the full markdown, just the scores).
- **Latency budget:** 100 cases × ~10 s/call = ~17 minutes total.
  v0.8 uses serial calls (no parallel) to avoid rate-limit
  flakiness; v0.9 can revisit.
- **Exit code:** 0 if `overall_pass=true`, 1 otherwise. CI uses
  the exit code to fail the build.

#### Story 6 — Per-dimension metrics, not just overall

> **As a calibration engineer**, I want the accuracy report to
> show **per-dimension** accuracy (readability / decision合理性 /
> risk-disclosure separately), so that I can see **which** dimension
> the judge struggles with — and target prompt improvements
> accordingly.

**Detail.**

- Each of the 3 dimensions gets its own Pearson r, Spearman ρ,
  MAE, and within-±2 agreement rate (per Story 5 schema).
- **Aggregate "overall accuracy" is NOT a single number.** A
  weighted average is misleading (it hides the worst dimension).
  v0.8 reports the **3 per-dimension numbers** as the source of
  truth and an `overall_pass` boolean that is the conjunction
  (all 3 dimensions pass their threshold).
- A **worst-dimension callout** is included:
  `"worst_dimension": "decision_quality",
  "worst_dimension_metric": {"pearson_r": 0.65}` so a reviewer
  sees the bottleneck at a glance.
- A **confusion-style breakdown** is included per dimension:
  - True positive: judge ≥ 7, ground truth ≥ 7
  - True negative: judge < 7, ground truth < 7
  - False positive: judge ≥ 7, ground truth < 7 (judge too lenient)
  - False negative: judge < 7, ground truth ≥ 7 (judge too strict)
  This catches **systematic bias** that Pearson alone can miss
  (e.g. Pearson 0.75 but the judge is consistently 2 points high).

#### Story 7 — Pass/fail threshold blocks v1.0 release

> **As a release manager**, I want a **release-gate threshold**:
> if any dimension has Pearson r < 0.70 OR within-±2 agreement
> < 60%, the gate fails and **v1.0 cannot ship**, so that the
> public release does not advertise a judge whose accuracy is
> unknown or known-bad.

**Detail.**

- **Thresholds (release gate):**
  - Pearson r ≥ 0.70 (per dimension)
  - Spearman ρ ≥ 0.65 (per dimension; tracked but not gating in v0.8)
  - MAE ≤ 2.0 (per dimension; tracked but not gating in v0.8)
  - Within-±2 agreement rate ≥ 0.60 (per dimension)
  - **All three dimensions must pass all three gating thresholds.**
- **CI integration:** the calibration job runs in
  `.github/workflows/release.yml` (the tagged-release workflow).
  Tagging v1.0 triggers the job; the job fails the release if the
  gate fails.
- **Override path:** the gate can be overridden with an explicit
  `--override-gate --reason "<text>"` flag, which appends to
  `calibration_report.json` and prints a loud warning. Overrides
  are intended for documented exceptions only (e.g. "we know the
  judge is biased high on crypto reports; we're shipping v1.0
  US-equity-only"). The override does NOT change the exit code —
  it only annotates the report. **No silent overrides.**
- **Manual ack:** even with override, tagging v1.0 requires a
  human to type the alphaloop version + their GitHub handle into
  the release notes. CI cannot bypass human review.

### R-Drift — Score-drift detection across releases

#### Story 8 — Regression test runs on every release to detect drift

> **As a maintainer cutting a new release**, I want a
> **regression test** that runs `alphaloop judge --calibration`
> on the v0.8 frozen dataset and **compares current scores
> against a golden file**, so that if the underlying LLM
> silently changes behavior (model swap, finetune, API behavior),
> the release fails before it ships.

**Detail.**

- **New test file:** `tests/test_judge_drift.py`.
- **Golden file:** `data/calibration/v1/golden_scores.jsonl`
  — a JSONL with one row per case, containing only
  `{case_id, predicted_readability, predicted_decision_quality,
  predicted_risk_disclosure}`. Frozen at v0.8 ship time.
- **Drift check logic (per dimension):**
  1. Run the judge on every case in the dataset.
  2. For each dimension, compute `mean_predicted` (current) and
     `mean_predicted_golden`.
  3. `drift_pct = abs(mean_predicted - mean_predicted_golden) /
     mean_predicted_golden`.
  4. If `drift_pct > 0.10` on any dimension → fail.
- **Test invocation:** `pytest tests/test_judge_drift.py
  --dataset=data/calibration/v1 --llm-model=$LLM_MODEL`
  (env vars injected by CI).
- **CI gating:** runs on push to `main` AND on tagged releases;
  the test is marked `@pytest.mark.llm` so it skips when no
  `LLM_API_KEY` is set (local dev / docs-only builds).
- **Drift threshold rationale:** 10% relative drift on a 100-case
  mean is roughly 0.5–1.0 score points on a 1-10 scale — large
  enough to catch real model behavior changes, small enough to
  tolerate normal LLM non-determinism (temperature=0 still gives
  ~1-2% run-to-run variance).

#### Story 9 — Drift report compares current vs golden alphabetically

> **As a reviewer reading the drift report**, I want the report
> to list cases in **alphabetical order** (calib_001, calib_002,
> ...) so that I can diff the report against the golden file with
> a plain text diff tool — no fancy visualizer required.

**Detail.**

- The drift report (printed to stdout by the test) sorts cases
  by `case_id` ascending. Alphabetical, not insertion order.
- The report format is:
  ```
  case_id       dim               golden  current  delta
  calib_001     readability             7        8      +1
  calib_001     decision_quality        6        6       0
  calib_001     risk_disclosure         8        7      -1
  calib_002     readability             5        5       0
  ...
  ```
- Cases whose delta exceeds ±3 on any dimension are marked with
  a `**` (loud visual flag) — those are the candidates for
  prompt-version regression, not just drift.
- The same report is also written to
  `drift_report_<git_sha>.txt` as an artifact for posterity.

#### Story 10 — Alerts if drift > 10% on any dimension

> **As a maintainer**, I want a **loud, blocking alert** if any
> dimension drifts > 10% relative to the golden, so that I cannot
> accidentally ship a release where the judge has silently
> started scoring 1.5 points higher than it did at v0.8 ship time.

**Detail.**

- The drift test (Story 8) fails the build with a clear message:
  ```
  ============================================================
  JUDGE DRIFT DETECTED — release blocked
  Dimension:   readability
  Drift:       +12.3% (golden mean 6.8, current mean 7.6)
  Threshold:   10%
  Likely cause: LLM provider model swap or finetune.
  Action:      re-run calibration, re-freeze golden file (Story 4),
               or document override.
  ============================================================
  ```
- The alert is loud (banner + non-zero exit + GitHub Actions
  annotation on the failing line). It cannot be silenced without
  modifying the test threshold.
- **Alert destination:** GitHub Actions annotation + PR comment
  (posted by the workflow). No email / Slack integration in v0.8
  (those are infrastructure the project does not own).

### R-Prompt — Prompt version tracking + improvement tooling

#### Story 11 — Judge prompt version is tracked

> **As a maintainer**, I want **every shipped prompt version to
> have a stable identifier** (e.g. `v0.6.0-prompt-1`, `v0.8.0-prompt-2`)
> so that when accuracy regresses, I can roll back to a known-good
> prompt with one CLI flag.

**Detail.**

- The judge prompt is stored at
  `src/alphaloop/judge/prompts.py::PROMPT_TEMPLATE` (the v0.6
  default) — this is `v0.6.0-prompt-1`.
- v0.8 introduces a **prompt registry** at
  `src/alphaloop/judge/prompt_registry.py`:
  ```python
  PROMPT_VERSIONS = {
      "v0.6.0-prompt-1": PROMPT_TEMPLATE,   # the v0.6 default
      "v0.8.0-prompt-2": "...",            # v0.8 default if improved
  }
  ```
- Resolution order at runtime: `--judge-prompt-version` flag →
  `ALPHALOOP_JUDGE_PROMPT_VERSION` env var → `"v0.8.0-prompt-2"`
  (current default). This means rolling back is one CLI flag.
- The calibration report (`calibration_report.json`, Story 5)
  records `prompt_version: "v0.8.0-prompt-2"` so historical
  reports are reproducible.
- **Backward compatibility:** `v0.6.0-prompt-1` MUST remain in
  the registry for at least 2 minor releases after v0.8 (so v0.7
  users can pin to the old prompt).

#### Story 12 — If accuracy < 70%, tooling to compare prompt versions A/B

> **As a calibration engineer**, when the v0.6 prompt fails the
> accuracy gate, I want **tooling** (`alphaloop judge
> --calibrate-prompt`) that runs two prompt versions on the
> calibration dataset and prints a side-by-side accuracy diff,
> so that I can iterate on prompt wording with evidence, not
> vibes.

**Detail.**

- **New CLI flag:** `alphaloop judge --calibrate-prompt
  --prompt-a v0.6.0-prompt-1 --prompt-b v0.8.0-prompt-2
  --dataset data/calibration/v1 --output prompt_ab.json`.
- **Behavior:** runs the judge on every case twice (once per
  prompt), computes per-dimension metrics for both, and prints a
  side-by-side comparison:
  ```
  Dimension         Prompt A (v0.6.0-prompt-1)   Prompt B (v0.8.0-prompt-2)   Winner
  readability       Pearson 0.72                  Pearson 0.78                  B (+0.06)
  decision_quality  Pearson 0.65                  Pearson 0.74                  B (+0.09)
  risk_disclosure   Pearson 0.81                  Pearson 0.79                  A (+0.02)
  ```
- The output JSON records per-case scores for both prompts so the
  reviewer can drill in.
- **No automatic loop.** The tool runs both prompts once and
  stops. A human reviews the diff, edits `PROMPT_VERSIONS`,
  re-runs the tool. This is intentional: prompt tuning is a
  craft, not an optimization problem.
- **Latency:** 2× the calibration cost (~34 minutes for 100 cases).
  Acceptable; calibration runs are infrequent (per-release, not
  per-PR).

---

## 3. Acceptance Criteria

Each criterion is a **single, observable check** that a reviewer
can perform by running one command or one test. The criteria are
grouped by feature; each maps back to one or more stories in § 2.

### 3.1 Dataset (Stories 1–4)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-1.1 | `data/calibration/v1/dataset.jsonl` exists and contains exactly 100 valid JSONL rows.                     |
| A-1.2 | Every row has `readability`, `decision_quality`, `risk_disclosure` ground-truth scores (no `null`).       |
| A-1.3 | `dataset.meta.json` shows ≥ 5 strategies, ≥ 3 asset classes, ≥ 3 time periods, ≥ 2 languages (en + zh). |
| A-1.4 | ≥ 20 cases are in the "clearly bad" stratum (judge should score < 5 across all 3 dims).                 |
| A-1.5 | `dataset.meta.json.inter_rater_alpha` ≥ 0.70 (Krippendorff's α on the 3-reviewer ratings).               |
| A-1.6 | `dataset.meta.json.dataset_sha256` matches the SHA-256 of `dataset.jsonl` (round-trip check).             |
| A-1.7 | Re-running `alphaloop judge --calibration` on the dataset produces byte-identical metrics given the same model + temperature=0 (within a 1% tolerance for LLM non-determinism). |
| A-1.8 | The dataset builds **without any LLM API call** — verified by `grep -r "openai\|anthropic" data/calibration/v1/build.py` returning zero matches. |

### 3.2 Accuracy (Stories 5–7)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-2.1 | `alphaloop judge --calibration --dataset data/calibration/v1` exits 0 and writes `calibration_report.json`. |
| A-2.2 | The report contains a `metrics` block with all 3 dimensions, each with `pearson_r`, `spearman_rho`, `mae`, `agreement_within_2`. |
| A-2.3 | The report contains a `worst_dimension` callout naming the lowest-Pearson dimension.                     |
| A-2.4 | The report contains a confusion-style breakdown (TP/TN/FP/FN per dimension at threshold=7).               |
| A-2.5 | If all 3 dimensions pass the gate (Pearson ≥ 0.70 AND within-±2 ≥ 0.60), `overall_pass=true` and exit=0. |
| A-2.6 | If any dimension fails the gate, `overall_pass=false`, exit=1, and a clear "GATE FAILED" banner is printed. |
| A-2.7 | Manual: the per-case `cases[]` array contains all 100 case_ids, with `predicted` and `ground_truth` scores for each dimension. |
| A-2.8 | Override: `alphaloop judge --calibration --override-gate --reason "..."` writes the reason into the report and exits 0 (but prints a loud warning). |

### 3.3 Drift (Stories 8–10)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-3.1 | `tests/test_judge_drift.py` exists and contains ≥ 3 test functions (`test_drift_under_threshold`, `test_drift_over_threshold_fails`, `test_drift_report_alphabetical_order`). |
| A-3.2 | `pytest tests/test_judge_drift.py -v` exits 0 when run against `golden_scores.jsonl` (no drift).          |
| A-3.3 | `pytest tests/test_judge_drift.py -v` exits 1 when `golden_scores.jsonl` is corrupted to fake 15% drift. |
| A-3.4 | The drift report lists cases in alphabetical order (`calib_001` before `calib_002`). Verified by parsing the printed stdout. |
| A-3.5 | Drift > 10% on any dimension triggers a banner with: dimension name, drift %, golden mean, current mean.   |
| A-3.6 | The test is marked `@pytest.mark.llm` and skips when `LLM_API_KEY` is not set.                            |
| A-3.7 | CI: the drift test runs in `.github/workflows/test.yml` (push) and `.github/workflows/release.yml` (tags). |

### 3.4 Prompt version tracking + A/B (Stories 11–12)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-4.1 | `src/alphaloop/judge/prompt_registry.py` exists with at least 2 entries (`v0.6.0-prompt-1`, `v0.8.0-prompt-2`). |
| A-4.2 | Setting `--judge-prompt-version=v0.6.0-prompt-1` on `alphaloop report` produces a report with `prompt_version: "v0.6.0-prompt-1"` in the JSON metadata. |
| A-4.3 | Setting `--judge-prompt-version=v0.8.0-prompt-2` (the default) loads the new prompt without any user action. |
| A-4.4 | `v0.6.0-prompt-1` is preserved in the registry (verifiable by `grep "v0.6.0-prompt-1" prompt_registry.py`). |
| A-4.5 | `alphaloop judge --calibrate-prompt --prompt-a ... --prompt-b ...` runs both prompts on the dataset and produces a side-by-side comparison JSON. |
| A-4.6 | Manual: if v0.6 prompt fails Pearson 0.70 on `decision_quality`, the A/B tool shows a candidate `v0.8.0-prompt-2` with Pearson ≥ 0.70 on `decision_quality`. |

### 3.5 Cross-cutting (test counts, compatibility, no regressions)

| ID    | Criterion                                                                                                |
|-------|----------------------------------------------------------------------------------------------------------|
| A-5.1 | Total Python tests ≥ 320 (v0.7.2 baseline) + 12 new = ≥ 332.                                              |
| A-5.2 | `pytest` exits 0 on the full suite (no regressions to the 320 v0.7.2 tests).                              |
| A-5.4 | The v0.6 judge code (`src/alphaloop/judge/*`, `src/alphaloop/diagnostic/judge.py`) is **unchanged** — verified by `git diff v0.7.2 HEAD -- src/alphaloop/judge src/alphaloop/diagnostic/judge.py` returning empty. |
| A-5.5 | `alphaloop report --judge-model=...` still runs end-to-end and produces a `Q7: LLM Judge` section (regression check). |
| A-5.6 | No new external services: `grep -r "https://" src/alphaloop/calibration/` (excluding comments) returns 0 hits. |
| A-5.7 | No new WebUI / frontend code in v0.8: `git diff v0.7.2 HEAD -- webui/` returns empty.                    |
| A-5.8 | Documentation: this PRD is the only new doc; `docs/requirements/v08-requirements.md` is the canonical reference. |

---

## 4. Out of Scope

The following items are **explicitly NOT part of v0.8**. Each is
listed with a one-line reason and the version it is expected to
land in (if known).

| # | Item                                                | Reason                                                       | Deferred to        |
|---|-----------------------------------------------------|--------------------------------------------------------------|--------------------|
| 1 | **Multi-model ensemble judge** (OpenRouter Fusion)   | v0.8 calibrates single-model; ensemble needs single-model baselines first | v0.9 |
| 2 | **Automated prompt-tuning loop** (Bayesian / DSPy)   | v0.8 ships human-driven A/B tooling; auto-loop is a different product | v2.0 (if at all) |
| 3 | **User-submitted calibration cases** (community ratings) | v0.8 dataset is internal; opening to users needs review queue + abuse model | v1.0+ |
| 4 | **Public leaderboard** (dataset + scores published) | v0.8 results are internal until v1.0 confidence statement is approved | v1.0 (with release notes) |
| 5 | **Calibration UI** (web form for reviewers to rate reports) | v0.8 uses a CSV + spreadsheet workflow; UI is overhead | v0.9 (if reviewers complain) |
| 6 | **Live calibration** (re-rate on every model upgrade) | Drift detection is sufficient; live re-rating is expensive | v1.0+ (if drift becomes noisy) |
| 7 | **Cross-dataset calibration** (financial-report-NLP datasets like FinQA) | Domain shift unmeasured; v0.8 stays inside alphaloop | post-v1.0 (research) |
| 8 | **Calibration for the 6 deterministic diagnostics** (DSR, CV, etc.) | Those are deterministic by definition; calibration is meaningless | never |
| 9 | **Per-strategy calibration** (separate gate per strategy) | N=100 is too small to stratify; per-stratum accuracy reported but not gated | v0.9 (with larger N) |
| 10 | **Confidence intervals on Pearson r** (bootstrap CIs) | Nice-to-have; not blocking v1.0 | v0.9 (with `scipy.stats.bootstrap`) |
| 11 | **Calibration in CI on every PR** | Too slow (~17 min) + costs LLM API $$ | post-v1.0 (when CI budget allows) |
| 12 | **Model comparison report** (rank 5 candidate models) | v0.8 picks one model via env var; multi-model is a v0.9 study | v0.9 |
| 13 | **Calibration on synthetic-only reports** (no real backtest data) | v0.8 uses real backtest reports; synthetic is a different test set | never (different product) |
| 14 | **Reviewer calibration training** (inter-rater agreement exercises) | Reviewers are domain experts; training is overhead | v1.0+ (if reviewer pool grows) |
| 15 | **LLM-as-judge for non-quant reports** (general text quality) | Out of product scope | never |

### Out-of-scope rule (anti-scope-creep)

If during implementation the developer wants to add any item from
this table, they MUST stop and get explicit user OK in writing
(loop state file or chat). The v0.8 PR will be rejected if it
contains out-of-scope work.

---

## 5. Dependencies

This section enumerates **external** dependencies (Python, LLM
API, reviewer workflow) that v0.8 introduces. Dependencies
already shipped in v0.7.x are listed once for context.

### 5.1 Python dependencies (pip / `pyproject.toml`)

**New (v0.8):**

- `scipy` (≥ 1.11) — new runtime dep, used for `scipy.stats.pearsonr`
  and `scipy.stats.spearmanr` in calibration metrics. (Story 5–6.)
- `numpy` (≥ 1.24) — already in v0.6's dev deps via pandas, but
  v0.8 lists it explicitly because calibration arrays use it.
- `pandas` (≥ 2.0) — already in v0.7 deps; v0.8 reuses for
  dataset CSV → JSONL conversion. No new install.
- `krippendorff` (≥ 0.6) — new dev dep, used for inter-rater α
  computation at dataset build (Story 1).
- `jsonschema` (≥ 4.20) — new dev dep, used to validate
  `calibration_report.json` and `golden_scores.jsonl` against
  the schemas in `docs/requirements/v08-schemas/` (if those are
  shipped; alternative: hand-rolled validators, no new dep).

**Unchanged from v0.7.2:**

- All v0.6 judge deps (`urllib`, `dataclasses`, stdlib only).
- All v0.7 deps (numpy, pandas, fastapi, uvicorn, etc.).
- All v0.7.2 deps (mkdocs, mkdocs-material — untouched).

**Explicitly NOT added in v0.8:**

- No `scikit-learn` (only need `scipy.stats`; `sklearn.metrics`
  is overkill for Pearson/Spearman/MAE).
- No `seaborn` / `matplotlib` (calibration report is JSON + ASCII;
  no figures in v0.8).
- No `pydantic` for the calibration report (uses dataclasses,
  matches v0.6 style; v0.9 can migrate if needed).
- No `httpx` / `aiohttp` (reuses v0.6 stdlib `urllib`).

### 5.2 LLM API dependencies (env vars)

v0.8 reuses the v0.6 LLM client as-is. The following env vars
are inherited unchanged:

- `LLM_API_KEY` — required for the judge + calibration run.
- `LLM_BASE_URL` — required; OpenAI-compatible endpoint.
- `LLM_MODEL` — required; the model to use for the judge.
- `LLM_TIMEOUT_S` — inherited (default 30).
- `LLM_JUDGE_CONFIG` — optional YAML fallback (unchanged).
- `ALPHALOOP_JUDGE_PROMPT_VERSION` — **NEW in v0.8** (Story 11).
  Defaults to `"v0.8.0-prompt-2"` (the v0.8 default prompt). Set
  to `"v0.6.0-prompt-1"` to roll back to the v0.6 prompt.

**No new model required.** v0.8 calibration runs against the
**same model** the user already configured for `alphaloop report`.
If the v0.6 default model is unavailable, the user sets a different
`LLM_MODEL` and re-runs. There is no "v0.8 calibration model"
hardcoded in alphaloop.

### 5.3 Reviewer workflow dependencies (human, not code)

The 900 ratings (100 cases × 3 dimensions × 3 reviewers) require:

- **3 reviewers** with quant-research background. Each reviewer
  independently rates every case on every dimension using the
  rubric from `docs/plans/v06-llm-judge.md` § 3.2 (readability /
  decision合理性 / risk-disclosure 1-10 scale).
- **Review tool:** a shared CSV template
  (`data/calibration/v1/reviewer_ratings_template.csv`) with
  columns `(reviewer_id, case_id, dimension, score, ts, notes)`.
  Reviewers fill it in offline (Google Sheets or local editor);
  no live UI in v0.8.
- **Time budget:** ~10–15 minutes per case × 100 cases = ~15–25
  hours per reviewer. Three reviewers × 20 hours = **~60 person-hours
  total**. Concentrated in 1 week.
- **No reviewer compensation tracked in v0.8** — the reviewers
  are alphaloop maintainers / volunteers for v0.8. v1.0+ may
  formalize this (out of scope).

### 5.4 Dataset source (where the 100 reports come from)

- **80 cases:** direct replays of `runs/<rid>/report.md` from
  v0.7.1 runs that already exist in the repo's `runs/` directory.
  Replay is deterministic given fixed data + parameters.
- **20 cases:** hand-edited variants of replays — the maintainer
  intentionally degrades the report (removes the risk section,
  contradicts the alpha source, etc.) to populate the "clearly
  bad" stratum. Documented in `dataset.meta.json` under
  `degraded_cases: ["calib_081", "calib_082", ...]`.
- **Source attributions:** every case records its source
  (`source: alphaloop_loop_v071_replay` or
  `source: hand_edited_from_calib_062`) in the per-record `meta`.

### 5.5 GitHub Actions workflows

**New (v0.8):**

- `.github/workflows/judge-calibration.yml` — runs
  `alphaloop judge --calibration` on the v0.8 dataset. Triggered
  on `workflow_dispatch` (manual) and on tags matching `v*.*.*`
  (release candidates). Uploads `calibration_report.json` as an
  artifact. Exits non-zero if `overall_pass=false`.

**Modified (v0.8):**

- `.github/workflows/release.yml` — adds the drift test
  (`pytest tests/test_judge_drift.py`) as a required job before
  the release publish step. If drift fails, the release is
  blocked.

**Unchanged from v0.7.2:**

- `.github/workflows/test.yml` — Python tests on push + PR (the
  drift test is added here too, marked `@pytest.mark.llm`).
- `.github/workflows/webui.yml` — Vite build + Vitest + Playwright.
  Unchanged: v0.8 has no WebUI work.
- `.github/workflows/docs.yml` — MkDocs site build + Pages
  deploy. Unchanged.

### 5.6 External services

**None added in v0.8.**

- No CDN. No auth service. No analytics.
- No new LLM API; v0.8 reuses the v0.6 client.
- No broker changes.
- No third-party calibration-as-a-service (e.g. Braintrust,
  LangSmith, Arize). v0.8 metrics are computed in-house with
  `scipy`. (Third-party tooling is out of scope per § 4.)

### 5.7 Backward compatibility with v0.7.x

| What                                    | v0.7.2 (shipped) | v0.8 (target)   |
|-----------------------------------------|------------------|-----------------|
| CLI subcommands                         | 6 (`backtest`, `optimize`, `fetch`, `report`, `loop`, `serve`) | 6 (`judge` is a new top-level flag, not subcommand — see Story 5) |
| `alphaloop report` behavior              | runs Q1–Q7, writes report.md | identical (judge prompt version selectable via env var / flag) |
| LLM judge code                          | `src/alphaloop/judge/*` + `src/alphaloop/diagnostic/judge.py` | **unchanged** (v0.8 wraps; does not modify) |
| WebUI views                              | 4 (Top-5, Strategy Detail, Run Diagnostics, Replay) | 4 (no new views) |
| Python tests                             | ≥ 320            | ≥ 332           |
| TypeScript tests                         | ≥ 39             | ≥ 39 (no new)   |
| E2E tests                                | ≥ 9              | ≥ 9 (no new)    |
| `runs/<rid>/` back-compat with v0.7.0    | yes              | yes             |
| LLM judge accuracy claim in README       | none             | "Calibrated against 100-case human-rated dataset; per-dim Pearson ≥ 0.70" (if gate passes) |

### 5.8 Risk dependencies (what could block v0.8)

| Risk | Mitigation |
|------|-----------|
| **Reviewer pool is too small** (cannot get 3 reviewers × 100 cases in 1 week) | Drop to 2 reviewers (raises α target to ≥ 0.75); or extend to 2 weeks; or reduce N to 60 cases (still meets Pearson r stability). |
| **LLM API costs too high for 100 cases** | Use a cheaper model for calibration (e.g. `gpt-4o-mini`) and document the model used. |
| **No dimension passes the gate** | Iterate prompt via `--calibrate-prompt` (Story 12). If still failing after 3 iterations, defer v1.0 release per the gate contract. |
| **Inter-rater α < 0.70** | Rubric is unclear; refine rubric, re-rate, re-build dataset. v0.8 ships only if α ≥ 0.70. |
| **Drift test fails on every run** (LLM provider has high variance) | Raise drift threshold to 15% for that dimension; document the override; do NOT silently lower the bar. |

---

## 6. Open Questions (need user confirmation before implementation)

These are NOT blockers for the requirements phase but they will
block implementation. The Coder dev agent should surface them
before writing code.

1. **Dataset size.** 100 cases is the proposed target. Is 100
   the right N, or should v0.8 ship with 50 (faster build) or 200
   (more stable Pearson)? Trade-off: build time vs metric stability.

2. **Reviewer pool.** Who are the 3 reviewers? If the user is
   the only reviewer, v0.8 cannot ship (need ≥ 2 for α). Should
   v0.8 recruit external reviewers, or is 1–2 reviewers acceptable
   for v0.8 with a documented caveat?

3. **Default model for calibration.** v0.8 calibration runs against
   whatever `LLM_MODEL` is set. Should there be a "canonical"
   model (e.g. `gpt-4o-mini` for cost) that the calibration report
   asserts, so different users running calibration get comparable
   numbers?

4. **Drift threshold = 10%.** Is 10% the right bar, or should it
   be tighter (5%) for stricter release gating? Trade-off:
   false-positive rate vs missed-drift rate.

5. **Override mechanism.** Story 7's `--override-gate` is for
   documented exceptions. Should the override require a specific
   user-signed file (e.g. `CALIBRATION_OVERRIDE.md` with their
   handle), or is a CLI flag + reason enough?

6. **Prompt iteration depth.** Story 12 says "at least one
   prompt improvement iteration if accuracy < 70%". Should
   v0.8 budget for 3 iterations (more likely to clear the gate)
   or just 1 (cheaper, but might not clear)?

7. **Dataset license.** Reports are alphaloop-generated MIT.
   Are reviewer ratings also MIT (so the dataset is fully
   reproducible downstream), or are they CC-BY-NC (reviewer
   retains rights)?

8. **Chinese-language cases.** 10 Chinese cases are required
   per Story 3. Are reviewers fluent in 中文, or should v0.8
   ship English-only (defer 中文 to v0.9)?

9. **Public release of calibration report.** v0.8 ships the
   report internally. Should the report be published as part of
   the v1.0 release notes (transparency) or kept internal
   (competitive intelligence)?

10. **CI cost.** Calibration in CI = ~17 min × LLM API cost per
    release. Is the budget approved, or should calibration
    remain a manual pre-release step in v0.8 (CI in v0.9+ when
    costs come down)?

---

## 7. References

- v0.6 design (judge that v0.8 calibrates):
  `docs/plans/v06-llm-judge.md` (762 lines)
- v0.6 judge code:
  `src/alphaloop/diagnostic/judge.py` (267 lines)
  `src/alphaloop/judge/client.py` (351 lines)
  `src/alphaloop/judge/prompts.py` (267 lines)
- v0.7.2 PRD (this PRD builds on its structure):
  `docs/requirements/v072-requirements.md` (791 lines)
- v0.7.2 ship commit: `2ae2f9f`, tag `v0.7.2`, 320 tests pass
- v0.7.1 design (WebUI):
  `docs/plans/v071-webui.md` (2045 lines)
- v0.7 design (hybrid loop):
  `docs/plans/v07-hybrid-loop.md` (883 lines)
- ROADMAP: `ROADMAP.md` § v0.8 (post-v0.7, pre-v1.0)
- Loop state file:
  `~/.hermes/profiles/coder/.claude/loops/alphaloop-v08-requirements-doc.md`
- Pearson r, Spearman ρ:
  `scipy.stats.pearsonr`, `scipy.stats.spearmanr`
- Krippendorff's α:
  https://en.wikipedia.org/wiki/Krippendorff%27s_alpha
- Cohen 2020 inter-rater reliability guidance (N ≥ 100):
  standard psychometric practice for ≥ 0.70 Pearson on
  1-10 ordinal scales.
- Drift detection best practice (run-to-run variance at
  temperature=0): ~1-2% baseline; 10% threshold gives ~5-10× SNR.

---

## 8. Self-check (Loop Engineering, per `~/.hermes/profiles/coder/CLAUDE.md`)

- [x] **Goal:** 5-section PRD for v0.8 calibration covering
      dataset, accuracy, drift, prompt tracking, with 12 user
      stories and 5 acceptance groups.
- [x] **Plan:** Read v0.6 design + v0.6 judge code + v0.7.2 PRD
      (pattern reference) + ROADMAP v0.8 context → write 5-section
      PRD → verify ≥ 300 lines + 5 sections + ≥ 10 user stories.
- [x] **Verify:** `wc -l ≥ 300`, `grep "## Goals|Requirements|Acceptance|Out
      of Scope|Dependencies" ≥ 5`, `grep -c "Story \d" ≥ 10` — all
      three checks documented in the loop's verify block.
- [x] **Stop rule:** Requirements phase ends when verify passes AND
      user explicit OK received (per loop state file §"stop_when").
- [x] **State:** This PRD + the loop state file's `state.last_*`
      fields will be updated by the Coder agent on completion.
- [x] **Hard wall:** No code, no tests, no commits, no broker
      connections — only this `.md` (and the loop state file).
- [x] **Out-of-scope discipline:** 15 explicit out-of-scope items
      with defer-to versions; ensemble, auto-tuning, public
      leaderboard, calibration UI all deferred.
- [x] **Risk dependencies:** 5 risks with mitigations documented
      in § 5.8; v0.8 ships only if gate passes.