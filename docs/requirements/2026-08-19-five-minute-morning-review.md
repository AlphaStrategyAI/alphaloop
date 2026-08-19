---
title: "Five-minute morning review — first-release requirements"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-19"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
---

# Five-minute morning review

**Date:** 2026-08-19
**Status:** Approved for this implementation cycle
**Scope:** Morning Job API payload, packaged Web console, `report.md`,
and first-release docs that still contradict the overnight-lab
positioning. Not a new product category. Not a trading UI.

## 1. Why this cycle exists

The product promise in
`docs/requirements/product-positioning-requirements.md` is:

> Submit in one minute before bed; run reliably overnight; understand a
> trustworthy conclusion in five minutes the next morning.

PRD §3.4 names that five-minute review as a first-release success
criterion. PRD §4.3 names the morning home page: lead with one of
`FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`, then evidence, funnel,
revisions, and queued hypotheses. PRD §1 and §3.1 forbid promising
alpha.

The current code already computes a legal research outcome and serves a
packaged morning page. The page and `report.md` are still too thin for a
trustworthy five-minute review:

| Surface | Gap vs PRD / scientific reporting |
| --- | --- |
| Job list | Shows `run_id — research_outcome` only. Job **status** and research **outcome** collapse into one token, which §4.3 and Nielsen's "visibility of system status" require to stay distinct (`queued` + `NONE` is not `FOUND`). |
| Job detail | Omits the frozen hypothesis **statement**, `spec_id`, `seed`, and `n_trials`. `morning_view` already has `hypothesis` and `spec_id`; the page never renders them. `seed` and `n_trials` are not in the payload. |
| `report.md` | Stub: outcome, stop reason, `name: pass\|fail`. No hypothesis, no trial count, no locked "does not claim alpha" line. |
| `ROADMAP.md` | Still sells a v0.5 rename, `alphaloop loop "find a strategy…"`, and "the loop finds alpha." That contradicts README and the PRD. |
| `docs/webui.md` | Describes the frozen Vite+FastAPI Quant Lab SPA as the product UI. First-release UI is the packaged static morning page. |

This cycle closes those gaps. It does not reopen product locks (local
workers, constrained DSL, no alpha promise, frozen `alphaloop.live`,
no `FakeWorker` in morning e2e).

## 2. Best-practice basis

These requirements are not invented copy. They follow established
reporting and HCI practice that already matches the PRD's trust model.

### 2.1 Separate job status from research conclusion

Nielsen's first usability heuristic is **visibility of system status**:
the interface must show what the system is doing now, in the user's
language, without forcing inference ([Nielsen, *Usability Engineering*,
1993; NN/g 10 heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)).
A row that only says `NONE` or `FOUND` hides whether the worker is
still running. PRD §4.3 already splits **job status** from
**research outcome**. The list and detail must show both.

### 2.2 Show the frozen hypothesis, not only the verdict

