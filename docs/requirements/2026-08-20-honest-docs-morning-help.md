---
title: "Honest published docs, in-console help, and five-minute gate evidence"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
---

# Honest published docs, in-console help, and five-minute gate evidence

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Published MkDocs home and CLI help copy, packaged morning
help, and rendering of already-sealed hard-gate `detail` on the morning
page and in `report.md`. Not a new product category. Not CPCV / PBO.
Not a trading UI.

## 1. Why this cycle exists

The product promise in
`docs/requirements/product-positioning-requirements.md` is:

> Submit in one minute before bed; run reliably overnight; understand a
> trustworthy conclusion in five minutes the next morning.

PRD §1 and §3.1 forbid promising alpha. PRD §4.3 requires the morning
home page to present supporting evidence, not only a verdict. PRD §5
names the local Job API + packaged static Web as the architecture.
Nielsen's **help and documentation** heuristic requires concise,
task-focused help in the product, not only in a distant site
([NN/g, 10 usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)).
Bailey and López de Prado require the reader to see **what was tried**
and the **out-of-sample evidence**, not only a pass token
([Bailey & López de Prado, "The Deflated Sharpe Ratio," *Journal of
Portfolio Management*, 2014](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)).

The five-minute morning review cycle aligned README, ROADMAP, package
description, and `docs/webui.md`. Three first-release honesty gaps
remain:

| Surface | Gap vs PRD / scientific reporting |
| --- | --- |
| Published MkDocs home (`docs/index.md`) | Still sells a hybrid DAG that "reports alpha strategies" and `alphaloop loop "find alpha with DSR > 1.0"`. GitHub Pages deploys this file. README already tells the overnight-lab story; the site does not. |
| Morning evidence | `gates.json` already stores `regime_stable`, half Sharpes, `oos_sharpe_median`, `returns_scope`, and DSR fields. The page and `report.md` still render `name: pass\|fail` only. A five-minute reader cannot see *why* walk-forward passed or failed. |
| In-console help | The packaged page has no help. A user who lands on the console without README cannot tell job **status** from research **outcome**, or that host sleep stops the worker. |

This cycle closes those gaps. It does not reopen product locks (local
workers, constrained DSL, no alpha promise, frozen `alphaloop.live`,
no `FakeWorker` in morning e2e). It does not start CPCV, nested
holdout, or new DSL kinds.

## 2. Best-practice basis

### 2.1 Docs must match the product the user can run

Nielsen's **match between the system and the real world** and
**consistency and standards** apply to the published site, not only the
UI. A homepage that still says the loop finds alpha trains the user to
expect a trading bot. The MkDocs home MUST match README and the PRD.

### 2.2 Help belongs in the product, short and task-focused

Nielsen's tenth heuristic: users rarely read a full manual before
trying the product. Help MUST be on the morning page, concise, and
about the overnight-lab tasks (submit, leave the host awake, read
`FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`). It MUST NOT invent `FOUND`.

### 2.3 Five-minute evidence must show the sealed numbers

A pass/fail chip hides the walk-forward contract that already exists:
mean fold Sharpe, chronological half Sharpes, median fold Sharpe when
`n_folds >= 3`, and `returns_scope`. CONSORT-style reporting states the
pre-specified measurement before the verdict. The morning page and
`report.md` MUST print those sealed `detail` keys when present. They
MUST NOT compute new statistics at review time.

### 2.4 Architecture docs that claim unfinished work destroy trust

`docs/plans/2026-08-19-overnight-lab-remaining-work.md` still describes
Phases 8–11 as unfinished (synthetic prices, no YAML submit, DSR on
buy-and-hold returns). Those phases shipped. A reader of the
architecture tree MUST be told the document is historical, not a
current gap list.

## 3. In-scope requirements

### R1. Shared gate-line formatter

A pure function `format_gate_line(row: Mapping[str, Any]) -> str` MUST
live in `src/alphaloop/runtime/artifacts_io.py`.

Given a `gates.json` result row, it MUST return:

```text
{name}: {pass|fail}
```

and, when the corresponding key is present in `row["detail"]`, append
each of these keys in this order, separated by ` · `:

1. `returns_scope`
2. `n_trials`
3. `dsr`
4. `oos_sharpe_mean`
5. `oos_sharpe_median`
6. `first_half_sharpe`
7. `second_half_sharpe`
8. `regime_stable`

