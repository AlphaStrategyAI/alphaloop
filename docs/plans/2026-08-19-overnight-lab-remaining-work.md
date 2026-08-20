---
title: "alphaloop Overnight Research Lab — Remaining Work Technical Design"
status: "design"
date: "2026-08-19"
related_requirements: "docs/requirements/product-positioning-requirements.md"
related_architecture: "docs/plans/overnight-research-lab-refactor.md"
---

> **Status (2026-08-20):** Historical design for Phases 8–11. Those
> phases shipped. Section 1 is **not** a current gap list.

# Overnight Lab Remaining Work — Technical Design

This document maps **unfinished first-release Included items** in
[`docs/requirements/product-positioning-requirements.md`](../requirements/product-positioning-requirements.md)
onto the tree after Phases 1–7 landed on `main`. It is the architectural
source of truth for Phases 8–11. Executable work lives in four
independent implementation plans under `docs/plans/`.

Phases 1–7 already delivered: contracts, local Job API + supervisor,
constrained DSL + profiles + hard-gate adapters, packaged morning
**review**, YAML-only `.asb` export, the overnight-lab Skill, and an
iterative `run_protocol` that honors `should_continue`.

They did **not** finish protocol semantics, durable artifacts, morning
submit/preflight/progress, or §12 verification.

## Product locks (do not reopen)

- Local-first overnight research lab. Not a trading bot. Promise: submit
  in one minute; run overnight; understand a trustworthy conclusion in
  five minutes. Do not promise alpha.
- Runtime: local self-hosted workers. `alphaloop start` launches control
  plane + worker + packaged static Web. Host sleep/power-off stops jobs;
  closing browser/CLI does not. Preflight discloses locked
  `HOST_CONSTRAINT`.
- Constrained DSL over engineer factors. Markets `us-equity-daily` and
  `crypto-daily` are independent. Outcomes `FOUND` / `NO_EVIDENCE` /
  `INCONCLUSIVE` are separate from job status. `FOUND` only from complete
  `GateEvidence`. `llm_judge` is not a gate.
- Handoff: human-triggered export of `FOUND` only → immutable YAML-only
  `.asb`. No Python in `.asb`. No credentials. Broker-neutral target
  weights.
- `alphaloop.protocol` must not import `alphaloop.live`,
  `alphaloop.webui`, or `alphaloop.runtime`.
- `alphaloop.live` stays frozen and importable for tests.

## 1. What is still unfinished

### 1.1 Protocol semantics (highest product impact)

`run_protocol` walks `method_parameter_grid` and passes
`strategy_fn=_strategy_fn_for(trial_doc, prices)` into walk-forward, but
computes:

```python
strategy_returns=primary_prices.pct_change().fillna(0.0)
```

DSR / vs_buy_hold / vs_benchmark / vs_random therefore ignore the grid.
Extra trials mainly inflate `n_trials`. That is not iterative research.

The production worker (`src/alphaloop/runtime/worker.py` `_run_protocol`)
does not pass `clock` or `remaining_cost_usd`. Mid-run budget stop is
test-only. Default worker does not pass `revision_proposer` (correct:
there is no in-run LLM planner; economic revisions stay queued when a
proposer is injected).

`should_continue` checks budget **before** `FOUND`. Today that is safe
only because remaining time is sampled at the start of the trial and
reused after gates. If the clock is sampled after a long trial, a
passing evidence set can be discarded as `budget_exhausted`.

### 1.2 Checkpoint, artifacts, dataset

`load_latest_complete` exists in `src/alphaloop/runtime/checkpoint.py`
and is unused by the protocol worker. Crash → full rerun. On restart,
the ledger **appends** while in-memory `n_trials` restarts at 0, and
`run_protocol` truncates `recommendations.json` to an empty list.

The overnight path writes spec, ledger, `evidence/gates.json`, empty
recommendations, and a single pre-protocol checkpoint. It does **not**
write `manifest.yaml`, `candidates.parquet`, or `report.md`.

`DatasetRef` / `require_dataset` are unused at runtime. Missing
`prices.parquet` → synthetic RNG prices. That violates fail-closed
replay.

### 1.3 Web / CLI / preflight

Packaged UI (`src/alphaloop/webui/static/`) is morning **review only**:
no submit, no preflight errors, no poll (`loadJobs()` once).

`POST /v1/jobs` already exists and returns 400 `{"errors": [...]}` on
preflight failure. The body must be a full `ResearchSpec.from_dict`
payload, including a matching `spec_id`. A user cannot type a hypothesis
in one minute without computing that hash.

