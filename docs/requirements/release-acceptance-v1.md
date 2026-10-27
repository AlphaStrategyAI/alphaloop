# Release acceptance matrix (product) — v1

**Owner:** 产品小马（product acceptance / PASS–FAIL on this matrix）  
**Package-level gate (out of scope here):** 开发小牛 — installers, sha/signing/codesign/SmartScreen on their REPORT, new-feature + main regression, self-test/self-fix, then notify Master Bot. Package sha256, signing, codesign, and SmartScreen verification are 开发小牛's gate and are out of scope for this matrix.  
**Updates on feature change:** 开发小牛 — same PR or follow-up docs PR when UI, copy, gates, or settings change  
**Scheduler:** Master Bot — tag/draft candidate package → **开发小牛 package-level PASS** → **产品小马 full product matrix PASS** (this file) → ask the user to publish  
**SSOT:** this file. Local `/workspace/pm/RELEASE-ACCEPTANCE.md` (if any) must only point here.  
**Related:** [docs/release.md](../release.md) (cut/sign/install), [strategy-families-v1.md](./strategy-families-v1.md), [settings-config-v1.md](./settings-config-v1.md), [i18n-glossary-v1.md](./i18n-glossary-v1.md), [v1-cut-line.md](./v1-cut-line.md)

## Gate rules

1. Order: tag/draft candidate package → 开发小牛 package-level PASS (installers; sha/signing/codesign/SmartScreen on their REPORT; new-feature + main regression; self-test/self-fix; then notify Master Bot) → 产品小马 runs this matrix to full PASS → Master Bot asks the user to publish. Package-level verification is 开发小牛's gate and is out of scope for this matrix.
2. After that package-level PASS, 产品小马 tests the **release-candidate installer** for the tagged commit. About must show that version and that commit.
3. CI green (including `windows-e2e` when present) is an **entry** condition, not product PASS. Prefer real market data; `ALPHALOOP_OFFLINE_MARKET_DATA=1` is allowed only when marked on the case and never substitutes for at least one real-source US and one real-source A-share happy path on the primary platform.
4. Mark each case `PASS` / `FAIL` / `BLOCKED` (environment only). Open **P0/P1 FAIL = release blocked**. P2 FAIL may ship only with an explicit user waiver recorded in the report.
5. Verdict: **全量 PASS** or **有阻塞** (list defects: severity, repro, screenshot path). Master Bot asks the user to publish only after 开发小牛 package-level PASS and 产品小马 **全量 PASS** on this matrix.
6. Platforms: 产品小马 defaults to **Linux deb** full matrix. macOS / Windows: at least install + About + one US happy path, or cite that release’s `windows-e2e` plus a product spot-check. Missing platform = `BLOCKED`, never silent PASS.
7. Evidence: `docs/reports/YYYY-MM-DD-release-vX.Y.Z-product.md` (draft runs may live under `/workspace/v0XY-smoke/` until the template is in-repo).

## How to use the tables

- **Pri:** P0 = blocks publish; P1 = must fix before announcing; P2 = track / waive only with user OK  
- Checkboxes are for the **per-release evidence report**, not for editing this SSOT mid-test.

---

## A. Install and identity

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| A1 | Install candidate | Install Linux deb / Mac DMG / Win setup from the draft release | App installs; launcher present | P0 | Package installs without fatal error |
| A2 | Launch clean | Open alphaloop | Window opens; no traceback; no blocking error banner | P0 | Usable main window |
| A3 | About version | Settings → About (or General About) | Version = release version; Commit = tagged SHA (full or unambiguous prefix) | P0 | Strings match tag build_info |

## B. Language and intake parsing

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| B1 | zh ↔ en chrome | Switch 中文 → English → 中文 → English | English chrome (rail, secrets, confirm, conclusion) has no leftover CJK; typed text may stay Chinese | P0 | No CJK in English chrome |
| B2 | EN time slot examples | English UI; new research; answer effective-time with UI examples `30 minutes` / `12 hours` | Parser accepts; no “couldn't understand” loop | P0 | Examples parse (regresses v0.9.1 #1) |
| B3 | EN methods / coverage examples | Same flow; answer methods and coverage using the English examples shown | Same as B2 | P0 | Examples parse |
| B4 | Single apology | Send one unparseable answer once, then a valid one | At most one apology line per miss | P1 | No doubled “I couldn't understand that” (regresses #2) |
| B5 | ZH slots still work | Chinese answers e.g. `30 分钟`, `至少 N 个` | Still accepted | P0 | ZH path unchanged |

## C. Secrets

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| C1 | Unlocked empty | Open secrets with no passphrase file | Not locked | P0 | Can open |
| C2 | Passphrase round-trip | Create passphrase → quit → launch → unlock | Unlock succeeds | P0 | Round-trip works |
| C3 | Windows credential path | On Windows only: confirm credential-manager path before forcing passphrase file | Matches docs/release.md | P1 | Path behaves as documented |

