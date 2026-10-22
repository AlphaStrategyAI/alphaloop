# alphaloop Night Figma vs Desktop App — Gap Audit

**Date:** 2026-09-22 (Asia/Shanghai, CST)  
**Scope:** `main` @ `4e74309` (`feat: Implement alphaloop B1–B6 product nails (#117)`)  
**Figma:** [JXelV0rnUUv5U5w9ur7jtk](https://www.figma.com/design/JXelV0rnUUv5U5w9ur7jtk) · page `Screens` (`0:1`) · Night / Dark  
**Contract:** `docs/requirements/ui-design-v0_0_1.md` (present on main)  
**Code read:** `apps/desktop/src/App.tsx`, `night.css`, `contracts.ts`; `engine/main.py` view builders + `/commands`; Tauri `commands.rs`  
**Shots:** `/workspace/figma-shots/01`–`07` (live MCP downloads, 1440×900)

**Verdict (honest):** The Night shell and seven screen *routes* exist. Most screens are **SKELETON** — they render thin data from `fetch_view`, not Figma card layouts / iteration depth / method detail. The product loop is closer to “engine works headless; desktop is a thin control panel” than a finished Night UI. User saying “pages basically not implemented” is fair for running / completed / methods / draft thread content.

Status legend:
- **DONE** — present in App with Figma-aligned role and wired command
- **SKELETON** — screen/region exists but content, density, or copy differs materially from Figma
- **MISSING** — Figma region/control absent from App (or engine view never supplies it)

Backend legend (for missing / thin controls):
- **YES-UNWIRED** — engine already has command and/or model fields; view or UI omits them
- **NO-BACKEND** — no durable engine path yet (or view hardcodes empty)

---

## Shared shell (all seven screens)

| Figma / ui-design element | App.tsx / night.css | Status | Backend |
|---|---|---|---|
| Rail width **148px**, void bg, 1px `line` right | `.rail` 148px, border-right `var(--line)` | **DONE** | n/a |
| Logo **148×148** square, α + ink dot | `.logo` 148×148 | **DONE** (CSS α; not Figma component asset) | n/a |
| Logo+Nav vertically centered as a group | `.rail-center` `top:50%; translateY(-50%)` | **DONE** | n/a |
| Nav: 研究 / 方法库; selected glass+hairline | `<nav>` + `.active` | **DONE** | n/a |
| HostStatus bottom: 等确认 / 本机静 / 运行中 / 已完成 | `hostStatusLabels` + colored classes | **DONE** | YES — `hostStatus` from `view_for` |
| Night tokens void/glass/ink/mute/line/cyan/run/ok/stop/hold | `:root` in `night.css` | **DONE** | n/a |
| Cyan **only** on awaiting + confirm-run | Glow on `.content.confirm_run/.awaiting_confirm`; cyan CTAs; awaiting primary border | **DONE** vs written contract (Figma 06 uses cyan on completed title/CTA — app correctly prefers `ok` per ui-design) | n/a |
| Glow* atmosphere ellipses | Radial gradients on confirm screens only; no GlowRun/GlowOk/GlowLib | **SKELETON** | n/a (CSS) |
| SMART_ANIMATE ~0.32s EASE_OUT route transitions | `transition` on buttons/links only; no route morph | **MISSING** | n/a |

---

## 1. Per-screen: Figma vs App

### 01 · 研究列表 · node `1:119`

| Figma element / region | App | Status |
|---|---|---|
| Browse layout, content eats remaining width | `.browse.list-screen` | **DONE** |
| Intro copy 「一条对话，一次研究…」 | Present | **DONE** |
| 「新建研究」 control | `quiet-button` → `createDraft` | **DONE** (visual weight quieter than some Figma frames) |
| Awaiting **primary card** (cyan border + glow, “待你确认”, title, universe · waited) | `.awaiting-primary` + breath animation | **SKELETON** — no “待你确认” eyebrow; shows StatusPill + 进入/删除; fallback 「等了 2 小时」 when `createdAt` missing |
| Ordinary rows + status pills (运行中/草稿/已暂停/已完成/已结束) | `.research-row` + `StatusPill` | **DONE** |
| Row actions 进入 / 删除 | Links + `confirmDelete` | **DONE** |
| Filters as **non-primary** leftover layer | Six filter chips always shown; `?status=` fetch | **SKELETON / wrong emphasis** — violates ui-design §列表 |
| Empty list state | None | **MISSING** |
| Page title 「研究」 in content | Intentionally omitted (ui-design: don’t re-title) | **DONE** (matches contract; some older shots titled) |

### 02 · 草稿 · node `12:13`

| Figma element / region | App | Status |
|---|---|---|
| Chat column + 240px settings rail | `.draft-layout` 1fr / 240px | **DONE** |
| Title 「新研究」 | `<h1>` | **DONE** |
| Thread bubbles (user + system) | `view.messages.map` + hard-coded system line | **SKELETON** — engine always returns `messages: []` |
| Composer placeholder 「把方向说清楚…」 | Present | **DONE** |
| 研究设定 five slots + 「未锁定」 | `Settings` / `settingLabels` | **DONE** |
| GlowDraft atmosphere | None on draft | **MISSING** |

### 03 · 确认开跑 · node `5:32`

| Figma element / region | App | Status |
|---|---|---|
| Focus centered ritual card, cyan border/glow | `.focus` + `.confirm-card` | **DONE** |
| Title + ritual copy (autonomy / effective-time) | Three `<p>`s | **SKELETON** — copy present but not pixel-matched |
| Five settings as **in-card rows** (label \| value) | Nested `<Settings>` restyled | **DONE** role / **SKELETON** density |
| Solid cyan 「确认开跑」 | `cyan-button` → `confirmRun` | **DONE** |
| 「再改改」 secondary | `<a href=#/research/…>` | **SKELETON** — does not force draft view if slots still locked (engine flips to confirm_run when locked) |

### 04 · 运行中 · node `9:13`

| Figma element / region | App | Status |
|---|---|---|
| Focus ~720 column | `.focus.running-screen` width 720 | **DONE** |
| Strip: 运行中 · 第 N 版 · 动作 · 有效研究 a / b · 覆盖 · 暂停 | header + StatusPill + pause | **SKELETON** — no `3h12/12h` paired budget string as designed; pause not inline on strip |
| Large title 「迭代与验证」 | `<h1>` | **DONE** |
| Round cards: tag · summary · verification line | `rounds: string[]` → title only + stub sentence | **SKELETON** — no logic/impl columns, no trial counters, no verification result line from data |
| Materials / data note block | `.materials-note` (sources, cutoff, coverage) | **SKELETON** — product-useful but **not** on Figma 04 |
| Paused: resume + modify+new version | Present | **DONE** (extra vs Figma frame which shows running) |
| GlowRun | Missing | **MISSING** |

### 05 · 等待确认 · node `6:61`

| Figma element / region | App | Status |
|---|---|---|
| Focus 640 cyan card | `.awaiting-card` width 640 | **DONE** |
| Eyebrow: 等待确认 · 第 N 版 · 不计入额度 (+ budget in Figma) | Eyebrow without `有效研究 a/b` | **SKELETON** |
| Title economic vs coverage | `confirmKind` branch | **DONE** |
| Three blocks: 改什么 / 为什么 / 变成什么样 | `proposed` / `reason` / `effect` | **DONE** |
| Three decisions (approve / reject / pause) | `decision-stack` → `resolveConfirm` | **DONE** |
| Who-pays / evidence refs (product B4; not on Night frame body) | Absent | **MISSING** (vs product; Figma Night shows three blocks only) |
| Cyan glow atmosphere | Parent `.content.awaiting_confirm` gradient | **DONE** |

### 06 · 已完成 · node `10:13`

| Figma element / region | App | Status |
|---|---|---|
| Centered focus + result card | `.completed-screen` + `.result-card` | **SKELETON** |
| 「已完成」 + 「可导出实盘交接…不去下单」 | StatusPill + shorter no-trade copy | **SKELETON** |
| Three eligibility pills (methods / no confirm / reverify) | Three spans; **ignores** `pitExecutedAndPassed` | **SKELETON** vs Figma-3; **MISSING** 4th gate vs engine export |
| Strategy title + universe blurb | Title + hard-coded 「美股 · 股票 · …」 | **SKELETON** |
| Primary 「导出策略包」 | Button (not cyan solid; uses glass) | **SKELETON** |
| 「对某一步重新验证」 | Present → `reverify` | **DONE** |
| 「导出研究记录包」 | Present (not on Figma 06 primary) | Extra vs Figma; product-ok |
| Overturned banner / extend / modify | Present | Extra product chrome |
| GlowOk | Missing | **MISSING** |

### 07 · 验证方法库 · node `11:13`

| Figma element / region | App | Status |
|---|---|---|
| Rail + 260 list + detail | `.methods-layout` 260px / 1fr | **DONE** |
| 「新建」 chip | Inline create form 「预先新建方法」 | **SKELETON** |
| Immutability blurb | Present | **DONE** |
| List rows: name + 「预置」 / 「来自 {research}」 | name + `revision` hash + usageCount | **SKELETON** — `source` / `depositedFromResearchId` returned by engine but unused in TS/UI |
| Detail: title, description, 「用过的研究」 titles, edit note | description + usageCount + revise button | **SKELETON** — no research title list; no Scorecard dimensions / PIT category |
| GlowLib | Missing | **MISSING** |

---

## 2. Backend: missing / thin UI ↔ engine

Engine API types handled in `ResearchCommandService.handle` (also exposed via Tauri):  
`fetch_view`, `create_draft`, `create_method`, `list_methods`, `revise_method`, `delete_research`, `send_dialogue`, `confirm_run`, `pause`, `resume`, `confirm_modification`, `extend_research`, `resolve_confirm`, `reverify`, `export_artifact`.

| Missing / thin UI control | Engine already? | Classification |
|---|---|---|
| Draft conversation transcript in view | `send_dialogue` updates slots only; `view_for` hardcodes `messages: []`; no turn store | **NO-BACKEND** (transcript) |
| Confirm-run 「再改改」 → unlock draft | Slots stay locked → view stays `confirm_run` | **NO-BACKEND** (or needs unlock/edit command) |
| Running round cards: logic / impl / trials / verify line | Models have `logic_statement`, `implementation_delta`, `trial_counters`; view emits `spec.id` strings | **YES-UNWIRED** |
| Running strip paired budget `used/max` | `_remaining` + `effective` exist separately | **YES-UNWIRED** (compose in view/UI) |
| Awaiting who-pays + evidence refs | `ConfirmRequest.who_pays_optional`, `why_change`; view omits; `resolve_confirm` ignores who-pays body | **YES-UNWIRED** (models) / partial **NO-BACKEND** on resolve payload |
| Awaiting budget line on card | Effective clock on research | **YES-UNWIRED** |
| Completed 4th eligibility PIT | `strategy_pack_eligibility` + `ExportEligibilityV2.pitExecutedAndPassed`; completed view emits 3 bools | **YES-UNWIRED** |
| Completed real subtitle / universe copy | Brief fields available | **YES-UNWIRED** |
| Method 「预置」 / 「来自 …」 labels | View already sends `source`, `depositedFromResearchId` | **YES-UNWIRED** |
| Method 「用过的研究」 title list | `list_method_usage` exists; view only aggregates `usageCount` | **YES-UNWIRED** |
| Method Scorecard dimensions / PIT | Engine methods + schemas; not in desktop view | **YES-UNWIRED** |
| Anomaly checklist UI | `detect_anomalies` + CSS `.anomaly-*`; App never mounts | **YES-UNWIRED** |
| List empty state | None required | **NO-BACKEND** (pure UI) |
| Demote list filters | Filter API already optional | **NO-BACKEND** (UI policy fix) |
| Route SMART_ANIMATE | n/a | **NO-BACKEND** (UI) |

---

## 3. Top severity (ruthless)

1. **Draft thread is fake** — Figma’s core draft experience is a conversation; App always paints an empty thread because `engine/main.py` sets `"messages": []` and dialogue never stores turns.  
2. **Running “迭代与验证” is a string dump** — Figma shows structured round cards; App maps `rounds: string[]` of attempt ids with a stub verification sentence. B2/B3 richness sits in models/contracts unused.  
3. **Completed eligibility lies about export readiness** — UI/view show three gates; engine export enforces four including PIT. Users can think they are eligible when pack export will fail (or never learn why).  
4. **Method library is a CRUD stub vs Figma detail** — No 预置/来自 labels, no 「用过的研究」 list, no Scorecard — despite engine returning `source` / usage helpers.  
5. **List filters contradict Night contract** — ui-design: Filters must not be primary; App exposes six chips as main chrome.  
6. **Awaiting card is the closest screen, still incomplete vs product** — Night three-block + three decisions are wired; B4 who-pays / evidence not projected (view strip).  
7. **Confirm-run 「再改改」 dead-end when slots locked** — Link reloads same `confirm_run` view; no unlock path.  
8. **Atmosphere / fidelity debt** — Glow* per screen, cyan CTA hierarchy on completed, strip layout, and route motion largely absent; shell geometry (148 rail/logo) is the rare strongly DONE piece.

---

## 4. Recommended fix order

**Prefer: wire existing engine → UI fidelity on already-wired screens → new backend only where blocked.**

1. **Project rich view payloads (highest leverage, YES-UNWIRED)**  
   - Completed: four eligibility booleans from `strategy_pack_eligibility`  
   - Running: `RoundRecord[]` from model rounds  
   - Methods: surface `source`, deposited-from title, usage research titles  
   - Awaiting: optional who-pays + whyChange if product wants B4 on Night card  

2. **UI fidelity pass on shells that already have data**  
   - List: demote/remove filter chips; add 「待你确认」 eyebrow; empty state  
   - Confirm-run / awaiting: match Figma card density and strip/eyebrow budget line  
   - Completed: Figma copy + primary CTA weight using `ok` (not cyan, per token contract)  
   - Methods: Figma list/detail chrome  

3. **NO-BACKEND blockers**  
   - Persist draft dialogue turns (or synthetic assistant replies) so Draft matches Figma  
   - 「再改改」 unlock / return-to-draft when slots locked  
   - `resolve_confirm` accept who-pays when collecting it  

4. **Polish last**  
   - Per-screen Glow*, SMART_ANIMATE 0.32s, list breath already partly done  

**Do not** rebuild B1–B6 engine nails; they are largely on main. The gap is projection + Night presentation.

---

## Evidence index

| Artifact | Location |
|---|---|
| Figma shots | `/workspace/figma-shots/01-research-list.png` … `07-methods.png` |
| App | `apps/desktop/src/App.tsx` (~382 LOC) |
| Tokens | `apps/desktop/src/night.css` |
| TS contracts | `apps/desktop/src/contracts.ts` (`RoundRecord`, `ConfirmCardData`, `ExportEligibilityV2` unused by live views) |
| View builder | `engine/main.py` `view_for` ~302–416; `messages: []` @346; eligibility 3 fields @400–411; rounds as ids @363 |
| Commands | `engine/main.py` `handle` ~418–664; Tauri `apps/desktop/src-tauri/src/commands.rs` |
| UI contract | `docs/requirements/ui-design-v0_0_1.md` |
