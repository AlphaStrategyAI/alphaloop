# Cancel/Resume designed chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Packaged `#cancel-job` and `#resume-job` use designed overnight chrome (focus blue / warn), not FOUND green.

**Architecture:** CSS only. Shared `--ink` chrome with Export/Load. Cancel `--focus`. Resume `--warn`. Hide/show unchanged.

**Tech Stack:** packaged `styles.css`, pytest static + Playwright e2e.

**Spec:** `docs/requirements/2026-08-20-lifecycle-chrome.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change hide/show. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle Export or Load.

---

### Task 1: Designed chrome

**Files:**
- Modify: `src/alphaloop/webui/static/styles.css`
- Modify: `docs/webui.md`, `mkdocs.yml`
- Test: `tests/runtime/test_static_console.py`
- Test: `tests/e2e/test_morning_console.py`

- [ ] **Step 1: Failing tests**

Static: `#cancel-job` and `#resume-job` in CSS; grouped or per-id rules set `background: var(--ink)`; cancel color block uses `var(--focus)` not `var(--accent)`; resume color block uses `var(--warn)` not `var(--accent)`.

E2E: after `#cancel-job:not([hidden])`, wait until `getComputedStyle` `.color` is `rgb(126, 184, 255)` and `.backgroundColor` is `rgb(11, 15, 22)`. After worker SIGKILL, open detail, wait until `#resume-job:not([hidden])` color is `rgb(255, 176, 32)`.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_static_console.py::test_packaged_console_lifecycle_chrome -v
```

- [ ] **Step 3: Implement**

Add `#cancel-job, #resume-job` chrome. Color `#cancel-job` with `--focus`. Color `#resume-job` with `--warn`.

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): style Cancel and Resume as overnight controls"
```
