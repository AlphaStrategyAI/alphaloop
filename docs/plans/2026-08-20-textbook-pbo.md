# Textbook S=16 PBO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefer Bailey/AFML `S=16` CSCV PBO when the aligned return sample is long enough, with vectorized path Sharpes so overnight jobs stay local-first.

**Architecture:** Reuse `select_cpcv_shape` for group count. Default `n_groups=None` auto-selects. Column Sharpes on boolean masks (`ddof=1`). `_attach_pbo` copies `pbo_n_groups`.

**Tech Stack:** Existing PBO module, protocol loop attach, pytest.

**Spec:** `docs/requirements/2026-08-20-textbook-pbo.md`

## Global Constraints

- Do not invent `FOUND`. Do not reduce DSR `n_trials`. `HOST_CONSTRAINT` locked.

---

### Task 1: Auto S=16 + vectorized Sharpes

**Files:** `src/alphaloop/diagnostic/pbo.py`; `tests/diagnostic/test_pbo.py`

### Task 2: Attach `pbo_n_groups`

**Files:** `src/alphaloop/protocol/loop.py`; `src/alphaloop/runtime/artifacts_io.py`; existing PBO protocol tests if they assert detail keys.
