# P0 E2E acceptance report — 2026-10-14

**Branch:** `cursor/p0-v1-honest-path-impl-c923` (PR #124)  
**Plan:** [#123](https://github.com/AlphaStrategyAI/alphaloop/pull/123) @ `428f71c` — decision **(b)** + round-3 advisories  
**Cut line:** `docs/requirements/v1-cut-line.md`

## Executive summary

| Metric | Count |
| --- | ---: |
| 通过 | 68 |
| 失败 | 0 |
| 未测 | 3 |

**Done #1 network (-0.25 default floor):** `ALPHALOOP_ACCEPTANCE_NETWORK=1 pytest tests/test_v1_honest_path.py -v` → **PASSED**. Research reaches **`COMPLETED`** with **not-passed** method verification (`all_current_methods_passed` false); export is **`research_record`** only (not strategy pack). Failed gates: **`scorecard.market`** (max_drawdown -0.324 vs floor -0.25) and **`pit.consistency`**.

**`-0.35` floor:** Exercised only via **economic confirm** (`test_economic_max_drawdown_floor_minus_035_requires_confirm_and_version_history`). Does **not** count toward Done #1.

**Default CI:** `python3 -m pytest tests/ -q` → **255 passed**, 1 skipped. Desktop `npm test` → vitest **62/62** + `tsc --noEmit`; `npm run build` green. `apps/desktop/src-tauri`: **cargo check** + **cargo test** (**23** unit/integration tests on Linux VM).

**Data window key for M:** `market|sorted(symbols)|simulation.start|simulation.end` (`DataWindowKey.serialize()` in `engine/research/data_window.py`).

**Implementation trial budget (default 5):** failed verification auto-iterates per version until budget exhausted; UI hint `已用 X/N 轮`; exhausted copy names gates + `research_record` only. Env: `ALPHALOOP_MAX_TRIALS`, `ALPHALOOP_TRIAL_BUDGET_INCREMENT` (default 5).

## Commands run (evidence)

```bash
python3 -m pytest tests/ -q
# 241 passed, 1 skipped

ALPHALOOP_ACCEPTANCE_NETWORK=1 python3 -m pytest tests/test_v1_honest_path.py -v
# test_v1_mean_reversion_reaches_completed_real_ports PASSED (~0.9s)

bash scripts/verify_v1_done.sh
# green when network env unset (skip message)

cd apps/desktop && npm test
# 62 vitest + tsc --noEmit

cd apps/desktop && npm run build
# tsc --noEmit && vite build

bash scripts/build_sidecar.sh && bash scripts/smoke_sidecar.sh
# .venv-sidecar + PyInstaller onedir + bundled akshare calendar (VM)

cd apps/desktop/src-tauri && cargo check --all-targets && cargo test
# 23 passed (runtime root contract + restart loop + supervision lifecycle)

bash scripts/stage_engine_for_tauri.sh
# verify_engine_resource_layout: alphaloop-engine + _internal/ (not flattened)
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
| **B4 real loop evidence** | `REQUEST_CONFIRM` fills `why_change` from pre-confirm attempt | 通过 | `tests/test_economic_confirm_evidence_real_loop.py`, `test_confirm_evidence.py` |
| **Export feedback** | Export returns path; UI shows 已导出到 + reveal folder | 通过 | `test_export_artifact_feedback.py`, `export-feedback.test.tsx` |
| **View repr guard** | No `CoverageFloor(...)` across list/draft/run/confirm/completed | 通过 | `test_desktop_view_repr_guard.py`, `App.test.tsx` |
| **Completed copy once** | Exhausted / not-passed text not duplicated in view/UI | 通过 | `test_completed_view_duplicate_copy.py`, `completed-copy.test.tsx` |
| **Running header idle** | Omit `currentAction` when IDLE; no route flash | 通过 | `test_running_view_idle_action.py`, `route-loading.test.tsx` |
| **Desktop typecheck gate** | `api-bind` + typed vitest fixtures; CI `npm run typecheck`/`build` | 通过 | `test_desktop_typecheck_ci.py`, `.github/workflows/desktop-typecheck.yml` |
| **Stopped-engine polling** | Pause `fetchView` when sidecar `stopped`; `.catch` on polls; resume after 重启 | 通过 | `engine-polling.test.tsx`, `App.tsx` |
| **Runtime vs data roots** | Persistent DB/materials/exports under `user_data_dir`; runtime lock/owner in tmpfs-safe dir | 通过 | `docs/requirements/paths-contract.md`, `EnginePaths`, `test_data_path_migration.py` |
| **Runtime root parity** | Injectable fixture table; `/run/user/<uid>` before temp fallback | 通过 | `runtime_root_cases.json`, `test_runtime_root_contract.py` |
| **Deb bundle metadata** | `bundle.icon`, Finance category, descriptions | 通过 | `test_tauri_bundle_metadata.py`, `tauri.conf.json` |
| **Handshake restart loop** | Startup/handshake failures retry with backoff; cap → stopped + owner clear | 通过 | `sidecar_restart.rs`, `drive_recovery_sync` tests |
| **owner.json on stop/restart** | Clear stale desktop pid when cap exceeded + user restart | 通过 | `engine_paths::clear_owner_file_logged`, `commands.rs`, `test_engine_owner_clear_rust.py` |
| **Sidecar supervision** | try_wait + stdin keepalive; no mutex deadlock on kill | 通过 | `sidecar.rs` integration tests (3), `shared_child_supervision.rs`, `sidecar-ui.test.tsx` |
| **Tauri compile gate** | `on_exit` closure + CI `cargo check`/`cargo test` | 通过 | `test_lib_rs_on_exit_closure.py`, `.github/workflows/desktop-tauri-rust.yml` |
| **Packaging onedir + akshare** | Directory resource map; `.venv-sidecar` build; layout verifier | 通过 | `test_tauri_engine_resource_layout.py`, `verify_engine_resource_layout.py`, smoke scripts |
| **P0 budget** | Auto-iterate until trial budget exhausted | 通过 | `tests/test_honest_stop.py`; `v1-cut-line.md` 已知限制 |
| **B2 cumulative M** | Cross-version rounds on data window in pack + view | 通过 | `tests/test_cumulative_trials.py` |
| **B5 late-pass** | Prior failure records before late pass conclusion | 通过 | `latePassPresentation` + vitest |
| **Continue guard** | Engine + UI confirm flags; high-M escalation | 通过 | `test_continue_*`, desktop vitest |
| **Hash navigation** | `#/research/<id>` / `#/methods` drive `fetchView(route)` | 通过 | `apps/desktop/src/navigation.test.tsx` (jsdom; **not** full Tauri IPC) |
| **Running `honestStopHint`** | Budget / auto-iterate copy on running screen | 通过 | `App.test.tsx` `honest-stop-hint-running` |
| **Confirm/list display** | Chinese universe & coverage; local timestamps | 通过 | `tests/test_desktop_view_format.py`, `format.test.ts`, `App.test.tsx` |
| **unlock_brief schema** | `unlock_brief` in desktop request schema | 通过 | `tests/test_desktop_api_schema_contract.py` |
| **Draft dialogue** | Persisted `dialogue`; off-topic + next_question replies | 通过 | `tests/test_dialogue.py`; vitest duplicate bubbles |
| **Mutation errors** | `bindDesktopApi` refresh + `mutation-error` banner | 通过 | `api-bind.test.ts` |
| **Methods hash / list** | `decodeURIComponent`; latest revision per id; `.active` | 通过 | `routing.test.ts`, `methods-ui.test.tsx`, `test_methods_view_route.py` |
| **Failed gate labels** | Deduped + `PRESET_NAMES` display | 通过 | `tests/test_verifier_display.py`; vitest formatted `failedVerifierIds` |
| **Late-pass paramChanges** | `prior_spec` in review gate → `lookback_days` delta | 通过 | `test_late_pass_after_third_round_success` + `_round_history_with_trials` |
| **review_attempts PK** | Composite `(research_id, attempt_id)` + migration | 通过 | `tests/test_review_attempts_store.py` |
| **Run error pause** | N identical errors → PAUSED + `lastError` | 通过 | `tests/test_run_errors.py`, `last-error.test.tsx` |
| **Delete cascade** | Child rows cleared on `delete_research` | 通过 | `tests/test_delete_research_cascade.py` |
| **research_record B2** | `history/rounds.json` in record export | 通过 | `tests/test_research_record_export.py` |
| **continue_iterate race** | No inline `run_once` in HTTP handler | 通过 | `tests/test_continue_iterate_handler.py` |
| **Running coverage text** | `format_coverage_vs_floor` | 通过 | `test_format_coverage_vs_floor_*` |
| **Completed copy dedupe** | Single exhausted paragraph | 通过 | `test_honest_stop.py` (adjusted) |
| **Draft polish** | Intro order, role classes, thesis strip | 通过 | `draft-polish.test.tsx`, `test_dialogue_intent.py` |
| **§1.2 Desktop** | Vitest + typecheck + build | 通过 | 62 vitest + `tsc`; real Tauri window smoke / Night 7-screen **未测** |

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
| **`unlock_brief` HTTP 400** | Schema enum missing type; mutations show errors + refresh | `test_desktop_api_schema_contract.py`, `api-bind.test.ts` |
| **Draft dialogue mute** | `Research.dialogue` + `process_send_dialogue`; view `dialogue` | `tests/test_dialogue.py` |
| **Methods library** | Hash decode, active link, latest revision only | `test_methods.py`, `methods-ui.test.tsx`, `test_methods_view_route.py` |
| **Empty late-pass `paramChanges`** | Review gate passes `prior_spec` into `build_implementation_delta` | `test_late_pass_after_third_round_success` |
| **Raw duplicate gate ids** | `format_verifier_ids` + dedupe in `_failed_gate_ids` | `test_verifier_display.py` |
| **review_attempts global PK** | Rebuild → `PRIMARY KEY (research_id, attempt_id)`; `get_attempt(..., research_id=)` | `test_review_attempts_store.py` |
| **Silent run loop / ConcurrentWrite** | `apply_run_failure` + PAUSED; `lastError` in view | `test_run_errors.py` |
| **research_record missing rounds.json** | `_round_history_with_trials` in record pack | `test_research_record_export.py` |
| **continue_iterate ConcurrentWrite** | Handler returns after RUNNING transition only | `test_continue_iterate_handler.py` |
| **Economic confirm empty `why_change`** | Loop builds `EvidenceRef` from failed attempt + gate labels | `test_economic_confirm_evidence_real_loop.py` |
| **Export buttons silent** | Tauri returns `path`; completed screen success/error + opener | `test_export_artifact_feedback.py`, `export-feedback.test.tsx` |
| **P1: `npm run build` tsc errors** | `revealExportInFolder` in `api-bind`; `DesktopView` test fixtures | `test_desktop_typecheck_ci.py`, `test-fixtures.ts` |
| **P2: dead-engine poll spam** | Pause view poll when stopped; handle rejections; clear `owner.json` | `engine-polling.test.tsx`, `engine_paths.rs`, `test_engine_owner_clear_rust.py` |
| **A: owner clear no-op without XDG** | Rust `dirs::runtime_dir()` None vs Python `/tmp/runtime-<uid>` | `engine_paths.rs` + `runtime.py` contract |
| **B: stuck restarting on handshake kill** | `schedule_sidecar_recovery` recurses on spawn `Err` | `sidecar_restart.rs` unit tests |

### SQLite scope review (same flaw hunt)

| Table | Key | Verdict |
| --- | --- | --- |
| `review_attempts` | Was global `attempt_id` | **Fixed** (composite PK + migration) |
| `method_usage` | `(method_id, revision_hash, research_id, version_number)` | OK — `research_id` in PK |
| `method_revisions` | `(method_id, revision_hash)` | OK — global method catalog |
| `researches` | `research_id` | OK |
| `engine_errors` | `error_id` AUTOINCREMENT | OK (rows per event, rate-limited) |
| Reverifications / rounds | Inside `state_json` only | N/A |

## Additional P0 — chat draft empty `symbols` (2026-10-17)

| # | Root cause (confirmed) | Fix | Tests |
| --- | --- | --- | --- |
| 1 | `intent._universe()` sets `symbols=()`; confirm had no guard | `ensure_runnable_universe()` at `confirm_run`; static `default_universe_symbols()` for US equity (`PROPOSAL_DATE=2026-10-17`, **pending product sign-off**); confirm view `settings.universe_symbols` | `test_universe_validation.py`, E2E |
| 2 | `RoutingDataAdapter.load_daily(())` — `all(())` is True → CN/AkShare → empty frame | `EmptySymbolsError` (`DATA_SYMBOLS_EMPTY`) before routing | `test_gather_empty_symbols.py` |
| 3 | Run loop surfaced raw `str(error)` (English assertion) | `classify_run_error` + `last_run_error_code` on research + `lastError.code` in running view | `test_run_errors.py`, E2E classified path |
| 4 | Tauri `error_for_status()` dropped engine JSON body; modify while running opaque | `parse_engine_error_body`; `RUNNING_CANNOT_MODIFY`; UI hides modify when `status=running`; lifted paused modification state in `App` | `commands.rs` unit test, `App.test.tsx`, `api-bind.test.ts` |
| 5 | `unlock_brief` cleared all five locks | Optional `slot` on `unlock_brief`; per-slot「改一改」on confirm card | `test_dialogue.py`, `test_engine_http_errors.py` |

**Default universe proposal (technical):** static US large-cap / broad ETF list (`SPY`, `QQQ`, `IWM`, `DIA`, `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`) in `engine/research/default_universe.py`. **Trade-offs:** static list is deterministic and offline-testable but drifts from index membership; live constituent fetch needs network, caching, and product rules for delistings. **Sign-off:** 产品小马 — list marked `pending product sign-off` until approved.

**E2E:** `tests/test_draft_confirm_run_e2e.py` — `create_draft` → dialogue lock sequence (no hand-built brief) → `confirm_run` → `ResearchLoop.run_once` with `FakeBuilder`; asserts `SPY` in symbols and no `prices must be non-empty`.

## 已知问题（本轮不修）

| Issue | 事实与影响 |
| --- | --- |
| **Crossref 每轮请求** | 文献 crossref 每轮调用，易触发 HTTP 429。影响：运行中断或降级，与导航/UI 无关。 |
| **Tauri 发行包端到端** | Linux VM：`cargo check`/`cargo test` + staged onedir layout；**未**运行 `tauri build` 安装包、**未**验证 macOS/Windows bundle、**未**开真实 Tauri 窗口端到端。 |
| **(a) 对话关键词解析器** | `engine/dialogue/intent.py` `interpret`：thesis 需一条里带市场+资产；时间只认「N 小时」；锁定需「锁定」+槽位词同句；覆盖底线三项缺一不可。建议：按当前提问槽填值、答后自动锁定、系统提示示例、识别分钟/半小时。 |
| **(b) 右侧研究设定只读** | 草稿/确认右侧 `Settings` 仅展示，不能在面板内直接编辑。 |
| **(c) 对话底部被输入框遮挡** | `night.css` `.conversation` 无 padding-bottom/内滚动，绝对定位表单盖住最后一条气泡。 |
| **(d) 方法库详情** | 原始 JSON；计分卡表头英文键；revision 截断；「编辑为新定义」无确认即新版本。 |
| **(e) 原生 `window.confirm`** | Tauri/WebKit 英文按钮与 `JavaScript - tauri://localhost#/research` 标题。 |
| **(f) 引擎状态与窗口尺寸** | 左下角引擎状态文案截断；最大化后内容区约 960×650。 |
| **(g) 新建研究不自动打开** | 列表新增一行但不导航到该研究。 |

以上均非本轮的一行修复项；未为修已知问题扩大范围。

## Open / not fixed in P0

1. **Green `strategy_pack` on live gather** without PIT evidence dates — out of scope for honest path.
2. **Tauri GUI / Night 7-screen manual walk** — re-smoke in real window after hash fix; vitest covers routing contract only.
3. **经济确认 EvidenceRef 管线** — see 已知问题；需引擎在 `REQUEST_CONFIRM` 时写入可追溯引用，桌面 `resolveConfirm` 透传（若需要）。
