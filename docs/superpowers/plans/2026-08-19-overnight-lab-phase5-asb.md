# Overnight Lab Phase 5 — `.asb` Producer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the Phase-1 export placeholder with an immutable `.asb` zip that a future AlphaStrategy consumer can load as YAML/DSL data only.

**Architecture:** New `alphaloop.bundle` writes and reads a zip archive whose layout matches requirements §8.2. It serializes Phase 1 `StrategyCandidateBundle` fields as YAML, copies sealed `evidence/`, and embeds shared conformance fixtures. Export is human-triggered, `FOUND`-only, and refuses any executable member. `alphaloop.protocol` and `alphaloop.live` are not imported by the archive writer except DSL `target_weights` for fixture generation (allowed: `bundle` may import `protocol.dsl` and `contracts`).

**Tech Stack:** Python 3.9+, stdlib `zipfile`, PyYAML, Phase 1 bundle contracts, Phase 3 DSL `target_weights`.

## Global Constraints

- Export only `FOUND` and a candidate id present in sealed evidence / trial ledger.
- Archive members: `bundle.yaml`, `strategy.dsl.yaml`, `market-profile.yaml`, `parameters.yaml`, `risk-envelope.yaml`, `lineage.yaml`, `evidence/`, `conformance/`. Optional `registry_uri` inside `bundle.yaml`.
- No `.py`, `.pyc`, wheels, scripts, notebooks, binaries, or credentials.
- YAML is canonical. Do not include generated Python projections.
- Hash matches Phase 1 `canonical_hash` of the bundle payload (not the zip bytes).
- No reverse telemetry fields (no fills, broker ids, live performance).
- Tests use synthetic prices only; shared fixtures live in-repo for a future consumer.
- Source of truth: `docs/requirements/product-positioning-requirements.md` §8 and design §3.5.

## File Structure

- Create: `src/alphaloop/bundle/__init__.py`
- Create: `src/alphaloop/bundle/archive.py`
- Create: `src/alphaloop/bundle/fixtures.py` — shared conformance inputs
- Modify: `src/alphaloop/cli/export.py`
- Modify: `tests/cli/test_export.py`
- Test: `tests/bundle/test_archive.py`
- Modify: docs Phase 5 pointer and requirements §13

---

### Task 1: Zip archive writer/reader and executable rejection

**Files:**
- Create: `src/alphaloop/bundle/__init__.py`
- Create: `src/alphaloop/bundle/archive.py`
- Test: `tests/bundle/test_archive.py`

**Interfaces:**
- `ASB_SCHEMA_VERSION = "asb.v1"` (stored as `StrategyCandidateBundle.schema_version`)
- `FORBIDDEN_SUFFIXES` includes `.py`, `.pyc`, `.pyo`, `.so`, `.dll`, `.exe`, `.sh`, `.bat`, `.whl`, `.ipynb`
- `write_asb(path, bundle: StrategyCandidateBundle, *, evidence: Mapping[str, bytes], conformance: Mapping[str, bytes]) -> None`
- `read_asb(path) -> StrategyCandidateBundle`
- `inspect_asb(path) -> tuple[str, ...]` member names
- Writer builds YAML members from `bundle.to_payload()` split across the layout files; `bundle.yaml` includes `schema_version`, `bundle_id`, `content_hash`, `registry_uri`
- Reader rejects zip if any member has a forbidden suffix or if `canonical_hash` of reconstructed payload != `content_hash` in `bundle.yaml`
- `read_asb` uses `bundle_from_payload` so unknown keys still fail closed

- [x] Tests: round-trip hash; `.py` member rejected on write and read; missing evidence dir still allowed if empty mapping writes no extra files? **Write `evidence/gates.json` when provided**; empty evidence mapping writes no evidence files but export of FOUND should include gates — CLI task supplies them.
- [x] Commit `feat(bundle): write and read immutable YAML-only .asb archives`

---

### Task 2: Shared conformance fixtures

**Files:**
- Create: `src/alphaloop/bundle/fixtures.py`
- Modify: `tests/bundle/test_archive.py`

**Interfaces:**
- `CONFORMANCE_AS_OF` = Timestamp `2018-12-31`
- `conformance_prices() -> dict[str, pd.Series]` deterministic rising AAPL/MSFT daily series (same construction as protocol tests: 300 bdays from 2018-01-01, `100+i`)
- `expected_weights(kind, parameters, universe, profile, prices, as_of) -> dict[str, float]` via `protocol.dsl.target_weights`
- `conformance_members(kind, parameters, universe, profile) -> dict[str, bytes]` YAML for `inputs.yaml` and `expected_weights.yaml`

- [x] Tests: expected weights sum to 1.0 or all 0; fixture bytes are YAML not Python
- [x] Commit `feat(bundle): add shared DSL conformance fixtures`

---

### Task 3: Wire `alphaloop export` to a FOUND run

**Files:**
- Modify: `src/alphaloop/cli/export.py`
- Modify: `tests/cli/test_export.py`

**Interfaces:**
- `alphaloop export CANDIDATE_ID --run-id RUN_ID [--data-dir DIR] --output PATH`
- Load `JobStore` at `{data_dir}/.alphaloop/state.db` (same control dir as the daemon)
- `assert_exportable(job.research_outcome, sealed_ids, candidate_id)` where `sealed_ids` come from trial-ledger `trial_id` values (fallback: candidate_id if ledger missing but evidence complete FOUND — still require ledger id match when ledger exists)
- Build DSL document from frozen spec; `parameters` from the matching ledger line if present else `{}`
- Include `evidence/gates.json` bytes from the run layout
- Help text no longer says placeholder
- Non-FOUND still exit 2

- [x] Tests: FOUND job exports zip with bundle.yaml and no .py; NO_EVIDENCE exit 2; help has `.asb` not placeholder
- [x] Commit `feat(cli): export FOUND candidates as immutable .asb archives`

---

### Task 4: Docs and regression

**Files:**
- Modify: design §5 Phase 5 → this plan
- Modify: requirements §13 items 1–4 done; item 5 is this plan
- Run: `python3 -m pytest tests/ -m "not integration" -q`

- [x] Commit `docs: point Phase 5 .asb producer at the implementation plan`

---

## Self-review

1. Spec coverage: zip layout, hash, FOUND-only, no executables, shared conformance, no telemetry.
2. Out of scope: AlphaStrategy consumer repo, Bundle Registry, Agent Skill, MCP.
3. Types: reuse `StrategyCandidateBundle`; do not invent a second schema.
