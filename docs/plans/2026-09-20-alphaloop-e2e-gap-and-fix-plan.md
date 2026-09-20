# alphaloop E2E Gap Audit & Fix Plan

**Date:** 2026-09-20 (Asia/Shanghai)  
**Scope:** `main` @ `4e74309` (`feat: Implement alphaloop B1–B6 product nails (#117)`)  
**Sources of truth (priority):**  
1. `docs/requirements/product-positioning.md`  
2. `docs/requirements/product-design-v0_0_1.md` (§3.1–3.8, §4.x, B1–B6 nails)  
3. `docs/requirements/ui-design-v0_0_1.md` (Night shell / seven screens)  
4. `docs/plans/2026-09-20-alphaloop-tech-design-b1b6.md` (engine/desktop contracts for B1–B6)

**Method:** Shallow clone of `AlphaStrategyAI/alphaloop`, inventory `engine/` `apps/` `tests/` `contracts/`, run pytest + desktop typecheck/vitest, read view builders and UI screens. Claims below are under-claimed: DONE only when both behavior and user-visible path exist with file evidence.

---

## 1. Test results (real runs)

| Suite | Command | Result | Notes |
| --- | --- | --- | --- |
| Engine / Python | `.venv/bin/python -m pytest tests/ -q` | **158 passed** in ~1.5s | Full `tests/` tree green on box (Python 3.13 venv). |
| Desktop unit | `npm test` (vitest) in `apps/desktop` | **FAIL (infra)** | `vitest-pool` / jsdom / undici: `webidl.util.markAsUncloneable is not a function`. **0 tests executed.** |
| Desktop typecheck | `npm run typecheck` | **FAIL** | `App.test.tsx` fixtures omit required `pitExecutedAndPassed` on `ExportEligibilityV2` (3 errors). |
| Tauri / Rust | `cargo test --offline` in `apps/desktop/src-tauri` | **FAIL (offline)** | Missing crates.io `serde` in offline index; not a product verdict. Unit tests for notify titles exist in `commands.rs` (`notify_titles_cover_only_awaiting_and_terminal_states`). |

**Interpretation:** Engine B1–B6 and core research loop are well covered by pytest. Desktop regression harness is currently broken (typecheck + vitest env), so UI claims cannot be treated as tested-green.

---

## 2. Inventory snapshot (main)

| Area | What exists (evidence) | Rough maturity |
| --- | --- | --- |
| Engine core | `engine/main.py` (~795 LOC) JSON command server; `engine/research/*` state machine, loop, coverage, methods, store | High for headless research |
| Export | `engine/export.py` strategy pack + research record; four-gate `strategy_pack_eligibility` incl. PIT | High in engine; view/API thin |
| Dialogue | `engine/dialogue/*` slot lock + intent; draft→`confirm_run` when `all_slots_locked` | Medium–high |
| CLI | `apps/cli/main.py`: **only** `start` + `status` | DONE vs §3.8 closed list |
| Desktop React | `apps/desktop/src/App.tsx` (~382 LOC), `contracts.ts`, `night.css` | Shell + 7 screens skeleton; B2–B5 UI mostly absent |
| Tauri | Sidecar lifecycle (`lib.rs`), commands + OS notify (`commands.rs`), notification plugin | Lifecycle + notify path present |
| Contracts | `contracts/*.schema.json` incl. method-definition, strategy-pack, research-record | Present; desktop view payloads lag schemas |
| B1–B6 types/tests | `tests/test_pit_verifier.py`, `test_logic_impl_split.py`, `test_evidence_ref.py`, `test_scorecard_dimensions.py`, `test_anomaly_detection.py` | Engine-side largely landed via #117 |

---

## 3. Coverage matrix

Status legend: **DONE** = user-visible + engine path with evidence · **PARTIAL** = types/tests/engine without full desktop or view wiring · **MISSING** = no credible path.

### 3.1 Product design §3.1–3.8

