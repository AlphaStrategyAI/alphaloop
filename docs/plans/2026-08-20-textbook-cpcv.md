# Textbook S=16 CPCV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefer AFML `S=16` `k=8` combinatorial purged CV when the sample is long enough, with a span-end cache so overnight jobs stay local-first.

**Architecture:** `select_cpcv_shape` chooses `(16, 8)` or `(6, 2)`. `combinatorial_purged_cv` auto-selects when groups are omitted, caches `strategy_fn` by span end, and ANDs majority of path Sharpes. `run_hard_gates` copies the new detail keys.

**Tech Stack:** Existing diagnostic CV, protocol gates, pytest.

**Spec:** `docs/requirements/2026-08-20-textbook-cpcv.md`

## Global Constraints

- Do not invent `FOUND`. CPCV can only tighten `walk_forward` or stay unevaluated.
- `HOST_CONSTRAINT` locked. No `FakeWorker` in morning e2e.

---

### Task 1: Shape + CPCV

**Files:** `src/alphaloop/diagnostic/cv.py`; `tests/diagnostic/test_cv.py`

`select_cpcv_shape(n) -> (16,8) | (6,2) | None`. Default `combinatorial_purged_cv` uses it. Cache net returns by `span_end`. Majority via `majority_fold_ok`.

### Task 2: Gate detail

**Files:** `src/alphaloop/protocol/gates.py`; `src/alphaloop/runtime/artifacts_io.py`; `tests/protocol/test_gate_adapters.py`

Copy `cpcv_n_groups`, `cpcv_n_test_groups`, `cpcv_n_positive_paths`. 400-bar WF test expects `cpcv_n_paths == 12870`.
