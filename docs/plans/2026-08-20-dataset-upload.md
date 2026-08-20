# Local dataset parquet picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a researcher pick a local parquet; the daemon caches it and fills dataset identity without submitting a job.

**Architecture:** `put_dataset_bytes` writes `{data_dir}/datasets/ds_<sha16>/prices.parquet`. `POST /v1/datasets` returns `{dataset_id, sha256}`. The packaged file input posts bytes and updates the form.

**Tech Stack:** Job API, stdlib HTTP, packaged static JS, pytest, Playwright.

**Spec:** `docs/requirements/2026-08-20-dataset-upload.md`

## Global Constraints

- Do not create a job from the picker. Do not invent `FOUND`.
- Do not change Help / `HOST_CONSTRAINT`. No FakeWorker in morning e2e.
- Dataset id format: `ds_` + first 16 hex chars of SHA-256.

---

### Task 1: Cache endpoint + picker

**Files:**
- Modify: `src/alphaloop/runtime/dataset_cache.py`, `api.py`, `daemon.py`, `client.py`
- Modify: `src/alphaloop/webui/static/index.html`, `app.js`
- Test: `tests/runtime/test_dataset_cache.py` (new or extend), `tests/runtime/test_http.py`, `tests/runtime/test_static_console.py`, `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

`put_dataset_bytes` / HTTP POST: parquet → 201 identity; empty and `not-parquet` → 400; `list_jobs` empty.

Static: `field-dataset-file` after `field-dataset-sha256`; `/v1/datasets` in script; `submitJob` not in the file-input handler.

E2E: `set_input_files` on `#field-dataset-file`; id/sha256 fill; Preview with Load example + uploaded bytes can enable Freeze; job count 0 until Freeze.

- [x] **Step 2: FAIL then implement**

- [ ] **Step 3: Unit + e2e**

- [ ] **Step 4: Commit**