| Req | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| §3.1 | Research dialogue workbench: 5 slots, summary, progress, iteration/validation log, confirm cards, results | **PARTIAL** | Draft + settings sidebar: `App.tsx` `DraftScreen` / `Settings`; progress header in `RunningScreen`; rounds rendered as **plain strings**, not two-column logic/impl + trial counts. Engine promotes draft→`confirm_run` when slots locked (`engine/main.py` ~341). |
| §3.2 | Confirm-run ritual (summary + autonomy + effective-time copy + confirm / 再改改) | **PARTIAL** | `ConfirmRunCard` / `confirm_run` view exist (`App.tsx` ~197–210). Dialogue→confirm-run **view switch** works via poll + `all_slots_locked`. No dedicated e2e that locks five slots then asserts card. |
| §3.3 | Running research: action, budget, materials note, pause/resume/modify, OS notify on await/complete/stop | **PARTIAL** | Running UI + materials note (`App.tsx` ~213–252). Notify: engine `notification_event` (`engine/research/progress.py`) + Tauri `maybe_notify` (`commands.rs`). Round history UI is stubby (string list). |
| §3.4 | Economic confirm card: **five** fields incl. who-pays; three decisions; no auto-timeout | **PARTIAL** | Engine `ConfirmRequest` has `who_pays_optional` + `why_change` + `assert_preconfirm_evidence` (`models.py`, `state_machine.py`). Desktop `AwaitingConfirmCard` shows only 3 sections (proposed/reason/effect); **no who-pays input**; contracts `ConfirmCardData` unused by UI. View builder omits who-pays / evidence refs (`engine/main.py` awaiting_confirm payload ~375–390). |
| §3.5 | Method library: list/detail, create, revise=new definition, usage, Scorecard dimensions, PIT preset | **PARTIAL** | Methods screen create/revise/usage (`App.tsx` `MethodsScreen`). Engine Scorecard + immutability + `pit.consistency` tests green. **UI does not render dimensions / failure_display / PIT category.** |
| §3.6 | Research list: six statuses, awaiting primary card, enter/delete, drafts retained | **DONE** (with caveat) | List + awaiting primary + filters + delete warning (`App.tsx` `ResearchList`). Caveat: UI design says filters must not be the primary path; filters are prominent (`list-filters`) — Night fidelity **PARTIAL**. |
| §3.7 | Strategy pack vs research-record; four eligibility gates; reverify fail revokes; overturned export banner | **PARTIAL** | Export kinds + buttons (`CompletedScreen`). Engine four gates incl. `pit_executed_and_passed` (`export.py` ~66–92). **Desktop eligibility UI shows only 3 checks** and ignores `pitExecutedAndPassed` (`App.tsx` ~275–280) even though `ExportEligibilityV2` has the field (`contracts.ts` ~193–198). Engine completed **view** also emits only 3 eligibility booleans (`main.py` ~400–414). Reverify + overturned flag paths exist engine-side (`mark_exports_overturned` / tests). |
| §3.8 | CLI closed list: start + status only | **DONE** | `apps/cli/main.py` `build_parser`: only `start` / `status`. |

### 3.2 Product design §4.x flows

