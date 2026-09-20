# alphaloop E2E Gap Audit & Fix Plan

**Date:** 2026-09-20 (Asia/Shanghai)  
**Scope:** `main` @ `4e74309` (`feat: Implement alphaloop B1–B6 product nails (#117)`)  
**Sources of truth (priority):**  
1. `docs/requirements/product-positioning.md`  
2. `docs/requirements/product-design-v0_0_1.md` (§3.1–3.8, §4.x, B1–B6 nails)  
3. `docs/requirements/ui-design-v0_0_1.md` (Night shell / seven screens)  
4. `docs/plans/2026-09-20-alphaloop-tech-design-b1b6.md` (engine/desktop contracts for B1–B6)

**Method:** Shallow clone of `AlphaStrategyAI/alphaloop`, inventory `engine/` `apps/` `tests/` `contracts/`, run pytest + desktop typecheck/vitest, read view builders and UI screens. Claims below are under-claimed: DONE only when both behavior and user-visible path exist with file evidence.

SEE FULL PLAN AT WORKSPACE PATH `/workspace/alphaloop-e2e-gap-and-fix-plan.md` (21803 chars). This remote stub will be replaced; opening PR now with note that full body is in the local workspace file and will be force-updated.

## Test results (summary)

- Engine pytest: **158 passed**
- Desktop vitest: FAIL (infra)
- Desktop typecheck: FAIL (missing `pitExecutedAndPassed` in fixtures)
- Cargo: FAIL offline

## Top gaps

1. Completed eligibility UI/view still 3 gates (PIT missing in view)
2. Awaiting-confirm missing who-pays + evidence refs
3. Running rounds are string[] not two-column + trial counters
4. Anomaly UI not mounted
5. Method library ignores Scorecard dimensions
6. Coverage confirm title-only
7. Desktop harness red
8. Dialogue→confirm-run under-tested
9. Night filter chrome vs IA
10. Engine richness not projected to desktop API

## Fix plan

Tasks 0–10 in workspace file: harness → PIT UI → who-pays → rounds → anomaly → methods → coverage → dialogue test → reverify → Night → rust CI.
