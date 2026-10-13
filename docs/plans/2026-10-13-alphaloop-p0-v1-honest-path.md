# AlphaLoop P0 — V1 诚实 MeanReversion 路径 技术实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans，按任务逐步执行。步骤使用 checkbox（`- [ ]`）跟踪。

> **修订 2026-10-13（[review 5498781600](https://github.com/AlphaStrategyAI/alphaloop/pull/123#pullrequestreview-5498781600)）：** 对照 main 修正三处实施阻塞。（1）`pit.consistency` **没有**接进 `run_verifiers`；T5 先接线再测导出，Done #3 / B1 不能只靠手插结果。（2）T3 必须改 `engine/research/models.py`，把 `Version.rounds` 收成 `RoundV2`。（3）`who_pays` 走桌面 invoke → `commands.rs` → `desktop-api.schema` → 引擎；持久落点只有新版本的 `confirmed_changes`。

> **修订 2026-10-13 round 2（[review 5500730280](https://github.com/AlphaStrategyAI/alphaloop/pull/123#pullrequestreview-5500730280)）：** 锁定决策 **(b)**。§2.1 Done #1 的 `COMPLETED` 不要求 PIT 通过。PIT 仍在 `run_verifiers` 里每次执行（B1）。review / `DeterministicReviewer` / `ResearchLoop` 完成分支用 `verification.passed_for(method_set)`，**排除** `pit.consistency`，不用全结果的 `.passed`。导出仍单独看 `pit_executed_and_passed`。`all_current_methods_passed` 与完成口径相同，避免和第四关双计。P0 不发明 Material 决策日（不用 `fetched_at`，不用 cutoff 回填）。缺 as_of → PIT 已执行且失败，只挡住 `strategy_pack`。

**Goal:** 在**不新开第二条研究路径**的前提下，让 V1 唯一承诺的诚实端到端（MeanReversion + 现有 `RoundBuilder` / `ResearchLoop`）满足 [V1 交付收口 §2.1](../requirements/v1-cut-line.md#21-可测-done) 五条可测 Done；工作台数据来自真实闭环，review 关由确定性 reviewer 兜底，导出四门栏 + PIT 全链成立。

**Architecture:** 生产侧继续 `engine/main.py::build_loop` → `DefaultRoundBuilder`（gather→specify→simulate→`run_verifiers`）→ `ResearchLoop.run_once` → `run_review_gate`（`ReviewerPort`）→ `transition`。P0 只补齐：**(1)** V1 路径选用确定性 `ReviewerPort`；(2) 轮次产物写入 store 的 B2/B3 字段并经 `ResearchCommandService.view_for` 诚实映射到 Night 七屏已有槽位；(3) 一条带真实 `MaterialPort`/`DataPort` 的验收路径（CI 其余仍 fixture）；(4) `run_verifiers` 每次执行 `pit.consistency`；`COMPLETED` 不要求它通过（决策 (b)）；导出仍用 `strategy_pack_eligibility` + `build_strategy_pack` / `build_research_record_pack` + `contracts/strategy-pack.schema.json`，第四关单独计。

**Tech Stack:** Python 3.12, pandas, NumPy, httpx, yfinance, akshare, SQLite, jsonschema, pytest; Tauri 2 + React + TypeScript（仅数据填充，不改 Night IA）

## Global Constraints

- **收口文档为准：** [docs/requirements/v1-cut-line.md](../requirements/v1-cut-line.md) §2.1–2.3、§3、§5；行为细节仍以 [product-design-v0_0_1.md](../requirements/product-design-v0_0_1.md)（B1–B6、§3.7 四条资格 + PIT 第四关）为准；壳层 [ui-design-v0_0_1.md](../requirements/ui-design-v0_0_1.md) 七屏不重设计。
- **单路径契约：** `RoundBuilder` / `DefaultRoundBuilder` / `ResearchLoop`；`VerifierResult` / `PitVerifierResult` / `pit.consistency`；`strategy_pack_eligibility` / `build_strategy_pack`；`contracts/strategy-pack.schema.json`（`live_handoff_eligible: true`）。
- **MeanReversion 导出硬约束：** `engine/export.py::build_strategy_pack` 仅接受 `MeanReversionStrategy`（已存在 `TypeError` 守卫）。
- **不下单、不接券商：** 策略包可含 `ExecutionPort` / `NotImplementedBroker` 占位；不交付券商执行器。
- **数据口 §2.3：** CI 可用 fixture；**至少一条被接受的验收路径**必须走真实 `DataPort` / `MaterialPort`（`engine/research/gather.py` 已有 crossref / SEC / `LocalMaterialAdapter` + `RoutingDataAdapter(YahooDataAdapter, AkShareDataAdapter)`）。
- **外部 LLM 不得卡住 V1 Done：** §2.1 Done #5 — 诚实路径钉确定性 reviewer（固定 Pass/Fail），`SubagentReviewer` 可保留给非 V1 / 后续期，但不得阻塞 P0 验收链。
- **决策 (b)：** Done #1（`COMPLETED`）与 Done #3（`strategy_pack`）分开。完成看 scorecard + `method_set`（排除 `pit.consistency`）。PIT 每次都执行，只进入第四关 `pit_executed_and_passed`。不把 `Material.fetched_at` 或回测 cutoff 写成 as_of。
- **界面：** 仅在真实字段无槽位时改 desktop；不为 V1 做 Night 视觉大改；小迪仅补槽位。

**本文不替代产品行为定义**；只描述 P0 工程如何落到现有契约上。产品想象段落是否已交付，以 v1-cut-line 必达与 §2.1 为准，不以本计划扩 scope。

### 交叉引用

| 文档 | 用途 |
| --- | --- |
| [v1-cut-line.md](../requirements/v1-cut-line.md) | 必达、§2.1 Done、§2.3 数据口、缓做/非目标 |
| [product-design-v0_0_1.md](../requirements/product-design-v0_0_1.md) | B1–B6、§3.7 四条可实盘资格（+ PIT） |
| [2026-09-20-alphaloop-tech-design-b1b6.md](./2026-09-20-alphaloop-tech-design-b1b6.md) | B1–B6 已 largely 接线；本计划是 V1 诚实路径收口 |
| [2026-08-28-alphaloop-implementation-plan.md](./2026-08-28-alphaloop-implementation-plan.md) | 基线引擎/桌面架构（冲突时以 v1-cut-line + 本计划 P0 为准） |

---

## 现有架构与契约（禁止第二条路径）

```text
confirm_run → RUNNING
  ResearchLoop.run_once (engine/research/loop.py)
    DefaultRoundBuilder.build / retry
      gather(material_ports) → specify → simulate_daily(data_port) → run_verifiers
    run_review_gate(draft, reviewer, builder.retry)  # engine/review/subagent.py
    transition(COMPLETE | REQUEST_CONFIRM | AUTO_CONTINUE | …)
  serve() 轮询 store.running_ids() → loop.run_once  # engine/main.py:919-925

导出（engine/main.py export_artifact + engine/export.py）
  strategy_pack_eligibility(research)  # 含 pit_executed_and_passed
  eligible → build_strategy_pack(..., MeanReversionStrategy, MarketPanel, zip)
  else     → build_research_record_pack + why_not_live.json.failed_checks
```

| 组件 | 路径 | P0 备注 |
| --- | --- | --- |
| `RoundBuilder` / `DefaultRoundBuilder` | `engine/research/loop.py` | 生产已用；测试里 `FakeBuilder` 仅 `tests/test_loop_runtime.py` |
| `ResearchLoop` | `engine/research/loop.py` | `run_once` 已接 review/coverage/confirm |
| `ReviewerPort` / `run_review_gate` | `engine/review/subagent.py` | 生产默认 `SubagentReviewer(FailClosedLLM\|OpenAICompatibleLLM)` |
| `VerifierResult` / `PitVerifierResult` | `engine/verifiers.py` | `_pit_consistency` 已实现；**`run_verifiers` 不调用它**（见 T5） |
| 第四导出关 | `engine/export.py::strategy_pack_eligibility` | 键 `pit_executed_and_passed`；UI 映射 `pitExecutedAndPassed` |
| 策略包 | `engine/export.py::build_strategy_pack` | `live_handoff_eligible: true`；MeanReversion-only |
| 桌面视图 | `engine/main.py::ResearchCommandService.view_for` | Night 槽位已有；**多处仍用占位/推导字段**（见 T0） |
| Schema | `contracts/strategy-pack.schema.json` | manifest 校验；`contracts/desktop-api.schema.json` 请求校验 |

---

## File Map（实施前总览）

| 操作 | 路径 | 职责 |
| --- | --- | --- |
| Create | `engine/review/deterministic.py` | `DeterministicReviewer`：`ReviewerPort`，可配置 pass/fail 规则 |
| Modify | `engine/main.py` | `build_loop` 选择 reviewer；`view_for` 诚实映射；reverify 把证据日传入 `run_verifiers`；`resolve_confirm` 把 `who_pays` 写入唯一落点；completed 视图补轮次/指标 |
| Modify | `engine/verifiers.py` | `run_verifiers` 始终追加一条 `pit.consistency`（调用已有 `_pit_consistency`，不塞进 `_SELECTABLE`） |
| Modify | `engine/research/methods.py` | 新鲜库与已有预置库都播种 `pit.consistency`；`PRESET_NAMES` 补键，避免 `seed_preset_methods` KeyError |
| Modify | `engine/research/loop.py` | `DefaultRoundBuilder` 产出 `RoundV2`；`build` / `retry` 把证据日传入 `run_verifiers`；完成分支改用 `passed_for`（排除 PIT），不再用 `verification.passed` |
| Modify | `engine/research/models.py` | `Version.rounds` 改为 `tuple[RoundV2, ...]`，store 往返能留下 B2/B3 字段 |
| Modify | `engine/review/subagent.py` | `run_review_gate` 构造 `RoundV2`；`ReviewGateOutcome.successful_round` 类型改为 `RoundV2 \| None` |
| Modify | `engine/research/specify.py` | 逻辑/实现分栏与 `classify_change` 对齐的真实文案 |
| Modify | `engine/export.py` | `all_current_methods_passed` 改为方法集口径（排除 PIT）；`build_strategy_pack` 写入 `history/rounds.json` |
| Modify | `apps/desktop/src/main.tsx` | `resolveConfirm` 把第三参 `whoPays` 传给 `invoke` |
| Modify | `apps/desktop/src-tauri/src/commands.rs` | `resolve_confirm` 的 JSON 转发 `who_pays` |
| Modify | `contracts/desktop-api.schema.json` | `resolve_confirm` 声明可选 `who_pays`；保持 `additionalProperties: false` |
| Create | `engine/research/desktop_view.py` | 从 `Research` → desktop JSON rounds/metrics/anomaly（去重 `view_for` 占位逻辑） |
| Modify | `apps/desktop/src/App.tsx` | 去掉 completed 硬编码副标题；无数据时 fail-closed 展示（仅当 engine 发 null/省略） |
| Modify | `apps/desktop/src/contracts.ts` | completed 视图可选 `rounds` / `metrics` / `failedExportChecks` |
| Create | `tests/test_deterministic_reviewer.py` | reviewer 单元测试 |
| Create | `tests/test_v1_honest_path.py` | 网络标记的 acceptance：真实 gather + yfinance 面板 + COMPLETED |
| Create | `tests/test_v1_acceptance.py` | §2.1 行级映射（schema、view payload、export 分支） |
| Modify | `pyproject.toml` | `markers`：`network`；可选 `acceptance` |
| Create | `scripts/verify_v1_done.sh` | 本地/CI 可选：跑 acceptance 子集并打印 §2.1 对照 |

**不修改：** `docs/requirements/v1-cut-line.md`（#122 已合 main 的副本；本 PR 只新增本计划）。

---

## T0：相对 §2.1 Done 的缺口清单（只读盘点）

**Files:** 只读 `engine/main.py`, `engine/research/loop.py`, `apps/desktop/src/App.tsx`, `tests/test_loop_runtime.py`

**Interfaces:** 无代码变更；产出 `docs/plans/2026-10-13-alphaloop-p0-v1-honest-path.md` 本段表格（实施时复制到 PR 描述即可）。

- [ ] **Step 1:** 在仓库根执行 `rg -n "FakeBuilder|FailClosedLLM|SubagentReviewer" engine tests`，确认生产路径。

| Done # | 现状（main @ P0 计划起草） | 缺口 |
| --- | --- | --- |
| 1 真实 `ResearchLoop` → `COMPLETED` | `build_loop` 已用 `DefaultRoundBuilder`；review 默认 `SubagentReviewer` + 无 LLM 时 `FailClosedLLM`（恒 fail） | 无 LLM 时极难在合理预算内 `COMPLETED`；缺 DefaultRoundBuilder 端到端验收测试 |
| 2 工作台诚实填充 | `view_for` running：`logicStatement.statement` = `spec.id`；`implementationDelta` 空；`trialCounters` 用 `attempt.number` 冒充 | `RoundV2` 类型存在但 `run_review_gate` 仍构造 `Round`；completed 屏无轮次/指标，且有硬编码「美股 · 股票 · …」 |
| 3 导出门槛 | `strategy_pack_eligibility` 在 `verification.results` 里找 `pit.consistency`；`export_artifact` 分支与 `why_not_live.json` 已有 | **`run_verifiers` 不产生 PIT 结果**（只跑 `_scorecard` + `_SELECTABLE`）。诚实路径上 `pit_executed_and_passed` 恒失败。T5 必须先接线，再测导出；手插 `PitVerifierResult` 不算 Done #3 |
| 4 schema + `live_handoff_eligible` | `test_export_pack.py` 覆盖 manifest 字段；**无** jsonschema 对 zip manifest 的自动化校验 | 缺 `jsonschema.validate(manifest, schema)` 测试 |
| 5 确定性 reviewer | 仅测试内 `PassReviewer` / `FailReviewer`（`tests/test_loop_runtime.py`） | 生产未接线；`SubagentReviewer` 可阻塞或 AUTO_CONTINUE 空转 |

- [ ] **Step 2:** 记录 B4 缺口（全栈，不是引擎单点）：`AwaitingConfirmCard` 已把 `whoPays` 传给 `api.resolveConfirm`（空则 `undefined`）。断在 `apps/desktop/src/main.tsx`（invoke 丢掉第三参）、`apps/desktop/src-tauri/src/commands.rs`（JSON 只有 `research_id` + `decision`）、`contracts/desktop-api.schema.json`（`resolve_confirm` 无 `who_pays` 且 `additionalProperties: false`，引擎 `jsonschema.validate` 会拒掉多出来的字段）。`engine/main.py` 的 `resolve_confirm` 也不读该字段。空答须记「未作答」。唯一落点见 T3。

- [ ] **Step 3:** 记录 B5 缺口：`ResearchCommandService._compute_anomaly` 使用硬编码 baseline `sharpe=0.5`, `trial_count=5`（非本轮闭环产物）。

- [ ] **Step 4:** Commit（仅当 T0 更新了计划文档时）：`docs: inventory P0 gaps vs v1 cut-line §2.1`

---

## T1：确定性 Reviewer 接入生产 V1 路径

**Files:**
- Create: `engine/review/deterministic.py`
- Modify: `engine/main.py`（`build_loop`）
- Test: `tests/test_deterministic_reviewer.py`

**Interfaces:**
- Consumes: `ReviewerPort`, `RoundDraft`, `ReviewReport` from `engine/review/subagent.py`
- Produces: `DeterministicReviewer(pass_when: Callable[[RoundDraft], bool] | None = None)`；`default_v1_pass(draft) -> bool`

**设计**

| 项 | 决定 |
| --- | --- |
| 行为 | 固定策略：`draft.attempt.verification.passed_for(method_set)` **且** `draft.attempt.spec.model_family == "mean_reversion"` 则 pass，否则 fail。`method_set` 先去掉 `method_id == "pit.consistency"` 再传入。PIT 失败而方法集通过时 review 仍 pass。**不要**用 `verification.passed`：该属性要求 `results` 里每一条都通过，T5 把 PIT 放进 `results` 之后，缺 as_of 的失败会挡住 Done #1。导出侧 `build_strategy_pack` 用 `isinstance(..., MeanReversionStrategy)` 拒绝其他族；`DefaultRoundBuilder` 只构造这一族。族名守卫保持 |
| 选型 | `ALPHALOOP_REVIEWER=deterministic`（**默认**）\| `subagent` |
| 生产 | `build_loop`：`deterministic` → `DeterministicReviewer()`；`subagent` → 现有 `SubagentReviewer(llm)` |
| 与 `FailClosedLLM` | V1 验收不依赖 `ALPHALOOP_LLM_*`；subagent 模式保留给开发/后续期 |

- [ ] **Step 1: 写失败测试**

```python
# tests/test_deterministic_reviewer.py
from engine.review.deterministic import DeterministicReviewer, default_v1_pass
from engine.research.models import RoundDraft, Attempt, ChangeClass
# … reuse helpers from tests/test_loop_runtime.py …

def test_deterministic_reviewer_passes_when_methods_pass_even_if_pit_failed(draft_methods_pass_pit_fail):
    # verification.passed is False; passed_for(method_set without pit) is True
    report = DeterministicReviewer(default_v1_pass).run(draft_methods_pass_pit_fail)
    assert report.passed is True
    assert report.findings == ()

def test_deterministic_reviewer_fails_when_method_set_failed(draft_with_failing_method):
    report = DeterministicReviewer(default_v1_pass).run(draft_with_failing_method)
    assert report.passed is False

def test_deterministic_reviewer_fails_for_non_mean_reversion_family(draft_methods_pass_pit_fail):
    draft = replace_model_family(draft_methods_pass_pit_fail, "other")
    report = DeterministicReviewer(default_v1_pass).run(draft)
    assert report.passed is False
```

- [ ] **Step 2:** `pytest tests/test_deterministic_reviewer.py -v` → 预期 FAIL（模块不存在）

- [ ] **Step 3: 实现** `engine/review/deterministic.py`（`run` 同步、无 I/O）

- [ ] **Step 4:** `build_loop` 读取 `os.environ.get("ALPHALOOP_REVIEWER", "deterministic")`

- [ ] **Step 5:** `pytest tests/test_deterministic_reviewer.py tests/test_reviewer.py -q` → PASS

- [ ] **Step 6:** `git commit -m "feat(review): wire deterministic reviewer for V1 default path"`

---

## T2：真实 DataPort / MaterialPort 验收路径（与 CI fixture 矩阵）

**Files:**
- Create: `tests/test_v1_honest_path.py`（在 `tmp_path` 写 thesis 匹配的 `.md`，不依赖仓库里的 `materials/`）
- Modify: `pyproject.toml`（markers）

**Interfaces:**
- Consumes: `gather`, `RoutingDataAdapter`, `LocalMaterialAdapter`, `DefaultRoundBuilder`, `DeterministicReviewer`
- Produces: `@pytest.mark.network` 测试 `test_v1_mean_reversion_reaches_completed_real_ports`

**CI vs 真实路径矩阵**

| 场景 | MaterialPort | DataPort | 运行方式 |
| --- | --- | --- | --- |
| 单元/环测（默认 CI） | `FakeMaterials`（`tests/test_gather_specify.py`） | 内存 CSV / `FakeBuilder` 仿真 | `pytest` 默认，无网络 |
| 环测 loop | N/A | N/A | `FakeBuilder` + `PassReviewer`（`tests/test_loop_runtime.py`）— **不算 §2.1 诚实 E2E** |
| **验收（§2.3 接受路径）** | `LocalMaterialAdapter(tmp_path)`，目录里有一份与 thesis 共享词的 `.md`；可选 `PapersAdapter`（crossref） | `RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())` | `pytest -m network` 或 `ALPHALOOP_ACCEPTANCE_NETWORK=1` |
| 桌面生产 | `build_loop` 全适配器 | 同上 | 用户本机；P0 用验收测试代表 |

- [ ] **Step 1: 写失败测试**（单标的；材料与 scorecard 见下）

`LocalMaterialAdapter.fetch` 只返回 root 下 `*.md`、且正文含 query 词的文件。测试在 `tmp_path` 写一份与 locked thesis 共享词的 `.md`，把 adapter 指到该目录。空目录会让 `gather` 抛 `no public or local evidence was gathered`。

Brief 写在测试 docstring：一只流动性足够的标的（如 `SPY`）、日频。窗口要长到 scorecard / walk-forward 算得出 `sharpe_oos` 与 `excess_ann`。方法集（scorecard + `method_set`，不含 PIT）未过时不会 `COMPLETED`。PIT 失败不挡住 `COMPLETED`。用 `ResearchLoop` 已有的 retry 预算。scorecard 失败时不要 `pytest.skip` 当成通过，也不要放宽阈值；窗口不够就在同一只标的上加长。T5 落地后，同一测试断言接纳轮的 verification 含 `verifier_id == "pit.consistency"`，`passed` 可以为 False。T2 先于 T5 时这条断言保持红色，不要删掉，也不要改成要求 PIT 通过。

```python
import os
import pytest

pytestmark = pytest.mark.network

@pytest.mark.skipif(
    os.environ.get("ALPHALOOP_ACCEPTANCE_NETWORK") != "1",
    reason="§2.3 honest path requires explicit opt-in network acceptance",
)
def test_v1_mean_reversion_reaches_completed_real_ports(tmp_path):
    # 构造 locked brief → confirm_run → 循环 run_once 直至 COMPLETED 或超时步数
    # builder = DefaultRoundBuilder(..., data_port=RoutingDataAdapter(...), material_ports=(LocalMaterialAdapter(...),))
    # loop = ResearchLoop(store, builder, DeterministicReviewer(), ...)
    assert research.status is ResearchStatus.COMPLETED
    assert len(research.versions[-1].rounds) >= 1
    pit = next(
        item
        for item in research.versions[-1].rounds[-1].accepted_attempt.verification.results
        if item.verifier_id == "pit.consistency"
    )
    assert pit.verifier_id == "pit.consistency"  # T5 之后必在；passed 不要求为 True
```

- [ ] **Step 2:** 本地 `ALPHALOOP_ACCEPTANCE_NETWORK=1 pytest tests/test_v1_honest_path.py -v` → 实现至 PASS

- [ ] **Step 3:** 在 `pyproject.toml` 增加：

```toml
[tool.pytest.ini_options]
markers = [
  "network: hits crossref/yfinance/akshare (§2.3 acceptance only)",
]
```

- [ ] **Step 4:** 文档化：默认 CI 不跑 network；merge 前维护者跑验收命令（见文末 §2.1 表）。

- [ ] **Step 5:** Commit `test(acceptance): real DataPort/MaterialPort path for V1 honest E2E`

---

## T3：`DefaultRoundBuilder` 端到端 → `COMPLETED` 且产物入 store + who_pays 全栈

**Files:**
- Modify: `engine/research/models.py`（`Version.rounds: tuple[RoundV2, ...]`）
- Modify: `engine/research/loop.py`, `engine/review/subagent.py`（构造 `RoundV2`；`ReviewGateOutcome.successful_round: RoundV2 | None`）
- Modify: `engine/research/specify.py`
- Modify: `engine/main.py`（`resolve_confirm`）
- Modify: `apps/desktop/src/main.tsx`（`resolveConfirm` 转发 `whoPays`）
- Modify: `apps/desktop/src-tauri/src/commands.rs`（`resolve_confirm` JSON 带 `who_pays`）
- Modify: `contracts/desktop-api.schema.json`（`resolve_confirm` 增加可选 `who_pays`）
- Test: `tests/test_logic_impl_split.py`（扩展）：轮次入库后字段非空；who_pays 落点用 `tests/test_evidence_ref.py` 或 `tests/test_v1_acceptance.py`

**Interfaces:**
- Produces: `run_review_gate` 成功时 `successful_round: RoundV2`（含 `logic_statement`, `implementation_delta`, `trial_counters`）
- Produces: `trial_counters` 规则：`candidates_evaluated` = review 尝试次数；`candidates_passed` = `passed_for(method_set)`（排除 `pit.consistency`）为真的尝试数；`conclusion_attempt_number` = 接纳的 attempt.number。不要用 `verification.passed` 计「通过」，否则 PIT 失败会把已完成轮计成未通过
- Produces: 经济确认 `approve_new_version` 后，新 `Version.confirmed_changes` **追加**一对 `("who_pays_optional", <原文或 "未作答">)`。这是 who_pays 的唯一持久记录；不替换 patch 里已有的确认项。

**Round → RoundV2 持久化**

`Round` 与 `RoundV2` 是并列 dataclass。`Version.rounds` 今天是 `tuple[Round, ...]`。`SQLiteStore._decode` 用 cattrs 按这个注解还原。不改 `engine/research/models.py` 就把 `RoundV2` 塞进 version，B2/B3 字段在往返中丢失或结构失败，T4 没有真字段可映射。

P0 把 `Version.rounds` 改成 `tuple[RoundV2, ...]`，`run_review_gate` 不再构造 `Round`。load 时不要填占位 `LogicStatement` / `ImplementationDelta` / `TrialCounters` 再交给 `view_for` 显示。无生产存量要迁；旧 JSON 缺这三字段时结构失败可以接受。

**who_pays 全栈（B4）**

确认卡 UI 已经在问（`AwaitingConfirmCard`，空则 `undefined`）。`contracts.ts` 的 `DesktopApi.resolveConfirm` 已有可选第三参。P0 不改这张卡的版式。断点在后面三跳，只改引擎会被 schema 拒掉：

| 跳 | 现状 | P0 |
| --- | --- | --- |
| `apps/desktop/src/main.tsx` | `resolveConfirm(researchId, decision)` 的 invoke 不带 `whoPays` | 把第三参传给 `invoke("resolve_confirm", {researchId, decision, whoPays})` |
| `commands.rs::resolve_confirm` | JSON 只有 `type` / `research_id` / `decision` | 有值时带上 `who_pays` |
| `contracts/desktop-api.schema.json` | `additionalProperties: false`，无 `who_pays` | 可选 string `who_pays`；不要改成允许任意额外字段 |
| `engine/main.py` `resolve_confirm` | 不读该字段 | 见下方唯一落点 |

**唯一持久落点：** 新版本的 `confirmed_changes`。`_open_version` 已把 `pending_confirm.patch` 抄进 `confirmed_changes`，然后清空 `pending_confirm`。`ResearchBrief` 没有 `who_pays_optional`，这项不会被套进 brief。引擎在 `transition` 之前，仅对经济确认 `approve_new_version`，把 `("who_pays_optional", text or "未作答")` 追加进 patch。不写 export history，也不在已清空的 `ConfirmRequest` 上再留一份。覆盖类决策（`accept_lower_floor`、`redefine_scope` 等）不提问，不写这项。

- [ ] **Step 1:** 写失败测试：SQLite 跑一轮后，round 上 `logic_statement.statement` 含 locked thesis 片段，而非裸 `spec.id`；reload 后字段仍在

- [ ] **Step 2:** `Version.rounds` 改为 `tuple[RoundV2, ...]`；`DefaultRoundBuilder.build` 末尾根据 `specify` / `classify_change` 填充 `LogicStatement` 与 `ImplementationDelta`

- [ ] **Step 3:** `run_review_gate` 构造 `RoundV2`；`ResearchLoop` 存入 version.rounds

- [ ] **Step 4:** 打通 who_pays 四跳（`main.tsx`、`commands.rs`、schema、`resolve_confirm`）。`approve_new_version` 且空/省略 → `confirmed_changes` 里是 `"未作答"`。断言没有第二份落点（export history 不出现该字段）

- [ ] **Step 5:** `pytest tests/test_loop_runtime.py tests/test_logic_impl_split.py tests/test_evidence_ref.py -q`（loop 测试改用 `DeterministicReviewer` 或保留 `PassReviewer` 仅测状态机）

- [ ] **Step 6:** Commit `feat(loop): persist RoundV2 and record who_pays on the new version`

---

## T4：去占位 / fail-closed 工作台填充

**Files:**
- Create: `engine/research/desktop_view.py`
- Modify: `engine/main.py::view_for`
- Modify: `apps/desktop/src/App.tsx`, `apps/desktop/src/contracts.ts`
- Test: `tests/test_v1_acceptance.py::test_running_view_round_fields_from_store`

**必须从 `ResearchLoop` 产物读取的字段（禁止编造）**

| 视图 | 字段 | 来源 |
| --- | --- | --- |
| running / paused | `rounds[].logicStatement` | `RoundV2.logic_statement` |
| running / paused | `rounds[].implementationDelta` | `RoundV2.implementation_delta` |
| running / paused | `rounds[].trialCounters` | `RoundV2.trial_counters` |
| running / paused | `rounds[].verificationPassed` | `passed_for(method_set)`（排除 `pit.consistency`），与完成口径相同。不要用 `verification.passed`，否则 PIT 失败会把已完成轮显示成验证未过 |
| running / paused | `rounds[].pitPassed` | 该轮 verification 里 `verifier_id == "pit.consistency"` 的 `passed`（true/false）。main 上 `view_for` 写死 `None`。依赖 T5 接线；没有这条结果就不要显示通过。PIT 失败可以与 `verificationPassed: true` 同时出现 |
| running / paused | `dataCutoff` | `research.last_coverage.end` 或 simulation end；**无则省略键或显式「尚无」** |
| running / paused | `sources` | `evidence_paths` / materials 摘要 |
| completed | `title` | `brief.thesis`；禁止空字符串默认大标题 |
| completed | `rounds` / `metrics`（新增槽位） | 最后一轮 `SimulationReport` + 同上 rounds |
| completed | `selectedMethodId` | 该轮 method set 中供重验使用的方法 id。main 的 completed 视图写死 `"overfit.walk"`，禁止保留字面量 |
| completed | 副标题 | `universe_label` 来自 `list_items` 逻辑，**删除**硬编码「美股 · 股票 · …」 |
| list | `createdAt` 缺失 | 不用「等了 2 小时」假时间（`App.tsx` awaiting 行） |
| anomaly | `baseline` | 来自 `detect_anomalies` 的真实 prior attempt / v1 baseline，**禁止**常量 0.5/5 |

- [ ] **Step 1:** 测试：fixture research 的 `view_for('#/research/{id}')` JSON 与 store 中 `RoundV2` 字段一致；`pitPassed` 等于 PIT 结果而不是 `None`；completed 的 `selectedMethodId` 不是字面量 `"overfit.walk"`；副标题不是硬编码「美股 · 股票 · …」

- [ ] **Step 2:** 抽取 `_rounds_for_desktop(research) -> list[dict]` 到 `desktop_view.py`，`view_for` 调用

- [ ] **Step 3:** completed 视图增加 `rounds`（及可选 `metrics`）；`App.tsx` 复用 `RunningScreen` 轮次卡片或只读片段

- [ ] **Step 4:** 写失败测试 `test_anomaly_baseline_not_hardcoded`，再替换 `ResearchCommandService._compute_anomaly` 里写死的 `AnomalyBaseline(kind="version_1_logic", sharpe=0.5, trial_count=5)`。sharpe 与试验次数取上一接受 attempt 的 `simulation.sharpe` / attempt 次数，或闭环里已有的 Version-1 逻辑基线。两者都没有则返回 `None`（fail-closed），不要用 0.5/5 充数。不改 `detect_anomalies` 的 `ANOMALY_HEURISTIC_DEFAULTS`

- [ ] **Step 5:** `cd apps/desktop && npm test -- --run` → PASS

- [ ] **Step 6:** Commit `fix(desktop): honest workbench fields from research artifacts`

---

## T5：把 PIT 接进 `run_verifiers`，再测四门栏导出

**Files:**
- Modify: `engine/verifiers.py`（`run_verifiers` 调用 `_pit_consistency`）
- Modify: `engine/research/loop.py`（`build` / `retry` 传入 `evidence_as_of`；完成分支改 `passed_for`）
- Modify: `engine/main.py`（reverify 的 `run_verifiers` 调用同样传入）
- Modify: `engine/research/methods.py`（播种 `pit.consistency`；`PRESET_NAMES`）
- Modify: `engine/export.py`（`all_current_methods_passed` 口径；`history/rounds.json`）
- Test: `tests/test_pit_verifier.py`, `tests/test_v1_acceptance.py`, `tests/test_export_pack.py`

**Interfaces:**
- Consumes: 已有 `_pit_consistency(spec, evidence_timestamps, backtest_cutoff)`、`PIT_VERIFIER_REVISION`、`strategy_pack_eligibility`、`build_strategy_pack`、`build_research_record_pack`
- Produces: 每份 `VerificationReport.results` 含恰好一条 `verifier_id == "pit.consistency"`；zip 内 `manifest.json` 通过 `contracts/strategy-pack.schema.json`；不合格时 `why_not_live.json`

**现状（main，已核对）**

- `_pit_consistency` 与 `PIT_VERIFIER_REVISION` 在 `engine/verifiers.py`。`run_verifiers` 只跑 `_scorecard`，再按 `spec.method_set` 查 `_SELECTABLE`（`overfit.walk` / `stability.oos` / `crowding.load` / `cost.turnover`），**从不调用 PIT**。
- `_pit_consistency` 的参数是 `(spec, evidence_timestamps, backtest_cutoff)`，不是 `_SELECTABLE` 的 `(report, spec)`。不能把它塞进 `_SELECTABLE`。
- `strategy_pack_eligibility` 只在 `accepted_attempt.verification.results` 里找 `pit.consistency`。不接线则 `pit_executed_and_passed` 恒失败。
- 默认 `round1_methods`（`specify.propose_brief_updates`）不含 pit。`seed_preset_methods` 只遍历 `VERIFIER_REVISIONS`，且 `if store.list_method_definitions(): return`。`PRESET_NAMES` 没有 pit 键；若直接并进 `VERIFIER_REVISIONS` 会在 `PRESET_NAMES[method_id]` KeyError。
- B1：每次验证都要执行 PIT，且该预置不能靠从 method set 里删掉来跳过。执行开关是 `run_verifiers`，不是 `round1_methods`。

**接线**

- `run_verifiers(report, spec, *, evidence_as_of: tuple[tuple[str, str], ...] = ())` 在 scorecard 与可选方法之后**始终**追加恰好一条 `pit.consistency`。`method_set` 里有没有它都要跑。
- cutoff = `report.end.isoformat()`。`report.end is None` 时追加 `passed=False` 的 `PitVerifierResult`（缺 cutoff 不算通过），不要借 `_pit_consistency([])` 的「空证据通过」放行。
- `evidence_as_of` 是 `(evidence_id, ISO date)`。三个生产调用点必须传入：`DefaultRoundBuilder.build`、`DefaultRoundBuilder.retry`、`ResearchCommandService` 的 reverify。
- `Material` 只有 `fetched_at`，没有发表日。**禁止**把 `fetched_at` 当成 as_of（抓取时刻通常晚于回测截止，会假失败）。**禁止**用 cutoff 回填 as_of（会假通过）。builder 拿不到可辩护的决策日时，对该 `material_id` 记 violation `missing as_of`，结果为已执行且未通过。本轮有 evidence 但 `evidence_as_of` 为空，同样失败。`_pit_consistency` 对空列表返回通过的单元行为保持不变，不作为生产规则。
- **决策 (b) 的两套通过。** PIT 结果始终留在 `results` 里，给资格检查和 `pitPassed`。review、`DeterministicReviewer`（T1）、以及 `ResearchLoop.run_once` 里现在的 `if accepted.verification.passed`（`engine/research/loop.py` 完成分支）改为 `passed_for`，传入的 method set **去掉** `pit.consistency`。`verification.passed` 保持「每一条结果都通过」的原义，完成路径不再调用它。这样缺 as_of 时 PIT 失败，研究仍可 `COMPLETED`。
- **导出不双计。** `pit_executed_and_passed` 仍只看 PIT 那一条（已执行且 `passed`）。`all_current_methods_passed` 今天是 `current_attempt.verification.passed`（`engine/export.py`）；改成与完成分支相同的 `passed_for`（排除 PIT）。方法集通过且 PIT 失败时，`failed_checks` 含 `pit_executed_and_passed`，**不含** `all_current_methods_passed`。
- 正面 `strategy_pack` 用例调用接线后的 `run_verifiers(..., evidence_as_of=(...,))`，日期早于 `report.end`。禁止手插 `PitVerifierResult` 再送进 `strategy_pack_eligibility` 来充当 Done #3。网络验收（T2）只要求 `COMPLETED`，并断言 `pit.consistency` 在结果里（可以失败）。PIT 未过时该路径导出 `research_record`，`why_not_live.json` 含 `pit_executed_and_passed`。
- 预置：`PRESET_NAMES["pit.consistency"] = "时点一致性"`。`seed_preset_methods` 播种 `PIT_VERIFIER_REVISION`。已有方法库的 store 也要幂等补上 `pit.consistency` / `pit-v1`（现有早退不能把已播种的库漏掉）。方法库展示用，不作为执行开关，也不放进 `round1_methods` 来决定要不要跑。

- [ ] **Step 1: 写失败测试** `test_run_verifiers_emits_pit_consistency`：`run_verifiers` 的结果含 `pit.consistency`；`report.end is None` 或有证据但无 as_of 时 **这条 PIT** 的 `passed is False`；as_of 早于 `report.end` 时该条 `passed is True`。方法集通过且 PIT 失败时，`passed_for`（排除 PIT）为 True，`verification.passed` 为 False。另测 `DefaultRoundBuilder`（或等价生产调用）产出的 verification 含同一 id，而不是只测 `_pit_consistency` 本身。

- [ ] **Step 2:** 按上面接线实现 `run_verifiers`、三个调用点、预置播种。完成分支与 `all_current_methods_passed` 改用排除 PIT 的 `passed_for`。

- [ ] **Step 3:** `pytest tests/test_pit_verifier.py tests/test_verifiers.py -q` → PASS

- [ ] **Step 4: 写失败测试 schema**

```python
import json
from pathlib import Path
import jsonschema

def test_strategy_pack_manifest_validates_against_contract_schema(tmp_path):
    archive = build_strategy_pack(...)
    manifest = json.loads(zipfile.ZipFile(archive).read("manifest.json"))
    schema = json.loads(Path("contracts/strategy-pack.schema.json").read_text())
    jsonschema.validate(manifest, schema)
    assert manifest["live_handoff_eligible"] is True
```

- [ ] **Step 5:** 写测试：verification 来自 `run_verifiers`。方法集通过且 PIT fail 时，研究可以 `COMPLETED`，`failed_checks` 含 `pit_executed_and_passed` 且不含 `all_current_methods_passed`；`export_artifact(strategy_pack)` 400；`research_record` 200 且 `why_not_live.json` 含 `pit_executed_and_passed`。PIT pass（as_of 早于 cutoff，且其余门栏过）时才能 `strategy_pack`。

- [ ] **Step 6:** `build_strategy_pack` 写入 `history/rounds.json` = `_round_history_with_trials(...)`（rounds 为 `RoundV2`，T3 之后版本里只有这一种）

- [ ] **Step 7:** `pytest tests/test_export_pack.py tests/test_v1_acceptance.py tests/test_pit_verifier.py -q` → PASS

- [ ] **Step 8:** Commit `feat(verify): run pit.consistency inside run_verifiers and cover export gates`

---

## T6：验收 harness — §2.1 五行 → 测试/脚本

**Files:**
- Create: `tests/test_v1_acceptance.py`
- Create: `scripts/verify_v1_done.sh`

- [ ] **Step 1:** 实现 `scripts/verify_v1_done.sh`（顺序执行下表命令，任一失败 exit 1）

- [ ] **Step 2:** 在 PR/CI 文档中写明：默认 CI = 无 network 子集；发布前跑完整脚本。

| §2.1 Done | 验收命令（实现 P0 后） |
| --- | --- |
| **1** 真实 `ResearchLoop`（非 `FakeBuilder`）→ `COMPLETED`（PIT 可失败；T5 后结果里有 `pit.consistency`） | `ALPHALOOP_ACCEPTANCE_NETWORK=1 pytest tests/test_v1_honest_path.py::test_v1_mean_reversion_reaches_completed_real_ports -v` |
| **2** 运行中/已完成字段来自闭环，无假指标（含 `pitPassed`、`selectedMethodId`、副标题、异常 baseline 非 0.5/5） | `pytest tests/test_v1_acceptance.py::test_running_view_round_fields_from_store tests/test_v1_acceptance.py::test_completed_view_no_placeholder_copy tests/test_v1_acceptance.py::test_anomaly_baseline_not_hardcoded -v` |
| **3** 四门栏 + PIT 由 `run_verifiers` 执行；否则仅 `research_record` + 缺关说明 | `pytest tests/test_pit_verifier.py::test_run_verifiers_emits_pit_consistency tests/test_v1_acceptance.py::test_export_strategy_pack_only_when_eligible -q` |
| **4** zip 通过 schema 且 `live_handoff_eligible: true` | `pytest tests/test_v1_acceptance.py::test_strategy_pack_manifest_validates_against_contract_schema -v` |
| **5** 确定性 reviewer，外部 LLM 不阻塞 | `pytest tests/test_deterministic_reviewer.py tests/test_v1_acceptance.py::test_build_loop_defaults_to_deterministic_reviewer -v` |

**默认 CI（无网络）子集：** `pytest tests/test_deterministic_reviewer.py tests/test_v1_acceptance.py tests/test_export_pack.py tests/test_pit_verifier.py tests/test_verifiers.py tests/test_loop_runtime.py -q`

- [ ] **Step 3:** Commit `test: map v1 cut-line §2.1 to acceptance harness`

---

## 可测 Done 验收清单（复制 v1-cut-line §2.1）

实施完成后，**五条须同时成立**：

1. 锁定五项研究设定，跑通至少一轮真实 `ResearchLoop`（不是 `FakeBuilder`），研究到达已完成（`COMPLETED`）。
2. 运行中 / 已完成工作台上的字段全部来自这一轮闭环。没有空标题，没有假指标。
3. 四条可实盘资格全部通过，含时点第四关，才能导出 `strategy_pack`。缺任何一关，只能导出 `research_record`，并写明缺的是哪一关。
4. 导出的 zip 能通过 `contracts/strategy-pack.schema.json` 校验，且 `live_handoff_eligible: true`。
5. 这条诚实路径钉一个确定性 reviewer（固定 Pass/Fail 策略），接在现有 review 关上。外部大模型的抖动不能卡住 V1 唯一的这条路径。

（与产品设计 §3.7 对齐：UI 展示的四条为「方法全通过 / 无待确认 / 重验成立 / PIT 通过」。决策 (b) 下「方法全通过」= `passed_for` 排除 PIT；「PIT 通过」只对应 `pit_executed_and_passed`。引擎 `strategy_pack_eligibility` 另含 `completed` 与 round 存在性，导出 API 在 non-COMPLETED 时本就拒绝 strategy_pack。）

---

## 风险与非目标

**来自 v1-cut-line §3 / §5（不进入 P0 承诺）**

- 开放式 LLM 对话主入口、多策略族挖掘、研究记忆与生产级 harness 工厂、行情终端/实盘下单、替换 Night 七屏、CLI 扩 scope。

**工程风险**

| 风险 | 缓解 |
| --- | --- |
| Review 关仍走 subagent，无 key 时 fail 导致无法 COMPLETED | T1 默认 `deterministic`；CI 断言 `build_loop` 默认；pass 条件与 MeanReversion 导出族对齐 |
| 真实 DataPort 网络 flake | 单标的 + docstring 里写明的窗口；`tmp_path` 放 thesis 匹配的 `.md`；CI 默认 skip network；scorecard 失败不加 skip、不放宽阈值 |
| `run_verifiers` 不跑 PIT，第四关恒失败或被手插结果放过 | T5 先接线；导出测试消费 `run_verifiers` 的报告。不用 `fetched_at`，不用 cutoff 回填 as_of。缺 as_of 只让 PIT 失败 |
| PIT 失败挡住 Done #1，或 `all_current_methods_passed` 与第四关双计 | 决策 (b)：完成 / review 用排除 PIT 的 `passed_for`；`verification.passed` 不用于 `COMPLETED`。第四关仍单独看 `pit_executed_and_passed` |
| 异常 baseline 仍是 0.5/5 | T4 用上一 attempt 或 Version-1 基线；没有则 `None` |
| `Round`/`RoundV2` 双类型漂移 | T3 改 `Version.rounds` 为 `RoundV2` 并入库；export/desktop 同一 helper |
| who_pays 只改引擎，schema 拒掉或答案无处可记 | T3 打通 invoke / `commands.rs` / schema；只写入新版本 `confirmed_changes` |
| Scope creep 到 P1 对话 | 仅 keyword `interpret`；不把 P1 归档/消息线程拉入 P0 |
| 桌面视觉改版 | 只删占位文案、补 completed 轮次槽位 |

---

## 建议实施顺序

```text
T0（盘点） → T1（deterministic reviewer） → T2（network acceptance 骨架）
    → T3（RoundV2 持久化 + who_pays 全栈）
    → T5 接线（run_verifiers 总会产出 pit.consistency）
    → T4（view_for + pitPassed / selectedMethodId / 副标题）
    → T5 其余（export/schema，报告必须来自 run_verifiers）
    → T6（harness 与文档命令）
```

T2 与 T3 可并行子代理。**T4 依赖 T3** 的真实 round 字段，并且 **`pitPassed` 依赖 T5 接线**。**T5 的 rounds 历史依赖 T3** 的 `RoundV2`。不要先写导出测试再补 PIT。

---

## Self-Review（计划自检）

| 检查项 | 结果 |
| --- | --- |
| §2.1 五行均有 T6 命令 | ✓ Done #3 含 `test_run_verifiers_emits_pit_consistency` |
| 未发明第二研究路径 | ✓ PIT 接进现有 `run_verifiers`，不新开验证路径 |
| 文件路径与 main 一致 | ✓ 已改正「pit 已在 `run_verifiers`」；对照 `verifiers.py`、`models.py`、`main.tsx`、`commands.rs`、schema |
| B1 不会因只测导出而漏执行 | ✓ T5 先接线；PIT 始终在 `results` 里 |
| 决策 (b)：Done #1 不要求 PIT 通过 | ✓ 完成 / review 用 `passed_for`，排除 `pit.consistency`；不用 `.passed` |
| `all_current_methods_passed` 不与第四关双计 | ✓ T5 与完成口径相同 |
| 不发明 Material as_of | ✓ 缺 as_of → PIT 已执行且失败，只挡 `strategy_pack` |
| B5 baseline 不是 0.5/5 | ✓ T4 显式替换 `_compute_anomaly` |
| B4 who_pays 全栈、单一落点 | ✓ T3：`Version.confirmed_changes` |
| T3 含 `models.py` | ✓ `Version.rounds: tuple[RoundV2, ...]` |
| 无 TBD/稍后 | ✓ |
| 不修改 v1-cut-line.md | ✓ |

---

**计划路径:** `docs/plans/2026-10-13-alphaloop-p0-v1-honest-path.md`

**执行选项（实施阶段）：**

1. **Subagent-Driven（推荐）** — 每任务独立子代理 + 任务间审查  
2. **Inline Execution** — 单会话按 `executing-plans` 批量执行并设检查点