| Flow | Status | Evidence / gap |
| --- | --- | --- |
| §4.1 Main path draft→confirm→run→confirm→complete→export | **PARTIAL** | Pieces exist; missing rich iteration UI + 4th gate in completed view. |
| §4.2 Pause (effective time frozen) | **PARTIAL** | Pause/resume commands + UI; clock behavior covered in engine tests (`test_loop_runtime.py` / state machine). Desktop does not surface “这段时间不计入” beyond awaiting card copy. |
| §4.3 Modify-and-rerun (new version, same dialogue) | **PARTIAL** | `confirmModification` / dialogue inputs on paused & completed screens. |
| §4.4 Economic confirm | **PARTIAL** | See §3.4 — missing 5th prompt + evidence citations in UI/view. |
| §4.5 Mid-run method add/replace → confirm + deposit | **PARTIAL** | Engine confirm kinds / deposit paths in `main.py` handle; desktop has no dedicated “method set change” card content. |
| §4.6 Coverage floor breach → must confirm; within floor auto-shrink recorded | **PARTIAL** | Engine coverage confirm + shrink recording (`coverage.py`, loop tests). Desktop distinguishes `confirmKind === "coverage"` title only; no explicit accept-lower-floor / supply-local / shrink-scope choices beyond the three generic buttons. |
| §4.7 Time exhausted → ended; extend opens new version; research-record only | **PARTIAL** | Ended status + extend controls on completed screen; export disables strategy pack when `status === "ended"`. |
| §4.8 Six-status matrix | **PARTIAL** | Status enum aligned; not every transition asserted in desktop tests (harness broken). |

### 3.3 B1–B6 (tech design) — do **not** re-implement engine nails already on main