Preflight checks DSL kind, hard gates, time/cost, disk — not dataset
availability. It does not require a content-addressed snapshot.

`docs/cli.md` documents top-level `alphaloop replay`; `cli/main.py` only
registers `alphaloop loop replay` (v0.7 DAG). Overnight replay should
re-emit `report.md` from sealed artifacts without re-running gates.

### 1.4 §12 verification

| Requirement | Status |
| --- | --- |
| Bundle hash/tamper | Done (Phase 5) |
| Status/outcome matrix, incomplete → not FOUND | Partial unit tests |
| Property suite for `n_trials` vs ledger | Missing |
| Overnight-path byte replay | Missing |
| LLM plan snapshot | **N/A** — first-release protocol has no LLM planner |
| Checkpoint fault injection | Missing |
| Disk-pressure suite | Preflight unit only |
| CI pytest | Missing (only `.github/workflows/docs.yml`) |
| Soak + 5-minute usability | Release process, not CI |
| AlphaStrategy consumer import tests | **Excluded** (other repo; stay excluded) |

§11 Excluded items remain correctly absent (hosted cloud, remote
workers, MCP, desktop, auto-promote, Python in `.asb`).

## 2. Decomposition

Independent subsystems, each with its own implementation plan. Each
plan must produce working, testable software on its own.

| Phase | Plan | Subsystem | Depends on |
| --- | --- | --- | --- |
| 8 | [`2026-08-19-overnight-lab-phase8-protocol-semantics.md`](2026-08-19-overnight-lab-phase8-protocol-semantics.md) | Strategy returns, FOUND-vs-budget, worker clock | Phase 7 code |
| 9 | [`2026-08-19-overnight-lab-phase9-durability-artifacts.md`](2026-08-19-overnight-lab-phase9-durability-artifacts.md) | Dataset fail-closed, checkpoint resume, manifest / parquet / report, `alphaloop replay` | Phase 8 |
| 10 | [`2026-08-19-overnight-lab-phase10-morning-submit.md`](2026-08-19-overnight-lab-phase10-morning-submit.md) | Web submit + YAML POST + progress poll; spec without `spec_id` | Phase 2/4 API (not 8) |
| 11 | [`2026-08-19-overnight-lab-phase11-verification.md`](2026-08-19-overnight-lab-phase11-verification.md) | CI pytest, matrix completeness, shortened overnight e2e, checkpoint kill/resume | Phases 8–10 |

Phase 10 does not need Phase 8 return math. Declared-dataset preflight
lives in Phase 9 with `DatasetRef`. Phase 11 must not claim overnight-path
coverage until 8 and 9 exist.

## 3. File boundaries

Do not rewrite diagnostic or engineer math. Do not revive Vite as the
overnight home page. Do not import `alphaloop.live` from protocol,
runtime, or bundle.

| Area | Keep | Change in Phases 8–11 |
| --- | --- | --- |
| `src/alphaloop/protocol/loop.py` | Grid, stop, ledger append | Lagged-weight returns; skip completed trials; ledger-based `n_trials`; do not truncate recommendations |
| `src/alphaloop/protocol/stop.py` | Forbidden reasons, economic queue | `FOUND` before budget |
| `src/alphaloop/runtime/worker.py` | Heartbeat, process spawn | Clock + cost kwargs; dataset fail-closed; checkpoint callback; no RNG prices |
| `src/alphaloop/runtime/checkpoint.py` | `load_latest_complete` | Used by worker; seq per completed trial |
| `src/alphaloop/contracts/research_spec.py` | Frozen identity | Optional `dataset: DatasetRef \| None`; omit from `spec_id` hash when `None` so existing IDs stay stable |
| `src/alphaloop/contracts/artifacts.py` | `RunLayout`, `require_dataset` | No layout change |
| `src/alphaloop/runtime/preflight.py` | HOST_CONSTRAINT | If dataset declared, require cache bytes + hash |
| `src/alphaloop/runtime/api.py` / `daemon.py` | POST `/v1/jobs` | Accept payload without `spec_id`; YAML content-type |
| `src/alphaloop/webui/static/` | Review lists | Submit form + poll; still no gate override |
| `src/alphaloop/cli/jobs.py` | start/submit/status/cancel/resume | Top-level `replay` re-emits `report.md` |
| `.github/workflows/` | docs.yml | pytest workflow `not integration` |

New files (not new packages):

- `src/alphaloop/protocol/returns.py` — lagged strategy returns (Phase 8)
- `src/alphaloop/runtime/dataset_cache.py` — snapshot cache path + load (Phase 9)
- `src/alphaloop/runtime/artifacts_io.py` — manifest, parquet, report writers (Phase 9)
- `src/alphaloop/runtime/submit.py` — `spec_from_submit_payload` (Phase 10)

