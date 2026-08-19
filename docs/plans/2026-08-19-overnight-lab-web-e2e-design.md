# Overnight lab morning console — real daemon and Web E2E

**Date:** 2026-08-19  
**Status:** approved design  
**Related:** `docs/requirements/product-positioning-requirements.md`,  
`docs/plans/2026-08-19-overnight-lab-phase4-morning-web.md`,  
`docs/plans/2026-08-19-overnight-lab-phase10-morning-submit.md`

## 1. Goal

Prove the overnight-lab morning path the way a user uses it:

- **Unit tests** may talk only to a **real daemon** (`spawn_detached_daemon` /
  `alphaloop start --detach` with `ProcessWorker`). They do not need a
  browser. They must not use `FakeWorker`.
- **End-to-end tests** must drive the **real packaged Web page** in a
  real browser **and** the **real daemon**. No `FakeWorker`. No injecting
  `FOUND`. No synthetic RNG prices.

Existing supervisor isolation tests that already use `FakeWorker` stay.
This work does not rewrite them.

## 2. Product surface (in scope)

Packaged morning console served by the loopback daemon:

- `/` copy and legend: `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`
- YAML textarea `#spec-yaml` and `#submit-job`
- `#preflight-errors` on 400
- `#host-constraint` on success (locked `HOST_CONSTRAINT` text)
- `#job-list` polled every 2s
- Click a job → `#detail`: outcome, stop reason, evidence, funnel,
  revisions, queued hypotheses
- No gate-override control; `/v1/jobs/{id}/gates` remains 404

Same `run_id` / `--data-dir` CLI:

- `alphaloop status`
- `alphaloop cancel`
- `alphaloop resume`
- `alphaloop replay`
- `alphaloop export` (FOUND only)

## 3. Out of scope

- Frozen v0.7 FastAPI + Vite SPA
- `alphaloop.live`
- Soak, five-minute human readability, AlphaStrategy consumer import
- Forcing `FOUND`; if the shortened worker run is not FOUND, export
  asserts exit 2 and the page still shows a legal outcome token

## 4. Architecture

```
Playwright Chromium  →  GET /  (packaged index.html + app.js)
                     →  POST /v1/jobs  (application/yaml)
Real daemon process  →  JobAPI + Supervisor + ProcessWorker
                     →  real worker: -m alphaloop.runtime.worker
CLI                  →  read_daemon_meta(data_dir) → same Job API
```

Each test gets an isolated `tmp_path` data dir and a detached daemon on
loopback port 0. Tests stop the daemon pid in teardown.

Fixture parquet lives at `data_dir/datasets/<id>/prices.parquet` with a
matching `DatasetRef` when the spec declares a dataset.

## 5. Scenario matrix

### Unit (real daemon, no browser)

| Id | Case | Assert |
| --- | --- | --- |
| U1 | POST YAML without `spec_id` | 201, `run_id`, `host_constraint` == locked text |
| U2 | POST empty `hard_gates` | 400, errors mention hard gate, no job row |
| U3 | POST unknown `signal_mechanism` | 400, no job row |
| U4 | POST declared missing dataset | 400, dataset unavailable |
| U5 | GET `/` and `/app.js` | HTML legend + YAML submit; JS posts `application/yaml`; no "override" |

### E2E (real page + real daemon)

| Id | Case | Assert |
| --- | --- | --- |
| E1 | Open `/` | Visible promise, three outcome tokens, submit form |
| E2 | Submit invalid YAML (empty gates) | `#preflight-errors` non-empty; job list does not gain a `j_` row |
| E3 | Submit valid YAML (no `spec_id`) with hashed fixture dataset | `#host-constraint` exact locked text; list shows `run_id` |
| E4 | Click the new job while not yet terminal | `#detail` visible; outcome is `none` or a later legal token; stop-reason line present |
| E5 | Wait until job is terminal (short `time_budget_s`) | Page outcome ∈ {FOUND, NO_EVIDENCE, INCONCLUSIVE}; matches `alphaloop status`; never "target found" |
| E6 | Spec declares dataset whose parquet is missing required columns | Terminal `INCONCLUSIVE`; no `evidence/gates.json`; page evidence list is empty/`none` |
| E7 | Submit then `alphaloop cancel` before seal | Page + CLI: `cancelled` and `INCONCLUSIVE` |
| E8 | If E5 sealed FOUND, `alphaloop cancel` | Page remains FOUND (else skip; contract tests already cover the matrix) |
| E9 | After worker has a pid, SIGKILL worker, `alphaloop resume` | Page list shows queued or running for that `run_id` |
| E10 | After terminal, `alphaloop replay RUN_ID` | `report.md` rewritten; page outcome unchanged |
| E11 | `alphaloop export` | FOUND → `.asb` exists; otherwise exit 2 |
| E12 | No gate override | Page has no override control; PUT/PATCH/POST `/v1/jobs/{id}/gates` → 404 |

## 6. Tooling

- Extra: `project.optional-dependencies.e2e = ["playwright>=1.40"]`
- Marker: `e2e`
- Default GitHub unit job: `pytest -m "not integration and not llm and not e2e"`
- New CI job: install `[dev,e2e]`, `playwright install --with-deps chromium`, `pytest -m e2e`
- Local skip: e2e tests `importorskip("playwright")` and skip if Chromium cannot launch

## 7. Locks

- `HOST_CONSTRAINT` text is frozen.
- `FOUND` only from complete `GateEvidence`.
- Protocol does not import `live` / `webui` / `runtime`.
- Do not enable Cloud Agent environment builds as part of this test work.
