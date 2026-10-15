# P0 E2E acceptance report — 2026-10-14

**Branch:** `cursor/p0-v1-honest-path-impl-c923` (PR #124)  
**Plan:** [#123](https://github.com/AlphaStrategyAI/alphaloop/pull/123) @ `428f71c` — decision **(b)** + round-3 advisories  
**Cut line:** `docs/requirements/v1-cut-line.md`

## Executive summary

| Metric | Count |
| --- | ---: |
| 通过 | 48 |
| 失败 | 0 |
| 未测 | 3 |

**Done #1 network (-0.25 default floor):** `ALPHALOOP_ACCEPTANCE_NETWORK=1 pytest tests/test_v1_honest_path.py -v` → **PASSED**. Research reaches **`COMPLETED`** with **not-passed** method verification (`all_current_methods_passed` false); export is **`research_record`** only (not strategy pack). Failed gates: **`scorecard.market`** (max_drawdown -0.324 vs floor -0.25) and **`pit.consistency`**.

**`-0.35` floor:** Exercised only via **economic confirm** (`test_economic_max_drawdown_floor_minus_035_requires_confirm_and_version_history`). Does **not** count toward Done #1.

**Default CI:** `python3 -m pytest tests/ -q` → **195 passed**, 1 skipped (network without opt-in). Desktop vitest **37/37**.

**Data window key for M:** `market|sorted(symbols)|simulation.start|simulation.end` (`DataWindowKey.serialize()` in `engine/research/data_window.py`).

**Implementation trial budget (default 5):** failed verification auto-iterates per version until budget exhausted; UI hint `已用 X/N 轮`; exhausted copy names gates + `research_record` only. Env: `ALPHALOOP_MAX_TRIALS`, `ALPHALOOP_TRIAL_BUDGET_INCREMENT` (default 5).

## Commands run (evidence)

```bash
python3 -m pytest tests/ -q
# 195 passed, 1 skipped

ALPHALOOP_ACCEPTANCE_NETWORK=1 python3 -m pytest tests/test_v1_honest_path.py -v
# test_v1_mean_reversion_reaches_completed_real_ports PASSED (~0.9s)

bash scripts/verify_v1_done.sh
# green when network env unset (skip message)

cd apps/desktop && npm test -- --run
# 37 passed
```

## Done #1 — network at default `max_drawdown_floor=-0.25`

| Field | Value |
| --- | --- |
| Window (frozen) | `2000-01-04` – `2010-12-31` (SPY, yfinance) |
| Status | `COMPLETED` |
| Method verification | **Not passed** (`passed_for` false) |
| Failed verifier | `scorecard.market` (drawdown below default floor) |
| PIT | `pit.consistency` executed, **failed** (no Material `as_of`) |
| Trial counters (concluding round) | `candidates_evaluated=1`, `candidates_passed=0`, `conclusion_attempt_number=1` |
| Export kind | `research_record` (`build_research_record_pack`) |
| `strategy_pack_eligibility.failed_checks` | `all_current_methods_passed`, `pit_executed_and_passed` |

No `-0.35` override in acceptance config or tests.

## Done #1 — `-0.35` via product confirm (not Done evidence)

| Field | Value |
| --- | --- |
| How applied | `EconomicDrawdown35Builder` → `AWAITING_CONFIRM` → `CONFIRM_APPROVE` with `why_change` `EvidenceRef` citing pre-confirm attempt |
| Version history | New version `opened_by=economic_confirm`, `confirmed_changes` includes `("max_drawdown_floor", -0.35)` |
| Trial counters before confirm | `candidates_evaluated=1` on concluding round of v1 |
| Counts toward Done #1? | **No** (product rule) |

Unit test: `tests/test_loop_runtime.py::test_economic_max_drawdown_floor_minus_035_requires_confirm_and_version_history`.

## Optional strategy_pack demo at -0.25

Not run as a separate window hunt. The single frozen acceptance window above **does not** produce a green pack (PIT + scorecard); failure is recorded in the network test assertions and `research_record` export.

## Implementation trial budget (replaces transitional fail-stop)

| Item | Detail |
| --- | --- |
| Semantics | Per-version round budget (`implementation_trial_budget`, default **5** via `ALPHALOOP_MAX_TRIALS`); each committed round counts; thresholds unchanged |
| Auto path | `can_auto_continue_impl_iteration` → `AUTO_CONTINUE` while `used < budget`; else `COMPLETED` not-passed |
| Confirm path | `change_requires_user_confirm` (economic/coverage/`signal_definition`/`feature_set`) → never consumes budget auto path |
| Manual continue | `continue_iterate` adds `ALPHALOOP_TRIAL_BUDGET_INCREMENT` (default **5**) then `run_once` |
| UI copy (running) | `验证未通过：在实现层预算内自动迭代中，已用 X/N 轮。` |
| UI copy (exhausted) | `实现层迭代预算已用尽（X/N 轮）…只能导出 research_record` + gate names |
| Code | `engine/research/honest_stop.py`, `engine/research/loop.py`, `engine/main.py` view fields `trialBudget` / `honestStopHint` |

**Tests:** `tests/test_honest_stop.py` (auto-continue, exhaustion, configurable env, economic still confirms, manual continue); loop tests with `ALPHALOOP_MAX_TRIALS=1`; desktop vitest budget-exhausted hint.

## Cumulative M + B5 late-pass + continue confirm

| Item | Evidence |
| --- | --- |
| Cumulative M in pack/view | `history/rounds.json` fields `data_window_key`, `cumulative_rounds_on_window`, per-round `cumulative_round_on_window`; view `cumulativeRoundsOnWindow` |
| B5 late-pass UI | `latePassPresentation` in `view_for`; `tests/test_cumulative_trials.py::test_late_pass_after_third_round_success` |
| Continue confirm | `user_confirmed` + optional `high_suspicion_acknowledged`; schema + `commands.rs`; vitest escalation |
| Copy | `running_budget_hint` / exhausted hint in `honest_stop.py` |

Command: `pytest tests/test_cumulative_trials.py -v`

## B4 SQLite `resolve_confirm` E2E (not Done #1)

| Item | Detail |
| --- | --- |
| Command | `pytest tests/test_b4_sqlite_confirm.py -v` |
| Path | `ResearchCommandService.handle(resolve_confirm)` + `SQLiteStore.get_attempt` + `-0.35` in v2 `confirmed_changes` |
| Evidence | `why_change` cites pre-confirm `attempt_id`; `who_pays` recorded |
| File | `tests/test_b4_sqlite_confirm.py` |

## Goal matrix (selected)

| ID | Goal | Status | Evidence |
| --- | --- | --- | --- |
| **§2.1 #1** | Real `ResearchLoop` → `COMPLETED` | 通过 | Network test at **-0.25**; completes with not-passed verification |
| **§2.1 #3** | Honest `research_record` when blocked | 通过 | Network test builds `research_record`; names `scorecard.market` + PIT |
| **§2.3** | Real DataPort / MaterialPort | 通过 | Yahoo + `LocalMaterialAdapter` |
| **Plan (b)** | `COMPLETED` uses `passed_for` excluding PIT for **export** | 通过 | `strategy_pack_eligibility`; review no longer requires pass |
| **B4** | `resolve_confirm` + SQLite `get_attempt` + EvidenceRef | 通过 | `tests/test_b4_sqlite_confirm.py` (-0.35 **not** Done #1) |
| **P0 budget** | Auto-iterate until trial budget exhausted | 通过 | `tests/test_honest_stop.py`; `v1-cut-line.md` 已知限制 |
| **B2 cumulative M** | Cross-version rounds on data window in pack + view | 通过 | `tests/test_cumulative_trials.py` |
| **B5 late-pass** | Prior failure records before late pass conclusion | 通过 | `latePassPresentation` + vitest |
| **Continue guard** | Engine + UI confirm flags; high-M escalation | 通过 | `test_continue_*`, desktop vitest |
| **Hash navigation** | `#/research/<id>` / `#/methods` drive `fetchView(route)` | 通过 | `apps/desktop/src/navigation.test.tsx` (jsdom; **not** full Tauri IPC) |
| **Running `honestStopHint`** | Budget / auto-iterate copy on running screen | 通过 | `App.test.tsx` `honest-stop-hint-running` |
| **Confirm/list display** | Chinese universe & coverage; local timestamps | 通过 | `tests/test_desktop_view_format.py`, `format.test.ts`, `App.test.tsx` |
| **§1.2 Desktop** | Vitest + build | 通过 | 37/37; real Tauri window smoke / Night 7-screen **未测** |

## Defects found and fixed (this pass)

| Defect | Fix | Test |
| --- | --- | --- |
| Product rejected silent `-0.35` in acceptance | Removed override; honest complete at -0.25 | `test_v1_mean_reversion_reaches_completed_real_ports` |
| Loop/reviewer blocked Done #1 at default floor | Reviewer + `COMPLETE` on failed PARAM path | `test_failed_method_verification_completes_without_param_iteration` |
| In-floor shrink test relied on failed-verify iteration | Pre-seed `last_coverage`; one passing round | `test_in_floor_shrink_across_rounds_is_recorded_and_can_complete` |
| **BLOCKER:** hash links change URL but UI stays on list | `route` state from hash + `hashchange`; poll `fetchView(route)` | `navigation.test.tsx` |
| Running screen omitted `honestStopHint` | Render hint on `RunningScreen` | `App.test.tsx` |
| Confirm card showed `Universe(...)` / `CoverageFloor(...)` repr | `format_*_display` in `desktop_view.py` → `_settings()` | `test_desktop_view_format.py` |
| List showed raw ISO timestamps | `formatResearchTimestamp` (default `Asia/Shanghai`) | `format.test.ts`, `App.test.tsx` |

## 已知问题（本轮不修）

| Issue | 事实与影响 |
| --- | --- |
| **经济确认 `EvidenceRef` 未填充** | 真实 `ResearchLoop` 进入 `AWAITING_CONFIRM`（经济类）时 `ConfirmRequest.why_change` 仍为空；桌面 `AwaitingConfirmCard` 要求 `whyChange` 非空才启用「同意」，故**真实桌面流程**下经济确认无法批准。SQLite B4 E2E（`tests/test_b4_sqlite_confirm.py`）在 `handle(resolve_confirm)` 前**手工注入** `why_change`，不反映生产路径。影响：经济逻辑变更卡在确认屏。 |
| **Tauri `resources` / PyInstaller** | `tauri.conf.json` 打包 onedir 时目录被拍平；spec 未包含 akshare 数据文件。影响：部分发行包缺数据/资源。 |
| **Crossref 每轮请求** | 文献 crossref 每轮调用，易触发 HTTP 429。影响：运行中断或降级，与导航/UI 无关。 |
| **Engine SQLite 致命退出** | 引擎进程遇 SQLite 错误直接退出且无自动重启。影响：桌面会话需用户重启应用。 |
| **草稿 `universe` 无 `symbols`** | 对话草稿阶段 brief 的 universe 常无 `symbols`，列表/设定仅显示市场·资产类。影响：展示不完整，开跑前需锁定标的。 |

以上均非本轮 1–3 的一行修复项；未为修已知问题扩大范围。

## Open / not fixed in P0

1. **Green `strategy_pack` on live gather** without PIT evidence dates — out of scope for honest path.
2. **Tauri GUI / Night 7-screen manual walk** — re-smoke in real window after hash fix; vitest covers routing contract only.
3. **经济确认 EvidenceRef 管线** — see 已知问题；需引擎在 `REQUEST_CONFIRM` 时写入可追溯引用，桌面 `resolveConfirm` 透传（若需要）。