Dataset bytes live in a **shared local cache**, not duplicated under
every run:

```text
<data_dir>/datasets/<dataset_id>/prices.parquet
```

`manifest.yaml` records `dataset_id` and `dataset_sha256`. Replay /
worker calls `require_dataset`. Missing or mismatched bytes →
`INCONCLUSIVE`, never synthetic prices, never `FOUND`.

## 4. Non-goals (explicit)

These remain out of Phases 8–11 and must not appear as fake CI gates:

- Official hosted cloud, remote workers, MCP adapter, desktop wrapper.
- Auto-promote, broker credentials, Python inside `.asb`.
- In-run LLM planner / `revision_proposer` default. Economic changes
  stay queued when a test injects a proposer. No LLM plan snapshot
  suite — the first-release protocol does not generate plans.
- Hypothesis.io property library (optional later). Phase 11 uses an
  explicit ledger-vs-`n_trials` accounting test instead.
- Multi-host soak (95% of 20 overnight runs on Windows/macOS/Linux).
  Documented as a **release-candidate checklist**, not a pytest.
- Human 5-minute usability study. Same: release checklist with the
  three tokens a reviewer must find (conclusion, primary evidence,
  stop reason).
- AlphaStrategy consumer repository tests.

## 5. YAGNI decisions

1. **Strategy returns** = `weights.shift(1).fillna(0.0) * asset_pct_change`.
   Do not introduce a portfolio engine, costs inside this multiply, or
   multi-name attribution. Walk-forward already uses `strategy_fn`.
2. **Cost meter**: do not invent token spend. `remaining_cost_usd` stays
   the spec value (or an explicit kwarg). Time is the only live budget
   the worker measures (`time.monotonic` elapsed vs `time_budget_s`).
3. **Morning submit**: YAML textarea + existing POST `/v1/jobs`. No
   Node, no form builder, no gate override, still loopback.
4. **`report.md`**: a view of sealed `gates.json` + outcome + stop
   reason. Not a source of truth. Not an LLM narrative.
5. **`alphaloop replay`**: re-read artifacts and rewrite `report.md`.
   Do not re-run `run_protocol`. Do not call v0.7 `LoopReplay`.

## 6. Verification mapping (PRD §12 → Phase 11)

| §12 item | Where it lands |
| --- | --- |
| Status/outcome combinations | Expand `tests/contracts/test_status.py`; keep sealed-FOUND rule |
| Incomplete evidence cannot FOUND | Existing gate + loop tests; add one worker-level assertion |
| Multiple-testing accounting | Ledger unique `trial_id` count equals `n_trials` passed into `run_hard_gates` |
| Deterministic replay | Same spec + snapshot + seed → identical `gates.json` bytes |
| LLM plan snapshot | Document N/A in Phase 11 |
| Checkpoint fault injection | Kill after checkpoint; resume skips completed trial_ids; no duplicate ledger `trial_id` |
| Disk pressure | Preflight already; one monkeypatched `shutil.disk_usage` remains enough |
| CI shortened overnight | JobAPI create + `run_worker` with fixture parquet + assert layout files |
| Soak / 5-minute study | Remaining-work §8 release checklist (not CI) |
| AlphaStrategy import | Stay excluded |

## 7. Implementation order for agents

1. Execute Phase 8 (semantics). Protocol tests must prove grid-varying
   returns and FOUND beating a zero remaining clock.
2. Execute Phase 9 (durability). Worker tests must prove no synthetic
   prices and resume without duplicate trials. Preflight must reject a
   declared missing/mismatched dataset.
3. Execute Phase 10 (morning submit). YAML POST and poll do not change
   protocol math.
4. Execute Phase 11 last. Do not enable Cloud Agent environment builds
   as part of this work.

## 8. Release checklist (not CI)

Before tagging a first-release candidate:

1. Overnight soak: print `alphaloop soak`, then on one local machine
   (host stays awake) run one `us-equity-daily` job and one
   `crypto-daily` job with real snapshot hashes.
   Record outcome tokens and whether resume after a forced `kill -9` of
   the worker recovered without duplicate `trial_id`s. Do not run this
   command as CI.
2. Five-minute review: a person who did not run the job opens the morning
   page, names the conclusion (`FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`),
   the primary failed or passed gate, and the stop reason.
3. AlphaStrategy consumer tests run in that repository against the shared
   `.asb` fixtures; they are not this repo's CI.