Pre-registered science reports the hypothesis that was tested, not only
the p-value. The CONSORT / ICMJE tradition is: state the pre-specified
question before the result. Bailey and López de Prado's Deflated Sharpe
Ratio work makes the same demand for strategy search: the reader must
see **what was tried** and **how many times** before trusting a
surviving Sharpe ([Bailey & López de Prado, "The Deflated Sharpe Ratio:
Correcting for Selection Bias, Backtest Overfitting and the p-Hacking of
Investment Strategies," *Journal of Portfolio Management*, 2014](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)).

alphaloop already passes unique-ledger `n_trials` into DSR. The morning
page and `report.md` must disclose that count, plus `spec_id` and
`seed`, so a five-minute reader can tell a sealed, reproducible
conclusion from a running or incomplete job.

### 2.3 Do not claim alpha in the artifact a human files away

Tufte's rule for analytical graphics is: the display must not imply a
causal or predictive claim the evidence does not support (*The Visual
Display of Quantitative Information*). The PRD already forbids promising
alpha. `report.md` is the artifact a user may archive or paste into
notes. It must contain one locked English sentence that the product does
not claim alpha or future profitability. The page legend must keep
`NO_EVIDENCE` and `INCONCLUSIVE` visually distinct from `FOUND` so a
skimming reader does not treat every green token as a win.

### 2.4 Docs that sell a different product destroy trust

Nielsen's "match between system and the real world" and "consistency
and standards" apply to README-adjacent docs as well as the UI. A
roadmap that still says the loop finds alpha, or a WebUI guide that
still describes a frozen SPA, trains the user to expect the wrong
product. First-release docs that users actually open (`ROADMAP.md`,
`docs/webui.md`, package `description`, MkDocs `site_description`)
must match the overnight-lab positioning.

## 3. In-scope requirements

### R1. Morning payload discloses review fields

`morning_view(job, data_dir)` MUST include, in addition to today's
keys:

- `seed`: `job.spec.seed` (int)
- `n_trials`: number of **unique** `trial_id` values in
  `trial-ledger.jsonl` for that run (int, `0` if the ledger is missing
  or empty). Duplicate `trial_id`s count once, matching protocol
  accounting.

Existing keys stay: `run_id`, `status`, `research_outcome`, `spec_id`,
`error`, `recovery_attempts`, `hypothesis`, `evidence`, `funnel`,
`revisions`, `queued_hypotheses`, `stop_reason`.

Job API list and get continue to return `morning_view` unchanged in
shape except for the two new keys.

### R2. Job list shows status and outcome

The packaged morning list button text MUST be:

```text
{run_id} — {status} — {research_outcome}
```

Exact separator: space-em-dash-space (` — `). `status` is the job
status enum value (`queued`, `running`, `completed`, `failed`,
`cancelled`). `research_outcome` remains the uppercase research enum
(`FOUND`, `NO_EVIDENCE`, `INCONCLUSIVE`, `NONE`).

E2E parsers MUST take the **last** ` — `-separated segment as the
research outcome.

### R3. Job detail shows hypothesis and reproducibility fields

When the user opens a job, the detail pane MUST show:

1. Research outcome (existing `#outcome`, still the visual lead).
2. Job status as distinct text (`Job status: {status}`).
3. Frozen hypothesis **statement** (`job.hypothesis.statement`).
4. `spec_id`, `seed`, and `n_trials` on one meta line.
5. Existing stop reason, evidence, funnel, revisions, queued
   hypotheses.

The page MUST NOT invent `FOUND`. It MUST NOT offer a gate override.

### R4. Outcome colors are distinct

`FOUND`, `NO_EVIDENCE`, `INCONCLUSIVE`, and `NONE` MUST use distinct
foreground colors on `#outcome` and in the header legend. `FOUND` stays
the existing accent green. The other three MUST NOT share that green.

### R5. `report.md` is a five-minute paper artifact

`write_report` MUST include:

1. Header `# Research conclusion`
2. Locked sentence, verbatim:

   `This report does not claim alpha or future profitability.`

3. `research_outcome`, `stop_reason` (when not `None`)
4. `spec_id`, `seed`, `n_trials` when a `ResearchSpec` is provided
5. Frozen hypothesis fields when a spec is provided (`statement`,
   `economic_logic`, `signal_mechanism`, `market_scope`,
   `market_profile`, `benchmark`)
6. Existing `## Gates` / `name: pass|fail` lines from `gates.json`

`n_trials` in the report is the unique ledger `trial_id` count unless
the caller passes an explicit integer. The worker MUST pass the run's
`ResearchSpec`. `alphaloop replay` MUST load `research-spec.yaml` when
present and pass that spec into `write_report`. Replay still must not
re-run gates.

No LLM prose. No "target found" copy.

### R6. First-release docs match the overnight lab

- Rewrite `ROADMAP.md` so it describes the local-first overnight lab,
  current first-release surface, and honest remaining work. It MUST NOT
  claim that the loop finds alpha, MUST NOT keep `alphaloop loop "find a
  strategy that beats SPY…"` as a shipped command, and MUST NOT treat
  MCP `serve` as the first-release runtime.
- Replace the lead of `docs/webui.md` with a short pointer: the
  first-release UI is the packaged static morning page under
  `src/alphaloop/webui/static/`, served by `alphaloop start`. The
  Vite+React Quant Lab SPA under `webui/` is frozen heritage and is not
  the product UI.
- Align `pyproject.toml` `[project].description` and MkDocs
  `site_description` with the overnight-lab promise. Do not mention
  finding alpha.

## 4. Out of scope

- Soak / 95% overnight benchmark (PRD §3.4 operational metric; not CI).
- Protocol preview-and-freeze UX before submit (PRD §4.1 step 4).
- Expanding the DSL search grid or new hard gates.
- MCP as a long-running runtime.
- Unfreezing `alphaloop.live` or the Vite SPA.
- Promising or synthesizing `FOUND`.
- Using `FakeWorker` in morning e2e. Existing supervisor isolation
  tests that already use `FakeWorker` stay.
- Cloud Agent environment builds.
- Changing locked `HOST_CONSTRAINT` text.

## 5. Acceptance

- Unit: `morning_view` exposes `seed` and unique-ledger `n_trials`;
  `write_report` contains the locked no-alpha sentence, hypothesis, and
  trial count when a spec is passed; packaged HTML/JS contain the new
  detail ids and the three-part list format.
- Integration: Job API get/list include the new keys; replay rewrites
  `report.md` with spec fields without changing research outcome.
- E2E: real Chromium + real daemon; list outcome is the last ` — `
  segment; detail shows hypothesis statement and job status; legal
  outcomes only; no gate override.

## 6. Exit condition for the improvement loop

After this cycle, remaining PRD items are either release-process
(soak), explicitly later (MCP, cloud workers, protocol preview), or
excluded (live trading, unfreezing the SPA). If no further
first-release-sized gap remains without reopening those locks, stop the
loop.