| Nail | Engine (#117) | Desktop / live view | Status |
| --- | --- | --- | --- |
| **B1** PIT verifier + 4th export gate | DONE — `engine/verifiers.py`, `export.py`, `test_pit_verifier.py` | MISSING in completed eligibility UI + view payload | **PARTIAL** |
| **B2** Trial counters on rounds + pack history | DONE — models + export helper + tests | MISSING in `RunningScreen` (rounds are `string[]`) | **PARTIAL** |
| **B3** Logic vs implementation two columns; logic change → confirm | Types + export DONE; loop/classify needs continuous enforcement | MISSING two-column UI | **PARTIAL** |
| **B4** Who-pays + preconfirm evidence ids | Models + `assert_preconfirm_evidence` on approve DONE | UI/view omit who-pays & `whyChange`; TS types unused | **PARTIAL** |
| **B5** Anomaly checklist vs baseline | `detect_anomalies` + tests DONE | No anomaly section in App; CSS may lack checklist block usage | **PARTIAL** |
| **B6** Scorecard dimensions + immutability | Schema + methods + tests DONE | Method detail UI does not show dimensions | **PARTIAL** |

### 3.4 Night UI / CLI / native

| Item | Status | Evidence |
| --- | --- | --- |
| Night tokens (void/glass/ink/…; cyan only on confirm screens) | **PARTIAL** | `night.css` tokens present; cyan used on confirm CTAs. Full Figma node parity not verified in-browser this audit. |
| Shell: 148 rail, logo square, HostStatus | **PARTIAL** | Rail + logo + host status in `NightShell`; widths differ slightly from UI doc table (doc 148px; CSS uses similar Night geometry). |
| Seven screens | **PARTIAL** | All kinds routed in `Screen` switch; content depth uneven (running/completed thin). |
| Two cards (confirm-run ≠ awaiting-confirm), not one modal | **DONE** | Separate `ConfirmRunCard` / `AwaitingConfirmCard`; tests *intend* non-dialog (blocked by vitest infra). |
| OS notifications (awaiting / completed / ended only) | **PARTIAL→near DONE** | Engine events + Tauri `notification_title` allowlist; depends on `fetch_view`/mutate draining notify payload while app lives. Not OS-integration-tested here. |
| Native quit kills sidecar; web tab close does not | **PARTIAL** | `lib.rs` window close / exit hooks call supervisor quit; dedicated rust tests not run (offline cargo). |
| CLI start+status only | **DONE** | See §3.8. |

---

## 4. Top gaps (ruthless)

1. **Completed eligibility UI/view still three gates** — engine export enforces PIT (#4) but `engine/main.py` completed view and `App.tsx` `CompletedScreen` only surface three checks; users can believe they are eligible when PIT failed, or conversely never see why pack export failed.
2. **Awaiting-confirm card missing B4 fifth prompt (who pays) and evidence refs** — engine validates on approve; desktop cannot collect `who_pays_optional` or show `why_change` EvidenceRefs; view payload strips them.
3. **Running iteration log is a string list** — product/B2/B3 require logic-statement column, implementation-delta column, and trial counters; `DesktopView.running.rounds: string[]` cannot carry them.
4. **Anomaly high-suspicion UI (B5) not mounted** — detection helpers exist; no checklist-before-conclusion presentation in results/running screens.
5. **Method library UI ignores Scorecard dimensions (B6)** — create/revise only free-text; no dimension thresholds / failure_display / PIT category.
6. **Coverage-floor confirm path is title-only specialization** — no product §4.6 choices (lower floor / local materials / redefine scope) beyond generic approve/reject/pause.
7. **Desktop test/typecheck red** — vitest pool broken; `App.test.tsx` out of date vs `ExportEligibilityV2.pitExecutedAndPassed`; no reliable UI regression net.
8. **Dialogue→confirm-run is poll-based and under-tested** — engine switches kind when slots lock; no green desktop test proves the ritual card appears after five locks.
9. **Night fidelity / list filters** — UI contract: filters not primary path; implementation exposes six filter chips as main chrome.
10. **Engine-only richness not projected to desktop API** — `contracts.ts` already declares `RoundRecord`, `ConfirmCardData`, `ExportEligibilityV2`, anomaly types, but live `DesktopView` unions and `main.py` view builder still use thin shapes — classic “types exist, product path doesn’t.”

---

## 5. Fix plan (ordered, TDD-shaped, no TBD)

**Rules:** Do not re-land B1–B6 engine nails already green on main. Prefer: failing test → thin view/API field → desktop render → acceptance. Exact files named.

### Task 0 — Unblock desktop harness (prerequisite)

**Files:** `apps/desktop/package.json` (jsdom/vitest pins if needed), `apps/desktop/src/App.test.tsx`, optionally `vite.config.ts`  
**Steps:**  
1. Fix vitest/jsdom/undici worker error until `npm test` executes files.  
2. Add `pitExecutedAndPassed` to all `ExportEligibilityV2` fixtures in `App.test.tsx`.  
3. RED→GREEN: `npm run typecheck` exits 0; `npm test` runs (even if some assertions fail).  
**Acceptance:** typecheck clean; vitest runs App tests without pool crash.

### Task 1 — Project four-gate eligibility through view → UI (B1 gap)

**Files:** `engine/main.py` (completed view), `apps/desktop/src/contracts.ts` (ensure view `eligibility` uses `ExportEligibilityV2`), `apps/desktop/src/App.tsx` `CompletedScreen`, `tests/test_export_pack.py` or new `tests/test_desktop_views.py`, `App.test.tsx`  
**Steps:**  
1. Test: completed view JSON includes `pitExecutedAndPassed` false when PIT missing/failed; strategy pack export still rejected by engine.  
2. Map `strategy_pack_eligibility(...).failed_checks` into four booleans in view builder (do not invent a second eligibility function).  
3. UI: fourth checklist row 「时点一致性已执行且通过」; disable strategy-pack CTA unless all four true; show which gate failed.  
**Acceptance:** With PIT fail fixture, UI shows ○ on PIT and export strategy pack disabled; research-record still enabled; pytest + App test cover the four rows.

### Task 2 — Awaiting confirm: who-pays + evidence list (B4 gap)

**Files:** `engine/main.py` awaiting_confirm payload, `apps/desktop/src/contracts.ts` (`awaiting_confirm` view fields), `App.tsx` `AwaitingConfirmCard`, `engine/research/state_machine.py` (already validates), `tests/test_evidence_ref.py` / view test, `App.test.tsx`  
**Steps:**  
1. Extend awaiting view with `whyChange: EvidenceRef[]`, `whoPaysOptional`, `createdAt`, `requestId`.  
2. UI: sections 1–3 unchanged; add section 4 who-pays textarea (optional, empty → 未作答); render whyChange as checklist of id/time/summary (read-only).  
3. On approve, send who-pays back via resolve API (extend command if needed in `commands.rs` + `engine/main.py`).  
4. Keep engine `assert_preconfirm_evidence` as source of truth — UI must not invent evidence.  
**Acceptance:** Approve with empty who-pays stores 未作答/null; missing whyChange cannot be fabricated client-side; App test clicks three decisions; who-pays field present.

### Task 3 — Round records: two columns + trial counters (B2/B3 gap)

**Files:** `engine/main.py` running (+ completed) view rounds, `contracts.ts` replace `rounds: string[]` with `RoundRecord[]`, `App.tsx` `RunningScreen`, `night.css`, `test_logic_impl_split.py` / view test, `App.test.tsx`  
**Steps:**  
1. View builder serializes `logic_statement`, `implementation_delta`, `trial_counters`, verification/PIT flags from engine rounds (same shapes as export).  
2. UI: each round card = two columns (逻辑陈述 | 实现与参数) + line for 候选/通过/第几次尝试.  
3. If loop still produces rounds without these fields, fail closed in serializer (explicit empty deltas) — do not silently drop.  
**Acceptance:** Fixture with counters 15/3/2 renders those numbers; logic `changedFromPrior` shows change description.

### Task 4 — Anomaly checklist presentation (B5 gap)

**Files:** `engine/main.py` (attach anomaly payload on round or completed), reuse `detect_anomalies` in `models.py`, `App.tsx`, `night.css`, `tests/test_anomaly_detection.py`, `App.test.tsx`  
**Steps:**  
1. Compute anomaly server-side for current round; send `AnomalyPresentation | null`.  
2. UI: if present, render checklist (data provenance, coverage shrink, trial count, method revision) **before** conclusion copy; tone checklist not celebration.  
**Acceptance:** Outlier fixture expands evidence block first; no celebratory banner class.

### Task 5 — Method library Scorecard UI (B6 gap)

**Files:** `engine/main.py` methods view, `contracts.ts` `ValidationMethod` (+ dimensions), `App.tsx` `MethodDetail`, `contracts/method-definition.schema.json` (already), tests  
**Steps:**  
1. Include `dimensions[]` + `category` in method list/detail payload.  
2. UI: table of kind/name/threshold/comparison/failure_display; show PIT category badge for `pit.consistency`.  
3. Create/revise flows must require ≥1 dimension (engine immutability already rejects semantic edits in place).  
**Acceptance:** Preset PIT method shows 时点/前视一致性; revising description creates new revision (existing engine rule) and UI states that.

### Task 6 — Coverage-floor confirm specialization (§4.6)

**Files:** `engine/research/coverage.py` / confirm request fields, `engine/main.py`, `App.tsx` awaiting card when `confirmKind==="coverage"`, tests/`test_coverage.py`  
**Steps:**  
1. Payload includes current coverage vs floor delta and suggested options metadata.  
2. UI copy + primary actions: 认下更低底线并开新版 / 提供本机材料 / 缩小范围 / 暂停 — map onto existing resolve decisions + modification path without adding CLI.  
**Acceptance:** Coverage card never looks identical to economic card; auto-continue below floor remains impossible (engine test already).

### Task 7 — Dialogue → confirm-run e2e wiring test

**Files:** `tests/test_dialogue.py` (extend), new desktop test or engine view test, `App.tsx` only if transition bug found  
**Steps:**  
1. Lock five slots via dialogue intents; `fetch_view` returns `kind: confirm_run`.  
2. Desktop: after mocked fetch returns confirm_run, ritual card mounts with cyan CTA.  
**Acceptance:** One engine test + one App test; no silent auto-start without `confirmRun`.

### Task 8 — Reverify revoke visibility (§3.7)

**Files:** `App.tsx` completed screen, `engine/main.py` eligibility after reverify fail, tests/`test_research_record.py`  
**Steps:**  
1. Ensure view sets `reverifiesPassed=false`, `overturnedExports=true`, and PIT/methods flags consistent after fail.  
2. UI disables strategy pack, keeps research-record, shows which method/round failed (pass ids in view).  
**Acceptance:** Reverify fail fixture closes pack CTA immediately; banner text matches product copy.

### Task 9 — Night fidelity pass (non-blocking but scheduled)

**Files:** `night.css`, `App.tsx` list filters chrome, fonts per UI design  
**Steps:**  
1. Demote filters visually (status pills on rows remain source of truth).  
2. Spot-check cyan-only rule, focus column width 640–720, HostStatus strings.  
**Acceptance:** Screenshot or component test: awaiting primary still top; filters not mistaken for IA.

### Task 10 — Native lifecycle verification

**Files:** `apps/desktop/src-tauri/tests/sidecar_lifecycle.rs`, `lib.rs`  
**Steps:**  
1. Run `cargo test` online in CI/dev once.  
2. Assert quit kills owned sidecar; attaching to CLI-owned engine does not kill on tab close (per existing supervisor design).  
**Acceptance:** Documented rust test green in CI; no product change if already correct.

---

## 6. Explicit non-goals (this plan)

- Re-implementing B1–B6 engine types/verifiers/export gates already on `main` (#117) unless a PARTIAL hole above requires a **wiring** fix.  
- Adding CLI capabilities beyond start/status.  
- Trading / broker / paper-trading UI.  
- Cloud sync or multi-user.  
- Pixel-perfect Figma replication beyond Night tokens + structural shell (Task 9 is fidelity, not a redesign).

---

## 7. Suggested sequencing & ownership

```
T0 harness → T1 eligibility/PIT UI → T2 who-pays/evidence UI → T3 round columns
    → T4 anomaly UI → T5 method dimensions UI → T6 coverage confirm UX
    → T7 dialogue confirm-run test → T8 reverify UX → T9 Night polish → T10 rust CI
```

Each task should land as its own PR with pytest and/or App tests green. Prefer under-claiming DONE in PR descriptions until the **desktop path** is demonstrated.

---

## 8. Audit limitations

- No interactive Tauri app / real OS notification observed on this box.  
- Vitest did not execute assertions (infra failure).  
- Cargo tests not run online.  
- Figma nodes not re-fetched; UI fidelity judged from `ui-design-v0_0_1.md` + `night.css`/`App.tsx` only.  
- README on main still describes an “empty skeleton”; ignore for product status — code tree contradicts it.

---

## Appendix A — Canonical symbols (as of `4e74309`)

| Concern | Engine | Desktop |
| --- | --- | --- |
| PIT gate field | `strategy_pack_eligibility` → `failed_checks` incl. `pit_executed_and_passed` (`engine/export.py`) | `ExportEligibilityV2.pitExecutedAndPassed` (`contracts.ts`) — **not rendered** in `CompletedScreen` |
| Who pays | `ConfirmRequest.who_pays_optional` (`engine/research/models.py`) | `ConfirmCardData.whoPaysOptional` — **unused** by `AwaitingConfirmCard` |
| Evidence | `why_change` + `assert_preconfirm_evidence` | `ConfirmCardData.whyChange` — **unused** |
| Trial counters | `TrialCounters` on rounds | `TrialCounters` / `RoundRecord` in contracts — **running view still `rounds: string[]`** |
| Logic/impl split | `LogicStatement` + `ImplementationDelta` | Same TS interfaces — **not rendered** |
| Anomaly | `detect_anomalies` (`models.py`) | `AnomalyPresentation` — **not rendered** |
| OS notify | `notification_event` (`engine/research/progress.py`) | `maybe_notify` / `notification_title` (`apps/desktop/src-tauri/src/commands.rs`) |
| Confirm-run card | view kind `confirm_run` | `ConfirmRunCard` |
| Awaiting card | view kind `awaiting_confirm` | `AwaitingConfirmCard` |
| CSS | — | `apps/desktop/src/night.css` |
