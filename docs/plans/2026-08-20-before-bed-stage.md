# Before-bed stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make before-bed a grouped lab form with YAML folded, without changing the POST payload.

**Architecture:** Fieldset groups in `#hypothesis-form`. `#spec-yaml` inside closed `<details id="spec-yaml-fold">`. E2E `_preview_yaml` opens the fold before `fill`.

**Tech Stack:** Packaged static HTML/CSS, pytest, Playwright.

**Spec:** `docs/requirements/2026-08-20-before-bed-stage.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- No webfont `http`. No FakeWorker in morning e2e.
- `#spec-yaml` remains the preview/freeze body.

---

### Task 1: Groups + YAML fold

**Files:**
- Modify: `src/alphaloop/webui/static/index.html`, `styles.css`
- Modify: `tests/e2e/test_morning_console.py` (`_preview_yaml`, first-open assert)
- Test: `tests/runtime/test_static_console.py`

- [ ] **Step 1: Failing tests**

Static: `id="group-hypothesis"` … `group-dataset` in order; `id="spec-yaml-fold"` before `id="spec-yaml"`; `.form-group` in CSS; `http` not in CSS.

E2E `test_home_shows_promise_and_submit_form`: `#spec-yaml-fold` exists and is not open.

- [ ] **Step 2: FAIL then implement** (open fold in `_preview_yaml` before fill)

- [ ] **Step 3: Unit + e2e**

- [ ] **Step 4: Commit**
