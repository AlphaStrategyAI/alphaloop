# Guided dataset fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the before-bed form declare `dataset_id` and `sha256` without hand-editing YAML, without auto-binding empty jobs to `ds_example`.

**Architecture:** Two inputs in `#hypothesis-form`. `formToYaml` writes `dataset:` when both values are non-empty. `parseSpecYaml` / `yamlToForm` read nested dataset keys into those inputs.

**Tech Stack:** Packaged static console, pytest, Playwright.

**Spec:** `docs/requirements/2026-08-20-form-dataset.md`

## Global Constraints

- Do not auto-fill `ds_example` on first paint.
- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT`.
- No FakeWorker in morning e2e.

---

### Task 1: Form fields + round-trip

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`, `app.js`
- Test: `tests/runtime/test_static_console.py`, `tests/e2e/test_morning_console.py`

- [x] **Step 1: Failing tests**

Static: `id="field-dataset-id"` and `id="field-dataset-sha256"` in HTML after `field-cost-budget`; script contains both ids in `formToYaml` / `yamlToForm` paths.

E2E `test_load_example_fills_guided_form`: fields equal `ds_example` and packaged sha256.

E2E: Preview with empty dataset fields shows `dataset snapshot is required`.

- [x] **Step 2: FAIL then implement**

- [ ] **Step 3: Unit + e2e**

- [ ] **Step 4: Commit**