## D. Research main path and tickers (#152)

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| D1 | US NL → confirm | Thesis naming one US stock (e.g. mean reversion on AAPL) | Confirm card: US · equities (or zh 美股 · …); symbol recognized | P0 | Card correct market/symbol |
| D2 | A-share 600519 → confirm | Thesis `…600519…` / 茅台均值回归 | Confirm: China A-shares / A 股; `600519.SH`; list spacing 「A 股」 half-width space | P0 | Card + glossary spacing |
| D3 | Open card focuses research | From list, open each confirm card | Opens that research | P1 | Correct research focused |
| D4 | Ticker / finance ask | Cases from #152 (suffix, finance abbreviation, mix-remove) | Confirm asks match locked copy; no silent wrong market | P1 | #152 regressions hold |

## E. Strategy family gates (#154 / docs)

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| E1 | Momentum / trend / breakout block | Thesis clearly momentum/trend/breakout | Blocked; **no** “continue as mean reversion”; only user-picked supported family | P0 | No silent MR |
| E2 | Disclose families | Low-vol / fundamental / stock-bond / all-weather (US or A-share as allowed) | Explicit yes (MEAN_REVERSION_ACK) before disclosed MR path; ack buttons only when `show_ack` | P0 | Explicit ack |
| E3 | Unidentified thesis | Unclassifiable thesis | familyFollowUp / chips; never auto MR | P0 | No MR fallback |
| E4 | A-share chips | After decline / pending_non_mr / block on A-share | Chips: mean reversion only (glossary order) | P0 | M2 chip set |
| E5 | US chips | Same on US | Five product family ids in glossary order | P1 | Chip set matches glossary |

