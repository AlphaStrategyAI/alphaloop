# Require dataset at preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fail closed in preflight when a spec omits `dataset`, and keep Load example → Preview honest via a packaged `ds_example` snapshot.

**Architecture:** `preflight` errors if `spec.dataset is None`. `JobAPI` copies committed parquet bytes into the local dataset cache. `EXAMPLE_SPEC` declares that id and `sha256`. Specs that omit `dataset` are not auto-bound to the example.

**Tech Stack:** `preflight`, packaged resources, pytest, Playwright.

**Spec:** `docs/requirements/2026-08-20-require-dataset.md`

## Global Constraints

- Locked error: `dataset snapshot is required`
- Dataset id: `ds_example`
- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT`.
- No FakeWorker in morning e2e. Do not shrink DSR `N`.

---

### Task 1: Fail-closed preflight + packaged example

**Files:**
- Create: `src/alphaloop/runtime/example_dataset/__init__.py`, `prices.parquet`
- Modify: `src/alphaloop/runtime/preflight.py`, `src/alphaloop/runtime/api.py`, `src/alphaloop/webui/static/app.js`, `pyproject.toml`
- Modify: tests that `create_run(_spec())` or `preview_run` expect `ok`
- Test: `tests/runtime/test_preflight.py`, `tests/runtime/test_static_console.py`, `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

`test_missing_dataset_is_rejected`: `preflight(_spec(), tmp_path)` is not ok; locked sentence in errors.

Static: `EXAMPLE_SPEC` contains `dataset_id: ds_example` and the packaged sha256.

E2E `test_load_example_fills_spec_without_creating_a_job`: after Load example, Preview enables Freeze; still zero jobs.

E2E: YAML without `dataset` shows `dataset snapshot is required`; `#job-list button` count 0.

- [ ] **Step 2: FAIL then implement**

`preflight`: if `dataset is None`, append `dataset snapshot is required`.

Packaged parquet + `ensure_example_dataset(data_dir)` from `JobAPI.__init__`.

`EXAMPLE_SPEC` dataset block. Hatch force-include the parquet.

API/CLI tests that create or preview a valid spec pass `dataset=example_dataset_ref()`.

- [ ] **Step 3: Unit + e2e**

- [ ] **Step 4: Commit**
