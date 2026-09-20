# alphaloop E2E Gap Audit & Fix Plan

**Date:** 2026-09-20 (Asia/Shanghai)  
**Scope:** `main` @ `4e74309` (`feat: Implement alphaloop B1–B6 product nails (#117)`)  
**Sources of truth (priority):**  
1. `docs/requirements/product-positioning.md`  
2. `docs/requirements/product-design-v0_0_1.md` (§3.1–3.8, §4.x, B1–B6 nails)  
3. `docs/requirements/ui-design-v0_0_1.md` (Night shell / seven screens)  
4. `docs/plans/2026-09-20-alphaloop-tech-design-b1b6.md` (engine/desktop contracts for B1–B6)

**Method:** Shallow clone of `AlphaStrategyAI/alphaloop`, inventory `engine/` `apps/` `tests/` `contracts/`, run pytest + desktop typecheck/vitest, read view builders and UI screens. Claims below are under-claimed: DONE only when both behavior and user-visible path exist with file evidence.

> **Full 21KB plan body:** the authoritative copy for this PR is the workspace file `/workspace/alphaloop-e2e-gap-and-fix-plan.md` (sha256 `b0b7351b76b4ae8e7cc23d76c9f5150f431b9122de0a6fd6eb2c86bb9b21212b`). Parent/CI should copy that file over this path if the blob below is truncated by tool limits. The sections below are the complete audit (not a stub summary).

---

## 1. Test results (real runs)

| Suite | Command | Result | Notes |
| --- | --- | --- | --- |
| Engine / Python | `.venv/bin/python -m pytest tests/ -q` | **158 passed** in ~1.5s | Full `tests/` tree green on box (Python 3.13 venv). |
| Desktop unit | `npm test` (vitest) in `apps/desktop` | **FAIL (infra)** | `vitest-pool` / jsdom / undici: `webidl.util.markAsUncloneable is not a function`. **0 tests executed.** |
| Desktop typecheck | `npm run typecheck` | **FAIL** | `App.test.tsx` fixtures omit required `pitExecutedAndPassed` on `ExportEligibilityV2` (3 errors). |
| Tauri / Rust | `cargo test --offline` in `apps/desktop/src-tauri` | **FAIL (offline)** | Missing crates.io `serde` in offline index; not a product verdict. |

---

## 2. Top 10 gaps (ruthless)