Booleans format as `true` / `false`. Floats use six significant digits
(`format(value, ".6g")`). Integers use `str`. Missing keys are omitted.
Unknown extra detail keys are omitted. Empty detail yields only
`{name}: {pass|fail}`.

The formatter MUST NOT invent values. It MUST NOT treat a missing
`detail` as a failed gate.

### R2. Morning payload includes `evidence_lines`

`morning_view` MUST include `evidence_lines`: a list of strings, one
`format_gate_line` per `evidence["results"]` dict row, in file order.
When evidence is missing or has no results, `evidence_lines` is `[]`.

Existing keys stay.

### R3. Packaged page renders `evidence_lines` and in-console help

The evidence list MUST render `job.evidence_lines` when that array is
non-empty. It MUST NOT invent `FOUND`. It MUST NOT offer a gate
override.

The packaged HTML MUST include a `#help` section, always visible on the
home page (not behind a modal), with these locked sentences, verbatim:

- `#help-no-alpha`: `This console does not claim alpha or future profitability.`
- `#help-status`: `Job status (queued, running, completed, failed, cancelled) is not the research conclusion.`
- `#help-host`: the existing `HOST_CONSTRAINT` string from
  `alphaloop.runtime.preflight` (verbatim).
- `#help-found`: `FOUND means every required hard gate is present and passed. It is not a promise of alpha.`

### R4. `report.md` uses the same formatter

`write_report` `## Gates` lines MUST be `format_gate_line` output, not
`name: pass|fail` alone. Replay still must not re-run gates.

### R5. Published MkDocs home matches the overnight lab

Rewrite `docs/index.md` so the lead is the local-first overnight lab
promise from README. It MUST:

- state `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`;
- state that alphaloop does not promise alpha;
- tell the user to run `alphaloop start` and open the packaged morning
  page;
- keep a short pointer that `alphaloop loop` is heritage v0.7 DAG, not
  the first-release overnight path.

It MUST NOT use `find alpha with DSR > 1.0` as a product example. It
MUST NOT describe the Vite Quant Lab SPA as the product UI.

### R6. CLI help and `docs/cli.md` put the overnight lab first

- `alphaloop --help` description stays overnight-lab (already true).
- The `loop` subparser help MUST say it is heritage v0.7 hybrid DAG,
  not the overnight lab. The `goal` example MUST NOT be
  `find alpha with DSR > 1.0`.
- `docs/cli.md` lead MUST describe `start` / `submit` / `status` /
  `cancel` / `resume` as the overnight-lab commands. The `loop`
  section MUST be marked heritage.

### R7. Remaining-work plan is labeled historical

At the top of
`docs/plans/2026-08-19-overnight-lab-remaining-work.md`, add a short
status note: Phases 8–11 shipped; §1 is not a current gap list.
Do not rewrite the historical design body.

Register this requirements document and its plan in `mkdocs.yml` nav.

## 4. Out of scope

- CPCV, PBO, nested train/validate/test, correlation-adjusted
  \(N_{\mathrm{eff}}\).
- New DSL kinds or method-grid expansions.
- Protocol preview-and-freeze UX (PRD §4.1 step 4).
- Rewriting the entire heritage `docs-site/` tree (not what GitHub
  Pages deploys). A one-line banner there is allowed.
- Unfreezing `alphaloop.live` or the Vite SPA.
- Promising or synthesizing `FOUND`.
- Using `FakeWorker` in morning e2e.
- Changing locked `HOST_CONSTRAINT` text.
- Cloud Agent environment builds.

## 5. Acceptance

- Unit: `format_gate_line` order and formatting; `morning_view`
  exposes `evidence_lines`; `write_report` contains a walk-forward
  detail key when present in `gates.json`; packaged HTML has the four
  help ids and locked sentences; `docs/index.md` does not contain
  `find alpha with DSR`; `loop --help` does not contain that phrase.
- Integration: Job API get includes `evidence_lines`; daemon still
  serves `#help` in `/`.
- E2E: real Chromium + real daemon; help sentences visible without
  opening a job; after a `walk_forward` job completes, job detail
  evidence text includes `regime_stable=`. Legal outcomes only. No
  gate override.

## 6. Exit condition for the improvement loop

After this cycle, remaining PRD items are soak (release process),
protocol preview (later), CPCV-scale validation, optional MCP/cloud
workers, or excluded live trading. If no further first-release-sized
gap remains without reopening those locks, stop the loop.
