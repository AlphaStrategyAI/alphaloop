# Overnight Lab Phase 3 — Research Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the LoopRunner stopgap with a constrained DSL research protocol that can seal `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE` from real hard-gate evidence.

**Architecture:** New `src/alphaloop/protocol/` interprets YAML DSL documents over `engineer` factors, evaluates two independent market profiles, applies epistemic stopping, and writes `evidence/` plus `trial-ledger.jsonl`. The Phase 2 worker calls `protocol.loop` instead of `LoopRunner`. No LLM in this phase: candidates come from the frozen spec's `signal_mechanism` as a named DSL `kind`.

**Tech Stack:** Python 3.9+, pytest, pandas/numpy (existing), PyYAML, Phase 1 contracts, Phase 2 runtime.

## Global Constraints

- `FOUND` only from complete `GateEvidence` via `evaluate_hard_gates` / `outcome_from_evidence`. `llm_judge` is not a hard gate.
- JobStatus and ResearchOutcome stay separate. Never store a LoopRunner termination letter as an outcome.
- DSL output is `effective_at -> {asset_id: target_weight}`. No orders. No `.py` in candidate documents.
- Unknown DSL `kind` is a preflight rejection, not a research outcome.
- Method repairs may continue; economic-logic / signal_mechanism / market_scope / hard-gate changes are queued, not executed.
- Negative OOS, cost failure, failed hard gate, regime instability, and expanding an already failed search do not justify more parameter search.
- `us-equity-daily` and `crypto-daily` are independent; mixed-profile ranking raises `MixedProfileError`.
- `alphaloop.protocol` must not import `alphaloop.live`, `alphaloop.webui`, or `alphaloop.runtime`.
- `alphaloop.loop` must not import `alphaloop.runtime` or `alphaloop.contracts.bundle`.
- Do not rewrite diagnostic or engineer math. Wrap them.
- Tests use synthetic prices only (no network).
- Source of truth: `docs/requirements/product-positioning-requirements.md` and `docs/plans/overnight-research-lab-refactor.md`.

## File Structure

- Create: `src/alphaloop/protocol/__init__.py`
- Create: `src/alphaloop/protocol/dsl.py`
- Create: `src/alphaloop/protocol/stop.py`
- Create: `src/alphaloop/protocol/profiles/__init__.py`
- Create: `src/alphaloop/protocol/profiles/us_equity_daily.py`
- Create: `src/alphaloop/protocol/profiles/crypto_daily.py`
- Create: `src/alphaloop/protocol/gates.py`
- Create: `src/alphaloop/protocol/loop.py`
- Modify: `src/alphaloop/contracts/gates.py` — JSON serialize/deserialize `GateEvidence`
- Modify: `src/alphaloop/runtime/store.py` — `complete_from_artifacts`
- Modify: `src/alphaloop/runtime/supervisor.py` — exit 0 reads sealed evidence
- Modify: `src/alphaloop/runtime/worker.py` — default runner is `protocol.loop`
- Modify: `src/alphaloop/runtime/preflight.py` — unknown DSL kind
- Test: `tests/protocol/`
- Modify: `tests/runtime/test_import_graph.py`
- Modify: docs pointers in design §5 Phase 3 and requirements §13

---

### Task 1: Constrained DSL interpreter

**Files:**
- Create: `src/alphaloop/protocol/__init__.py`
- Create: `src/alphaloop/protocol/dsl.py`
- Test: `tests/protocol/test_dsl.py`

**Interfaces:**
- Consumes: `alphaloop.engineer` factor functions
- Produces:
  - `DSL_SCHEMA_VERSION = "dsl.v1"`
  - `ALLOWED_KINDS` — the ten engineer factor names
  - `UnsupportedDslError(ValueError)`
  - `StrategyDocument(schema_version, kind, parameters, universe, market_profile)` frozen
  - `parse_strategy_document(payload: Mapping) -> StrategyDocument`
  - `target_weights(doc, prices: Mapping[str, pd.Series], effective_at) -> dict[str, float]`
  - Weights are non-negative, finite, and sum to 1.0 if any long else all 0.0
  - Unknown kind / wrong schema / empty universe raise `UnsupportedDslError`
  - `effective_at` missing from an asset series → that asset weight 0

- [x] **Step 1: Write failing tests** in `tests/protocol/test_dsl.py` covering parse, unknown kind, momentum_12_1 weights on a rising series, unknown kind error, empty universe error, weights sum to 1.

- [x] **Step 2: Run tests, expect FAIL** (`ModuleNotFoundError: alphaloop.protocol.dsl`)