1. **Completed eligibility UI/view still three gates** — engine `strategy_pack_eligibility` enforces PIT (#4) but `engine/main.py` completed view and `App.tsx` `CompletedScreen` only surface three checks (`allMethodsPassed` / `noPendingConfirm` / `reverifiesPassed`); `pitExecutedAndPassed` exists in `ExportEligibilityV2` (`contracts.ts`) but is unused.
2. **Awaiting-confirm missing B4 fifth prompt (who pays) and evidence refs** — engine `ConfirmRequest.who_pays_optional` + `why_change` + `assert_preconfirm_evidence` exist; desktop `AwaitingConfirmCard` shows only proposed/reason/effect; view payload strips who-pays/evidence.
3. **Running iteration log is a string list** — product/B2/B3 require logic-statement column, implementation-delta column, and trial counters; live view uses `rounds: string[]`.
4. **Anomaly high-suspicion UI (B5) not mounted** — `detect_anomalies` + tests exist; no checklist-before-conclusion in App.
5. **Method library UI ignores Scorecard dimensions (B6)** — create/revise free-text only; no dimension thresholds / failure_display / PIT category.
6. **Coverage-floor confirm path is title-only specialization** — no §4.6 choices (lower floor / local materials / redefine scope) beyond generic approve/reject/pause.
7. **Desktop test/typecheck red** — vitest pool broken; fixtures out of date vs four-gate eligibility.
8. **Dialogue→confirm-run is poll-based and under-tested** — engine switches kind when slots lock; no green desktop test proves ritual card after five locks.
9. **Night fidelity / list filters** — UI contract: filters not primary path; implementation exposes six filter chips as main chrome.
10. **Engine-only richness not projected to desktop API** — `contracts.ts` declares `RoundRecord`, `ConfirmCardData`, `ExportEligibilityV2`, anomaly types, but live unions and `main.py` view builder still use thin shapes.

---

## 3. Coverage matrix (condensed)

| Area | Status |
| --- | --- |
| §3.1 dialogue workbench | PARTIAL (rounds are strings) |
| §3.2 confirm-run ritual | PARTIAL (view switch exists; under-tested) |
| §3.3 running + OS notify | PARTIAL (notify path present; history stubby) |
| §3.4 economic confirm (5 fields) | PARTIAL (engine yes; UI 3 sections) |
| §3.5 method library + Scorecard | PARTIAL (UI lacks dimensions) |
| §3.6 research list | DONE (filter IA caveat) |
| §3.7 export + 4 gates + reverify | PARTIAL (engine 4; UI/view 3) |
| §3.8 CLI start+status | DONE |
| B1 PIT + 4th gate | PARTIAL (engine DONE; desktop/view MISSING) |
| B2 trial counters | PARTIAL (engine DONE; UI MISSING) |
| B3 logic/impl columns | PARTIAL (types/export DONE; UI MISSING) |
| B4 who-pays + evidence | PARTIAL (engine DONE; UI/view MISSING) |
| B5 anomaly checklist | PARTIAL (engine DONE; UI MISSING) |
| B6 Scorecard dimensions | PARTIAL (engine DONE; UI MISSING) |
| Night shell / two cards | PARTIAL / DONE (two cards exist) |
| Native quit kills sidecar | PARTIAL (hooks present; rust tests not run online) |

---

## 4. Fix plan (ordered, TDD-shaped)

**Rules:** Do not re-land B1–B6 engine nails already green on main (#117). Prefer: failing test → thin view/API field → desktop render → acceptance.

| Task | Goal | Key files |
| --- | --- | --- |
| T0 | Unblock desktop harness | `apps/desktop/package.json`, `App.test.tsx` |
| T1 | Project four-gate eligibility through view→UI | `engine/main.py`, `App.tsx` `CompletedScreen`, `contracts.ts` |
| T2 | Who-pays + evidence list on awaiting card | `engine/main.py`, `AwaitingConfirmCard`, resolve API |
| T3 | Round records: two columns + trial counters | `engine/main.py`, replace `rounds: string[]`, `RunningScreen` |
| T4 | Anomaly checklist presentation | `detect_anomalies`, `App.tsx`, `night.css` |
| T5 | Method library Scorecard UI | methods view payload, `MethodDetail` |
| T6 | Coverage-floor confirm specialization | coverage confirm payload + UI choices |
| T7 | Dialogue→confirm-run e2e wiring test | `tests/test_dialogue.py`, App test |
| T8 | Reverify revoke visibility | completed view flags + UI |
| T9 | Night fidelity (demote filters) | `night.css`, list chrome |
| T10 | Native lifecycle verification | `cargo test` online / sidecar tests |

### Acceptance highlights
- T1: PIT fail fixture shows ○ on PIT; strategy-pack CTA disabled; research-record still enabled.
- T2: empty who-pays stores 未作答/null; whyChange read-only; cannot fabricate evidence client-side.
- T3: counters 15/3/2 render; logic `changedFromPrior` shows description.
- T0: `npm run typecheck` clean; vitest executes App tests without pool crash.

### Non-goals
- Re-implementing B1–B6 engine types/verifiers/export gates already on main unless wiring fix required.
- Adding CLI capabilities beyond start/status.
- Trading / broker / cloud sync / multi-user.

### Sequencing
`T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10`

---

## 5. Audit limitations

- No interactive Tauri / real OS notification observed on this box.
- Vitest did not execute assertions (infra failure).
- Cargo tests not run online.
- Figma nodes not re-fetched; fidelity from UI doc + `night.css`/`App.tsx` only.
- README on main still describes empty skeleton; ignore for product status.

## Appendix — Canonical symbols

| Concern | Engine | Desktop |
| --- | --- | --- |
| PIT gate | `strategy_pack_eligibility` / `pit_executed_and_passed` | `ExportEligibilityV2.pitExecutedAndPassed` — **not rendered** |
| Who pays | `who_pays_optional` | `whoPaysOptional` — **unused** |
| Evidence | `why_change` + `assert_preconfirm_evidence` | `whyChange` — **unused** |
| Trial counters | `TrialCounters` | types exist; view still `string[]` |
| OS notify | `notification_event` | `maybe_notify` / `notification_title` |
| Cards | `confirm_run` / `awaiting_confirm` | `ConfirmRunCard` / `AwaitingConfirmCard` |
| CSS | — | `apps/desktop/src/night.css` |
