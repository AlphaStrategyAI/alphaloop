---
title: "alphaloop — static UI mockups"
status: "design"
date: "2026-08-24"
---

# alphaloop Web console — static UI mockups

High-fidelity static mockups for the four screens that carry alphaloop's core
experience, derived from
[`docs/requirements/product-positioning-requirements.md`](../../requirements/product-positioning-requirements.md).

These files are **design artifacts only**. Nothing here is wired to the Job
API, no requirements document was changed, and no trading surface exists.

## Opening them

Open [`00-overview.html`](00-overview.html) in any browser directly from disk. There is no
build step, no bundler, and no network dependency — one shared stylesheet
(`assets/mockups.css`) and plain HTML. The rail navigation in every screen links
to the other three, so the whole set is walkable from any starting point.

The screens are drawn at a fixed **1440px** width, so view them in a window at
least that wide. Fonts fall back through `Inter → system sans` and
`JetBrains Mono → system mono`; if neither is installed the layout is unchanged
but the type will be less tight.

## The four screens

| File | Screen | What it has to prove |
| --- | --- | --- |
| [`01-morning-home.html`](01-morning-home.html) | Morning Home — `FOUND` | §4.3: the five-minute scan |
| [`02-new-research-preflight.html`](02-new-research-preflight.html) | New Research / Preflight | §4.1: submit in one minute before bed |
| [`03-run-progress.html`](03-run-progress.html) | Run Progress — `running` / `NONE` | §4.2 and §5.3: durable overnight execution |
| [`04-result-detail.html`](04-result-detail.html) | Result Detail and `.asb` handoff | §7 and §8: evidence inspection and export |

### 01 · Morning Home

Leads with a single conclusion in display type, immediately followed by
`Primary evidence` and `Stop reason` — the three things §3.4 requires a user to
find in five minutes. Below that, in order: qualifying candidates with their
metrics, fold Sharpes and the six passing gates; the candidate elimination
funnel with dominant failure reasons; the methodological revisions the loop
made overnight, with the reminder that all of them entered multiple-testing
accounting (`DSR N = 60`, not the 48 planned); and the hypotheses queued for
human review.

The rail carries the other overnight runs, each reduced to one coloured dot, so
`NO_EVIDENCE` and `INCONCLUSIVE` runs are visible without competing with
tonight's conclusion.

### 02 · New Research / Preflight

A three-beat flow — hypothesis and market, preflight and protocol preview,
freeze and submit — laid out as three columns so the whole submission is
reviewable without scrolling past the freeze action, which sits in a sticky
action bar.

Covers hypothesis statement and economic logic, the signal mechanism from the
constrained DSL, the two first-release market profiles as selectable tiles with
their calendar, benchmark, cost and survivorship rules, a content-addressed
dataset snapshot, the six predeclared hard gates, seven preflight checks
(six pass, one warning that foreshadows a method revision), the compute, time
and disk budgets as meters, the frozen method grid behind
`planned_n_trials = 48`, and the `research-spec.yaml` that gets frozen.

The host-must-stay-awake constraint is disclosed verbatim as an amber callout
with an explicit acknowledgement, next to a panel stating exactly what freeze
returns: a `run_id` immediately, job status `queued → running`, and outcome
`NONE` until evidence is sealed.

### 03 · Run Progress

The hero states `RUNNING` and, in the same breath, that the outcome is `NONE`
and both `Primary evidence` and `Stop reason` read
`(running or not yet terminal)`. Job status is visibly not a conclusion.

Liveness is the point of the right-hand column: supervisor pid, worker count,
heartbeat age, the latest complete checkpoint, and recovery attempts, with the
note that closing the tab does not stop the job but suspending the host does.

Progress uses one tick per planned trial rather than a percentage bar, so the
pass / fail / incomplete texture of the search is legible at a glance. Budgets
burn down; the funnel shows `DSR` and `Qualified` as hatched *pending* rows
because DSR is evaluated once against the final unique-trial count; the trial
ledger shows recent lines and a gross in-sample Sharpe strip. A locked note
states that the console cannot override an evidence gate, and a
"what cannot happen tonight" panel enumerates the safety walls.

### 04 · Result Detail

Deep inspection of one qualifying candidate. `walk_forward` is expanded with
its six purged fold Sharpes, half-sample split, CPCV paths and nested holdout,
plus the full raw gate line. The other five gates are collapsed rows carrying
their own detail. Then the append-only trial ledger (8 of 60 lines, mixed
outcomes) and the run artifact tree.

The handoff column shows the `.asb` layout, `bundle_id`, content hash, unset
`registry_uri`, and an explicit "no executable files" line, with the manual
export action and its receipt — including the disclaimer that an export claims
nothing about future profitability. Queued hypotheses sit underneath, marked
`never auto-executed`.

## Visual system

The direction is a quantitative-research instrument, not an ops console: dark,
calm, and low-chroma, with colour reserved almost entirely for verdicts.

### Surface

- Base ramp `#05070B → #080B11`. Near-black blues, never neutral grey.
- Three wide, low-opacity radial light sources plus a 96px hairline grid,
  masked toward the top. This gives depth without gauges or panel borders
  fighting for attention.
- Panels are 2.6% white glass with a 7% hairline border, an 18px backdrop blur,
  an inset top highlight and a deep soft drop shadow. Radius 18px for panels,
  14px for cards, 9px for controls.