- [x] **Step 3: Implement dsl.py** wrapping engineer functions. For each asset, call the factor on that asset's close series; take the value at `effective_at` (asof last bar ≤ timestamp); clip negatives to 0; L1-normalize.

- [x] **Step 4: Tests PASS**

- [x] **Step 5: Commit** `feat(protocol): add constrained DSL interpreter over engineer factors`

---

### Task 2: Independent market profiles

**Files:**
- Create: `src/alphaloop/protocol/profiles/__init__.py`
- Create: `src/alphaloop/protocol/profiles/us_equity_daily.py`
- Create: `src/alphaloop/protocol/profiles/crypto_daily.py`
- Test: `tests/protocol/test_profiles.py`

**Interfaces:**
- `MarketProfile(name, periods_per_year, default_benchmark, cost_bps, calendar)` frozen
- `US_EQUITY_DAILY`: name `us-equity-daily`, periods_per_year 252, default_benchmark `SPY`, cost_bps 5.0, calendar `nyse`
- `CRYPTO_DAILY`: name `crypto-daily`, periods_per_year 365, default_benchmark `BTC-USD`, cost_bps 10.0, calendar `247`
- `get_profile(name: str) -> MarketProfile` raises `ValueError` on unknown
- `assert_single_profile(docs: Sequence[StrategyDocument])` raises `MixedProfileError` if more than one `market_profile`

- [x] Tests first, then implement, then commit `feat(protocol): add independent US equity and crypto daily profiles`

---

### Task 3: Hard-gate adapters over real diagnostics

**Files:**
- Create: `src/alphaloop/protocol/gates.py`
- Modify: `src/alphaloop/contracts/gates.py` add `evidence_to_dict` / `evidence_from_dict`
- Test: `tests/protocol/test_gates.py`
- Test: `tests/contracts/test_gates.py` (round-trip dict)

**Interfaces:**
- `run_hard_gates(required, *, prices, strategy_returns, buy_hold_prices, benchmark_prices, secondary_frames, n_trials, profile, seed, strategy_fn) -> GateEvidence`
- Map: `dsr`→`deflated_sharpe`, `walk_forward`→`walk_forward_cv`, `vs_random`→`vs_random`, `vs_buy_hold`→`vs_buy_hold`, `vs_benchmark`→`vs_spy_buyhold` when profile is US else `vs_buy_hold` against `benchmark_prices`, `data_consistency`→`data_source_consistency` (if `secondary_frames` missing, result `passed=False` with detail `{"reason": "missing_secondary_source"}` — incomplete data is a failed gate, not skipped, unless the required set omits it)
- Never call `llm_judge`
- Catch diagnostic exceptions → do not include that gate (caller translates missing required gate to INCONCLUSIVE via `IncompleteEvidenceError`)
- `evidence_to_dict` / `evidence_from_dict` round-trip `GateResult.name` as strings

- [x] Tests: each adapter name present; llm_judge not invoked; US vs crypto benchmark function choice; missing secondary → data_consistency fail; dict round-trip
- [x] Commit `feat(protocol): wrap diagnostics as hard-gate evidence`

---

### Task 4: Epistemic stop and revision classifier

**Files:**
- Create: `src/alphaloop/protocol/stop.py`
- Test: `tests/protocol/test_stop.py`

**Interfaces:**
- `RevisionKind` enum: `METHOD`, `ECONOMIC`
- `classify_revision(frozen_hypothesis, frozen_hard_gates, proposed: Mapping) -> RevisionKind` — ECONOMIC if any of `economic_logic`, `signal_mechanism`, `market_scope`, `benchmark`, `hard_gates` differ; otherwise METHOD
- `StopDecision(continue_search: bool, queue_for_human: bool, reason: str)` frozen
- `should_continue(*, remaining_time_s, remaining_cost_usd, last_evidence: Optional[GateEvidence], proposed_kind: RevisionKind, stop_reason: Optional[str]) -> StopDecision`
- If `proposed_kind is ECONOMIC`: `continue_search=False`, `queue_for_human=True`, reason `economic_change_queued`
- If `stop_reason` in `{"negative_oos","failed_after_costs","hard_gate_failed","regime_unstable","expand_failed_search"}`: `continue_search=False`, `queue_for_human=False`
- If remaining_time_s <= 0 or remaining_cost_usd <= 0: `continue_search=False`, reason `budget_exhausted`
- If last_evidence complete and not all_passed and proposed_kind is METHOD with stop_reason None: still `continue_search=False`, reason `hard_gate_failed` (do not search until profitable)
- METHOD repair with incomplete evidence and budget remaining: `continue_search=True`, reason `method_repair`

