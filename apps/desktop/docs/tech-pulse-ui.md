# Tech Pulse UI (desktop)

Visual layer aligned with 设计小迪 Figma **Tech Pulse v003** (`night.css` + `tech-pulse.css`).

## Tokens

| Token | Value | Use |
|-------|-------|-----|
| void | `#07090C` | App background |
| ink | `#E8EEF5` | Primary text |
| cyan | `#5EEAD4` | Confirm / export accents |
| pulse | `#60A5FA` | Running orbit, quota meter |
| line | `#1E2530` | Borders |

## Motion

- UI transitions: `0.32s ease-out` (`--motion-fast`)
- Orbit “breathing”: `3.6s` (`--orbit-breathe`), disabled when `prefers-reduced-motion: reduce`
- Hover: border/glow only (no scale on press)
- **Run-start ritual** (~500ms): when view transitions `confirm_run` → `running`, applies `.run-start-ritual` on the shell (atmosphere fade-in) and `.run-start-ritual-running` on the running panel (orbit entrance). Skipped entirely when `prefers-reduced-motion: reduce`. No fake progress or invented metrics.

## Brand

Sidebar uses `src/assets/brand-icon-{96,192}.png` (from v2 transparent master). Tauri bundle icons under `src-tauri/icons/` are unchanged.

## Layout (v003 alignment)

- Main column: `max-width: min(1120px, calc(100% - 48px))` on `.tech-pulse-content`; focus cards ~720px centered.
- Atmosphere orbs (teal confirm, blue running, red failed) scale with viewport; centered behind cards.
- Minimum usable width **1024×640**; list and focus screens remain scrollable.

## Sidebar rail status

Bottom of rail: **one line** — status dot + short copy from real view state (`railStatus.ts`):

| View / list signal | Copy |
|--------------------|------|
| `awaiting_confirm` or list `awaiting` pin | 等确认 |
| `confirm_run` or list row `confirm_run` | 确认开跑 |
| `running` (not paused) | 运行中 |
| `running` paused | 已暂停 |
| `completed` | 已完成 |
| Idle list (no active signals) | hidden |

Engine line (“引擎：运行中”) is no longer shown in the rail; engine health stays in tooltips/title when a rail label is present.

**Bare rail (v003):** `.host-status.rail-status` overrides the default glass chip (`.night-shell.tech-pulse-shell .host-status`) so the dot + label sit directly on the rail.

## Glossary

`#/glossary` reuses `.tech-pulse-card` and a `<details>` fold. Copy comes from the engine glossary (`docs/GLOSSARY.md`), not from a second set of labels in the desktop.

## Research list

- Header: **+ 新建研究** (`data-testid="new-research-button"`).
- Pinned cyan cards when `view.awaiting` or a `confirm_run` row exists; **打开确认卡** deep-links to the research.
- Row pills: 草稿 / 运行中 / 等待确认 / 已暂停 / 已完成 / 未通过 (`listStatusDisplay.ts`); `ended` rows use `.research-row--failed`.
- Gate-failed studies still `ResearchStatus.COMPLETED` in the store list as **`ended`** via `list_row_status()` (strategy pack not eligible) so the pill is red **未通过**, not green **已完成**.
- `.row-actions` uses `flex-shrink: 0`, `nowrap`, and `min-width` so **进入 · 删除 · pill** stay horizontal; titles wrap/truncate instead.

## Confirm to run

- Primary **开跑** (`confirm-run-start`); secondary **再修改** calls `api.unlockBrief(researchId)` with no slot → engine `unlock_all_slots` (same as unlocking every slot from draft/confirm).
- Policy copy in `<details>`; lead line keeps lock semantics.
- **将使用的数据** nested panel (`confirm-data-panel`) with **展开看全表**; AkShare / date range / universe summary unchanged from engine payload.

## Running

- Orbit: `v{version}` + current stage label when `currentAction` is not `idle`.
- **有效研究额度** progress bar when `parseEffectiveQuotaFromView(effective, remaining)` can derive used/total (slash form or `N 小时` + `剩余`); hidden when unknown. Track height **10px** (visible fill, not a hairline).
- Running atmosphere: layered blue radial disc upper-left (stronger than default wash); respects `prefers-reduced-motion` for animations only.

## Completed / failed

- Single focus card (`completed-focus-card`): success eyebrow “Export ready · 四关全绿”; failed eyebrow `COMPLETED · 未通过门禁`.
- Failed: primary **导出研究记录** (coral) only — no duplicate cyan **导出研究记录包**; export success/error feedback via `ExportOutcomeMessages`. **导出策略包（未解锁）** disabled. Reverify / 改策略再跑 in **collapsed** `<details>` by default (failed path).
- Failed atmosphere: large soft **red** disc on `.tech-pulse-atmosphere` when `viewContentFailedTone()` is true (gate-failed `completed`, not only `status: ended`). Matches running orb scale/opacity; `data-atmosphere-tone="failed"` for tests.
- Success: primary **导出策略包** when all four eligibility gates pass; more actions collapsed under **更多操作**.

## Regenerate web brand assets

From repo root, resize the transparent master with Pillow or replace PNGs manually after design delivery.

## Tests

`src/tech-pulse-ui.test.tsx`, `src/railStatus.test.ts`, `src/effectiveQuota.test.ts`, and updated `App.test.tsx` cover rail copy, list pills/pinned card, confirm actions/data panel, quota parsing, failed export buttons, ticker nowrap, and run-start ritual.