- The 1440px frame is a real app shell: sticky 248px rail, sticky 58px top bar,
  and a scrolling canvas. The first **900px** are treated as the designed fold —
  conclusion and evidence above it, "what next" below — and a near-invisible
  hairline marks it.

### Colour

One accent hue is bound per screen through `--accent` on `<body>`, so a single
class switches the whole surface between verdict states.

| Token | Hex | Meaning |
| --- | --- | --- |
| `FOUND` | `#4ADE9B` emerald | Every predeclared hard gate passed. Never a promise of alpha. |
| `INCONCLUSIVE` | `#F5B544` amber | Evidence set incomplete: data, budget, diagnostics, or technical failure. |
| `NO_EVIDENCE` | `#E0798F` muted rose | A required gate failed. Not proof that alpha is absent. |
| `running` / `NONE` | `#7EB8FF` blue | In flight. Pulsing, never green. |

Ink ramp: `#E9EDF5` primary, `#A7B2C7` secondary, `#6E7A92` tertiary,
`#4C566B` quaternary. Everything that is not a verdict or a state badge is ink
and hairline.

**Deliberate divergence:** the packaged console today locks `FOUND #3EE0A0`,
`NO_EVIDENCE #FFB020` (amber) and `INCONCLUSIVE #C4A0FF` (violet). These
mockups instead map amber to `INCONCLUSIVE` and rose to `NO_EVIDENCE`, so that
"a gate failed" reads as a negative result and "we could not judge" reads as a
caution. This is a proposal, not an accident — reconciling it is a decision for
whoever implements the screens.

### Type

- **Inter** for everything human, **JetBrains Mono** with tabular figures for
  everything machine-generated: `run_id`, `spec_id`, `trial_id`, hashes,
  parameters, metrics, and raw gate lines. If a value comes out of an artifact,
  it is monospaced.
- Verdicts are Inter 300 at 74–82px with −0.05em tracking and a
  white→accent gradient text fill. Nothing else on any screen is above 19px.
- UI text is 10–13px. Micro-labels are 9.5–10px uppercase at 0.13–0.20em
  tracking in tertiary ink.

### Components

`assets/mockups.css` is organised in numbered sections. The reusable pieces:

- **Verdict hero** (`.verdict`) — display conclusion, gloss, and a
  label/value lead stack, with a bordered identity column beside it.
- **Elimination funnel** (`.funnel`) — one row per stage with a label, a
  proportional bar and a count; the final row takes the accent, and pending
  stages are hatched.
- **Dominant failure reasons** (`.reasons`) — hairline-thin rose bars, ranked.
- **Fold chart** (`.folds`) — signed bars around a zero line, for per-fold
  Sharpe.
- **Search ticks** (`.ticks`) — one segment per planned trial, coloured
  pass / fail / incomplete, with the active trial breathing.
- **Sparkline strip** (`.bars`) — dense gross-metric bars, eliminated trials
  deliberately desaturated.
- **Gate tokens** (`.gtok`) and **badges** (`.badge`) — pass / fail / warn /
  pending states.
- **Meters** (`.meters`) — budget burn-down with a caption explaining the
  consequence of exhaustion.
- **Checks** (`.checks`) — preflight results and prohibition lists.
- **Stepper** (`.stepper`), **sticky action bar** (`.actionbar`), **profile
  tiles** (`.tile`), **gate picks** (`.pick`), **queue rows** (`.qrow`),
  **artifact trees** (`.tree`), and **notes** (`.note`) in lock, awake and
  accent variants.

### Language

UI copy is English and follows the product vocabulary exactly — `FOUND`,
`NO_EVIDENCE`, `INCONCLUSIVE`, `run_id`, `spec_id`, `preflight`,
`planned_n_trials`, `walk_forward`, `dsr`, `.asb`. Section titles carry a
short Chinese gloss (早间复盘, 淘汰漏斗, 方法修正, 睡前提交, 待人工审阅) where it
reads naturally for a Chinese-speaking researcher; the machine vocabulary is
never translated.

Every screen carries at least one honest-limits statement, because the product
promise is trustworthiness rather than profit: FOUND is not a promise of alpha,
job status is not a conclusion, the console cannot override a gate, and export
authorizes nothing.

## Sample data

All values are fabricated but internally consistent. One narrative run threads
all four screens:

```text
run_id       j_20260823T234118Z_a1b2c3d4
spec_id      rs_8c4f2e1a9b0d7f6e5a4c3b2a1f0e9d8c
dataset      ds_spx100_2005_2026 · sha256 03796e74…bc66bc55
profile      us-equity-daily · SPY · NYSE · 5.0 bps · seed 7
hypothesis   12-1 momentum, net of cost, out of sample, US large caps
23:41        frozen, run_id returned          -> screen 02
03:12        trial 26 of 48, ckpt_0007        -> screen 03
05:58        evidence sealed, FOUND, 60 trials-> screens 01 and 04
```

The funnel reconciles: 60 generated, 2 incomplete, 58 with a complete evidence
set, of which 21 fail net-of-cost, 21 fail walk-forward OOS, 7 fail regime
stability, 5 fail DSR and 2 fail PBO, leaving 2 qualifying candidates. The
`n_trials = 60` against `planned_n_trials = 48` is the visible consequence of
the four method revisions, and it is the DSR `N`.

## Not in scope

- No backend, Job API, or React implementation — static HTML only.
- No team identity, permissions, or approval UI; one local user.
- No trading, broker, paper, or promotion surface. Export is the boundary.
- No changes to any requirements document; this folder is additive.
