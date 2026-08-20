# Queued follow-up auto-preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After Load into editor, preview the queued YAML so a human can Freeze and submit in one click, without auto-creating a job.

**Architecture:** `loadQueuedHypothesis` fills the form then calls existing `previewProtocol()`. Submit stays the only `POST /v1/jobs` create.

**Tech Stack:** Packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-queued-preview.md`

## Global Constraints

- Do not invent `FOUND`. Do not auto-submit. `HOST_CONSTRAINT` locked.

---

### Task 1: Console

**Files:** `src/alphaloop/webui/static/app.js`; `tests/runtime/test_static_console.py`; `tests/e2e/test_morning_console.py`

`loadQueuedHypothesis` ends by calling `previewProtocol()`. Static test asserts `previewProtocol` appears after `loadQueuedHypothesis`. E2E waits for `#submit-job` enabled, asserts one job.