## F. Confirm card, data source, Run gating

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| F1 | No source selected | Confirm card with source Not selected / 待选择 | Run disabled; reason N3: 还没选数据源… / No data source selected yet… | P0 | Run blocked + copy |
| F2 | Unlicensed honesty | Pick Yahoo / AkShare (Sina) | Honesty notice + checkbox; Run stays off until ack | P0 | Ack required |
| F3 | Edit keeps source | Select source + ack → Edit a slot → return | Source still selected (or clear re-pick UX without stale ack); no ConcurrentWrite / stuck card (#156) | P0 | Regresses #4 + #156 race |
| F4 | Coverage vs universe floor | One-name thesis + coverage “at least 25” / `至少 25 个` | Run blocked **before** crash **or** mapped localized `UNIVERSE_TOO_FEW_SYMBOLS` (no generic unmapped banner) | P0 | Regresses #3 |
| F5 | Market not from UI language | N4: stock-bond/all-weather unnamed → US funds list; unlocked → 待选择; never infer market from zh/en UI | Matches locks | P1 | N4 holds |

## G. Run → conclusion → export

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| G1 | US real-source run | Yahoo + ack → Run → finish | Conclusion renders; metrics/gates honest; no fake green | P0 | Completes without crash |
| G2 | A-share real-source run | Sina/AkShare + ack → Run → finish | Same; A-share honesty (e.g. T+1 / limit) when applicable | P0 | Completes without crash |
| G3 | PIT copy | On conclusion | PIT text covers dated materials only; does not claim universe/adjustments/revisions | P1 | Copy intact zh+en |
| G4 | Export gates | After gate fail / pass | Research record export allowed as designed; strategy pack only when verification eligible; lock reason clear | P0 | Honest export split |
| G5 | Offline badge (optional) | With `ALPHALOOP_OFFLINE_MARKET_DATA=1` | Test-data badge; not counted as G1/G2 substitute | P2 | Badge visible |

## H. Lifecycle

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| H1 | Delete while running | Delete a running research | Engine process stays up | P0 | Sidecar alive |
| H2 | Persist across relaunch | Quit → launch | Kept research present; deleted absent | P0 | Persistence correct |
| H3 | Uninstall | Uninstall package | App gone | P1 | Clean removal |

## I. Settings

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| I1 | Data sources page | Settings → Data sources | Real data-source UI / locked placeholders only where intentional | P1 | Not blank wrong page |
| I2 | LLM page | Settings → LLM / 大模型 | LLM-specific copy (base URL, API key, model, local) — **not** Data-sources M2 placeholder | P0 | Regresses #6 |
| I3 | EN dashed boxes | English UI workshop + settings | No light dashed rectangle around every text run | P1 | Regresses #5 |
| I4 | Chat field long EN | Long English methods sentence in intake | Readable (wrap or scroll without cutting meaning); Enter submits | P2 | Regresses #7 |

## J. Release regression pack

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| J1 | CHANGELOG / PR delta | Walk user-facing items in this version’s CHANGELOG and merged product PRs | Each named behavior covered by a case above or a new row added this release | P0 | No uncovered ship item |
| J2 | Prior release defects | Re-run open defects from last product report (incl. v0.9.1 #1–#7 until closed) | Fixed stay fixed | P0 | No regressions |
| J3 | #152 ticker corpus | Spot-check #152 cases still green | Pass | P1 | Corpus OK |
| J4 | #156 confirm/source race | Confirm run while ack/source save in flight (or product path that previously ConcurrentWrite) | Confirm proceeds; research running; source saved | P0 | Race fixed |

## K. Shell and navigation

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| K1 | Rail nav | Click 研究 / 方法库 / 术语 | Hash routes work; highlight follows; 1s poll does not kick detail back to list | P0 | Navigation usable |
| K2 | Enter research | Click row / 进入 | `#/research/<id>` shows correct screen for status | P0 | Correct screen |
| K3 | Glossary naming | Open 术语 | Has current glossary names (e.g. 分段稳健性检验 / 集中度); no obsolete primary names 走样检验 / 拥挤度 | P1 | Glossary lock |
| K4 | Route error | Stop engine then change route (or force load fail) | Error + retry, not blank crash | P1 | Recoverable |

## L. Running, continue, and pause

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| L1 | Running chrome | Catch running screen (raise trial budget if needed) | Action capsule; round cards logic vs impl; pause / continue-current / modify+new version controls present | P1 | Controls exist |
| L2 | Continue iterate | After budget exhausted completed: 继续迭代 → confirm → cancel path then OK path | Cancel no-op; OK adds budget, returns running, M increases, thresholds unchanged | P0 | Continue works |
| L3 | High-suspicion second confirm | When cumulative M ≥ high-suspicion threshold | Second confirm required before more iterate | P1 | Second gate shows |
| L4 | Pause / resume | From running or confirm: 暂停 → 按当前版本继续 | Paused state then resume without losing rounds | P0 | Pause/resume |
| L5 | Logic change → new version | Modify economic/logic settings path | Opens new version / awaiting confirm; does not silently burn implement-layer budget | P0 | Version split |

## M. Late-pass and economic confirm

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| M1 | Late-pass prior failures | Completed research that failed then passed later (demo or real) | 「先前未通过轮次」/ late-pass block visible when applicable | P1 | Suspicion UI |
| M2 | Economic confirm who-pays | Hit awaiting_confirm economic path | Who-pays / evidence rules per product design; agree disabled without evidence when required | P0 | Confirm card honest |
| M3 | Coverage confirm specialization | Trigger coverage-floor confirm | Not identical to economic card; actions: lower floor / local materials / shrink scope / pause | P1 | Distinct card |

## N. Methods library

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| N1 | Methods list/detail | Open 方法库 | Definitions readable; immutable published methods; scorecard dimensions if shipped | P1 | Library usable |

## O. Double-run, mixed pool, network, reverify, old data, counters

Cases only. An older M1 inventory is not already PASS.

| ID | Case | Steps (summary) | Expect | Pri | PASS when |
| --- | --- | --- | --- | --- | --- |
| O1 | Double-click Run | Mash Run on confirm | Single run; button disabled / 开跑中…; no 500; no flash back to confirm | P0 | Idempotent Run |
| O2 | Mixed pool sources | US+A symbols | Yahoo + AkShare both shown; confirm does not hammer quotes repeatedly | P1 | Stable confirm |
| O3 | Offline / network error | Unplug or block market → Run | Real error copy, not endless spinner / bare 500; retry after restore works | P0 | Honest network fail |
| O4 | Reverify | Completed → 重新验证 | Refreshes; eligibility flags consistent; no false “prior strategy pack” toast on fail | P1 | Reverify correct |
| O5 | Old DB open | Launch with older research.db if available | History opens; old PIT semantics; missing fields neutral defaults | P1 | No crash on old data |
| O6 | Completed counters | Completed page | 本研究累计 N 轮 + 全局累计; window/cutoff labels; PIT pass vs not-executed distinct | P1 | Counters honest |

## Verdict template (copy into the evidence report)

```text
Release: vX.Y.Z
Candidate commit: <sha>
Package(s) tested: <asset names>
Platforms: …
CI entry: windows-e2e / other = …
Cases: P0 __/__  P1 __/__  P2 __/__
Open FAIL: …
Verdict: 全量 PASS | 有阻塞
Signer: 产品小马
Time (Asia/Shanghai): …
Package-level gate: 开发小牛 REPORT (out of scope for this matrix)
```

## Revision history

| Date | Change |
| --- | --- |
| 2026-10-27 | Initial matrix: A–J without a package checksum row; folds v0.9.1 smoke #1–#7, #152, #154 family locks, #156 ConcurrentWrite / source remember. |
| 2026-10-27 | Gate order: tag/draft candidate package → 开发小牛 package-level PASS → 产品小马 full matrix PASS → Master Bot asks the user to publish. Package sha256, signing, codesign, and SmartScreen stay on 开发小牛's REPORT and are out of scope here. |
| 2026-10-27 | Add K–O (navigation, continue/pause/new version, late-pass and economic/coverage confirm, methods library, double-run / mixed pool / network / reverify / old DB / counters). Inventory is cases only, not prior PASS. |