- [x] Commit `feat(protocol): add epistemic stop and revision classifier`

---

### Task 5: Protocol loop, trial ledger, evidence artifacts

**Files:**
- Create: `src/alphaloop/protocol/loop.py`
- Test: `tests/protocol/test_loop.py`

**Interfaces:**
- `ProtocolResult(job_status: JobStatus, research_outcome: ResearchOutcome, candidate_id: Optional[str], evidence: Optional[GateEvidence])`
- `run_protocol(spec, layout, *, prices, buy_hold_prices, benchmark_prices, secondary_frames=None, clock=None, gate_runner=None, remaining_cost_usd=None) -> ProtocolResult`
- Build one `StrategyDocument` from `spec.hypothesis.signal_mechanism` as `kind`, `market_profile` from spec, universe from `market_scope` split on commas (strip)
- Append trial-ledger JSONL lines `{trial_id, kind, parameters, revision: "method"|"none", timestamp}`
- Write `layout.evidence / "gates.json"` via `evidence_to_dict`
- Write `layout.recommendations.json` listing queued economic ideas as empty list for this phase (no LLM)
- Default `gate_runner` is `run_hard_gates`
- Outcome via `outcome_from_evidence(JobStatus.COMPLETED, evidence)` after a successful evaluate; on `IncompleteEvidenceError` or `UnsupportedDslError` → COMPLETED + INCONCLUSIVE and do not write a complete gates.json (or write incomplete marker without claiming FOUND)
- If `should_continue` says stop after a complete failing evidence set, do not generate further parameter variants
- Injectable `gate_runner` so FOUND/NO_EVIDENCE tests do not depend on beating all six real diagnostics

- [x] Tests: FOUND via fake all-pass gates; NO_EVIDENCE via fake one-fail; INCONCLUSIVE via missing required gate; economic revision not executed (loop does not change signal_mechanism); mixed profiles not applicable (single spec); trial ledger appended; recommendations.json exists
- [x] Commit `feat(protocol): add research loop with trial ledger and sealed evidence`

---

### Task 6: Wire worker, store, supervisor, preflight

**Files:**
- Modify: `src/alphaloop/runtime/store.py` add `complete_from_artifacts(run_id) -> JobRecord`
- Modify: `src/alphaloop/runtime/supervisor.py` on worker exit 0 call `complete_from_artifacts`
- Modify: `src/alphaloop/runtime/worker.py` default path calls `run_protocol` with synthetic/local prices loaded from `layout.run_dir / "prices.parquet"` if present else a deterministic synthetic fixture generated from spec seed (no network)
- Modify: `src/alphaloop/runtime/preflight.py` reject when `signal_mechanism` not in `ALLOWED_KINDS`
- Test: `tests/runtime/test_complete_from_artifacts.py`
- Modify: existing supervisor success test still INCONCLUSIVE without gates.json

**Interfaces:**
- `complete_from_artifacts`: if `evidence/gates.json` missing → `update_status(COMPLETED)` (INCONCLUSIVE, Phase 2 compatible); if present, `outcome_from_evidence(COMPLETED, evidence)` and persist `research_outcome` and `sealed_outcome` when FOUND
- Worker: if `runner_factory` provided, keep current LoopRunner-style call for existing worker unit tests; **default** factory None → `run_protocol`
- Generating synthetic prices must not import `alphaloop.loop`

- [x] Commit `feat(runtime): seal research outcome from protocol evidence artifacts`

---

### Task 7: Import graph, docs, regression

**Files:**
- Modify: `tests/runtime/test_import_graph.py` — also scan `protocol/` for live/webui/runtime imports
- Modify: `docs/plans/overnight-research-lab-refactor.md` Phase 3 bullet → link this plan
- Modify: `docs/requirements/product-positioning-requirements.md` §13 — items 1–2 done; item 3 is this plan
- Run: `python3 -m pytest tests/ -m "not integration" -q`

- [x] Commit `test(protocol): lock import graph and document phase 3 plan`

---

## Self-review

1. Spec coverage: DSL, epistemic stop, both profiles, real diagnostic wrap, worker no longer requires LoopRunner for default overnight jobs, FOUND only from GateEvidence.
2. Out of scope: morning Web, `.asb` zip producer, Agent Skill, MCP, LLM planner, rewriting aggregator.py math (protocol replaces it for new jobs; LoopRunner remains for `alphaloop loop`).
3. Types: `StrategyDocument`, `MarketProfile`, `StopDecision`, `ProtocolResult`, `complete_from_artifacts` consistent across tasks.
