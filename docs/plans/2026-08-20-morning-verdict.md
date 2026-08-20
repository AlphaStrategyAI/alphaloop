# Morning verdict stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the packaged morning conclusion a visual verdict stage whose gloss is copied from locked Help copy.

**Architecture:** `#verdict` wraps `#outcome` + `#outcome-gloss`. `fillOutcomeGloss` copies Help paragraphs. CSS grid overlay + clamp type. No webfont fetch. `#outcome` text stays the token.

**Tech Stack:** Packaged static console, pytest, Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-morning-verdict.md`

## Global Constraints

- Do not invent `FOUND`. Do not change `HOST_CONSTRAINT` or existing Help sentences.
- No `FakeWorker` in morning e2e. Do not unfreeze `webui/`.

---

### Task 1: Markup, gloss, visual system

**Files:** `src/alphaloop/webui/static/index.html`, `app.js`, `styles.css`; `tests/runtime/test_static_console.py`; `tests/e2e/test_morning_console.py`
