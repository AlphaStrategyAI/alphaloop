# AlphaLoop P0 — V1 诚实 MeanReversion 路径 技术实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans，按任务逐步执行。步骤使用 checkbox（`- [ ]`）跟踪。

**Goal:** 在**不新开第二条研究路径**的前提下，让 V1 唯一承诺的诚实端到端（MeanReversion + 现有 `RoundBuilder` / `ResearchLoop`）满足 [V1 交付收口 §2.1](../requirements/v1-cut-line.md#21-可测-done) 五条可测 Done；工作台数据来自真实闭环，review 关由确定性 reviewer 兜底，导出四门栏 + PIT 全链成立。

**Architecture:** 生产侧继续 `engine/main.py::build_loop` → `DefaultRoundBuilder`（gather→specify→simulate→`run_verifiers`）→ `ResearchLoop.run_once` → `run_review_gate`（`ReviewerPort`）→ `transition`。P0 只补齐：**(1)** V1 路径选用确定性 `ReviewerPort`；(2) 轮次产物写入 store 的 B2/B3 字段并经 `ResearchCommandService.view_for` 诚实映射到 Night 七屏已有槽位；(3) 一条带真实 `MaterialPort`/`DataPort` 的验收路径（CI 其余仍 fixture）；(4) 导出沿用 `strategy_pack_eligibility` + `build_strategy_pack` / `build_research_record_pack` + `contracts/strategy-pack.schema.json`。

**Tech Stack:** Python 3.12, pandas, NumPy, httpx, yfinance, akshare, SQLite, jsonschema, pytest; Tauri 2 + React + TypeScript（仅数据填充，不改 Night IA）

## Global Constraints

- **收口文档为准：** [docs/requirements/v1-cut-line.md](../requirements/v1-cut-line.md) §2.1–2.3、§3、§5；行为细节仍以 [product-design-v0_0_1.md](../requirements/product-design-v0_0_1.md)（B1–B6、§3.7 四条资格 + PIT 第四关）为准；壳层 [ui-design-v0_0_1.md](../requirements/ui-design-v0_0_1.md) 七屏不重设计。
- **单路径契约：** `RoundBuilder` / `DefaultRoundBuilder` / `ResearchLoop`；`VerifierResult` / `PitVerifierResult` / `pit.consistency`；`strategy_pack_eligibility` / `build_strategy_pack`；`contracts/strategy-pack.schema.json`（`live_handoff_eligible: true`）。
- **MeanReversion 导出硬约束：** `engine/export.py::build_strategy_pack` 仅接受 `MeanReversionStrategy`（已存在 `TypeError` 守卫）。
- **不下单、不接券商：** 策略包可含 `ExecutionPort` / `NotImplementedBroker` 占位；不交付券商执行器。
- **数据口 §2.3：** CI 可用 fixture；**至少一条被接受的验收路径**必须走真实 `DataPort` / `MaterialPort`（`engine/research/gather.py` 已有 crossref / SEC / `LocalMaterialAdapter` + `RoutingDataAdapter(YahooDataAdapter, AkShareDataAdapter)`）。
- **外部 LLM 不得卡住 V1 Done：** §2.1 Done #5 — 诚实路径钉确定性 reviewer（固定 Pass/Fail），`SubagentReviewer` 可保留给非 V1 / 后续期，但不得阻塞 P0 验收链。
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
| `VerifierResult` / `PitVerifierResult` | `engine/verifiers.py` | `pit.consistency` 已在 `run_verifiers` |
| 第四导出关 | `engine/export.py::strategy_pack_eligibility` | 键 `pit_executed_and_passed`；UI 映射 `pitExecutedAndPassed` |
| 策略包 | `engine/export.py::build_strategy_pack` | `live_handoff_eligible: true`；MeanReversion-only |
| 桌面视图 | `engine/main.py::ResearchCommandService.view_for` | Night 槽位已有；**多处仍用占位/推导字段**（见 T0） |
| Schema | `contracts/strategy-pack.schema.json` | manifest 校验；`contracts/desktop-api.schema.json` 请求校验 |

---

## File Map（实施前总览）

| 操作 | 路径 | 职责 |
| --- | --- | --- |
| Create | `engine/review/deterministic.py` | `DeterministicReviewer`：`ReviewerPort`，可配置 pass/fail 规则 |
| Modify | `engine/main.py` | `build_loop` 选择 reviewer；`view_for` 诚实映射；`resolve_confirm` 写入 `who_pays`；completed 视图补轮次/指标 |
| Modify | `engine/research/loop.py` | `DefaultRoundBuilder` 产出 `RoundV2`（或统一 Round 扩展字段）；持久化 `TrialCounters` / `LogicStatement` / `ImplementationDelta` |
| Modify | `engine/research/models.py` | 若采用「Version 存 RoundV2」：迁移 `Version.rounds` 类型或序列化兼容 |
| Modify | `engine/research/specify.py` | 逻辑/实现分栏与 `classify_change` 对齐的真实文案 |
| Modify | `engine/export.py` | `build_strategy_pack` 写入 `history/rounds.json`（调用已有 `_round_history_with_trials`） |
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
| 3 导出门槛 | `strategy_pack_eligibility` + `export_artifact` 分支已实现；`why_not_live.json` 已有 | 需 E2E 证明四门栏 + PIT 与 UI 一致；`research_record` 在不合格时仍可导出（已支持） |
| 4 schema + `live_handoff_eligible` | `test_export_pack.py` 覆盖 manifest 字段；**无** jsonschema 对 zip manifest 的自动化校验 | 缺 `jsonschema.validate(manifest, schema)` 测试 |
| 5 确定性 reviewer | 仅测试内 `PassReviewer` / `FailReviewer`（`tests/test_loop_runtime.py`） | 生产未接线；`SubagentReviewer` 可阻塞或 AUTO_CONTINUE 空转 |

- [ ] **Step 2:** 记录 B4 小缺口：`resolve_confirm` 未把桌面传入的 `who_pays` 写入 `ConfirmRequest` / version 记录（`engine/main.py` `kind == "resolve_confirm"`）。

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
- Produces: `DeterministicReviewer(pass_when: Callable[[RoundDraft], bool] | None = None)`；`default_v1_pass(draft) -> bool`（建议：`draft.attempt.verification.passed` 且 `model_family == "mean_reversion"`）

**设计**

| 项 | 决定 |
| --- | --- |
| 行为 | 固定策略：默认 **verification 全通过则 review pass**，否则 fail（可测、无网络） |
| 选型 | `ALPHALOOP_REVIEWER=deterministic`（**默认**）\| `subagent` |
| 生产 | `build_loop`：`deterministic` → `DeterministicReviewer()`；`subagent` → 现有 `SubagentReviewer(llm)` |
| 与 `FailClosedLLM` | V1 验收不依赖 `ALPHALOOP_LLM_*`；subagent 模式保留给开发/后续期 |

- [ ] **Step 1: 写失败测试**

```python
# tests/test_deterministic_reviewer.py
from engine.review.deterministic import DeterministicReviewer, default_v1_pass
from engine.research.models import RoundDraft, Attempt, ChangeClass
# … reuse helpers from tests/test_loop_runtime.py …

def test_deterministic_reviewer_passes_when_verification_passed(draft_with_passing_verification):
    report = DeterministicReviewer(default_v1_pass).run(draft_with_passing_verification)
    assert report.passed is True
    assert report.findings == ()

def test_deterministic_reviewer_fails_when_verification_failed(draft_with_failing_verification):
    report = DeterministicReviewer(default_v1_pass).run(draft_with_failing_verification)
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
- Create: `tests/test_v1_honest_path.py`
- Modify: `pyproject.toml`（markers）
- Modify: `materials/README.md`（可选：验收用本地材料文件名）

**Interfaces:**
- Consumes: `gather`, `RoutingDataAdapter`, `LocalMaterialAdapter`, `DefaultRoundBuilder`, `DeterministicReviewer`
- Produces: `@pytest.mark.network` 测试 `test_v1_mean_reversion_reaches_completed_real_ports`

**CI vs 真实路径矩阵**

| 场景 | MaterialPort | DataPort | 运行方式 |
| --- | --- | --- | --- |
| 单元/环测（默认 CI） | `FakeMaterials`（`tests/test_gather_specify.py`） | 内存 CSV / `FakeBuilder` 仿真 | `pytest` 默认，无网络 |
| 环测 loop | N/A | N/A | `FakeBuilder` + `PassReviewer`（`tests/test_loop_runtime.py`）— **不算 §2.1 诚实 E2E** |
| **验收（§2.3 接受路径）** | `LocalMaterialAdapter(materials/)` + 可选 `PapersAdapter`（crossref） | `RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())` | `pytest -m network` 或 `ALPHALOOP_ACCEPTANCE_NETWORK=1` |
| 桌面生产 | `build_loop` 全适配器 | 同上 | 用户本机；P0 用验收测试代表 |

- [ ] **Step 1: 写失败测试**（缩短 universe：1 符号、短窗口，降低 flake）

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

## T3：`DefaultRoundBuilder` 端到端 → `COMPLETED` 且产物入 store + 桌面

**Files:**
- Modify: `engine/research/loop.py`, `engine/review/subagent.py`（`Round` → `RoundV2` 构造）
- Modify: `engine/research/specify.py`
- Modify: `engine/main.py`（`resolve_confirm` who_pays）
- Test: `tests/test_logic_impl_split.py`（扩展）：轮次入库后字段非空

**Interfaces:**
- Produces: `run_review_gate` 成功时 `successful_round: RoundV2`（含 `logic_statement`, `implementation_delta`, `trial_counters`）
- Produces: `trial_counters` 规则：`candidates_evaluated` = review 尝试次数；`candidates_passed` = verification.passed 的尝试数；`conclusion_attempt_number` = 接纳的 attempt.number

- [ ] **Step 1:** 写失败测试：SQLite 跑一轮后，round 上 `logic_statement.statement` 含 locked thesis 片段，而非裸 `spec.id`

- [ ] **Step 2:** `DefaultRoundBuilder.build` 末尾根据 `specify` / `classify_change` 填充 `LogicStatement` 与 `ImplementationDelta`

- [ ] **Step 3:** `run_review_gate` 构造 `RoundV2`；`ResearchLoop` 存入 version.rounds

- [ ] **Step 4:** `resolve_confirm` 将 request body 的 `who_pays`（若 API 已传）写入 approve 后的 research/version 元数据（`who_pays_optional` 或 export history）

- [ ] **Step 5:** `pytest tests/test_loop_runtime.py tests/test_logic_impl_split.py -q`（loop 测试改用 `DeterministicReviewer` 或保留 `PassReviewer` 仅测状态机）

- [ ] **Step 6:** Commit `feat(loop): persist RoundV2 artifacts from DefaultRoundBuilder`

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
| running / paused | `rounds[].verificationPassed` | `accepted_attempt.verification.passed` |
| running / paused | `dataCutoff` | `research.last_coverage.end` 或 simulation end；**无则省略键或显式「尚无」** |
| running / paused | `sources` | `evidence_paths` / materials 摘要 |
| completed | `title` | `brief.thesis`；禁止空字符串默认大标题 |
| completed | `rounds` / `metrics`（新增槽位） | 最后一轮 `SimulationReport` + 同上 rounds |
| completed | 副标题 | `universe_label` 来自 `list_items` 逻辑，**删除**硬编码「美股 · 股票 · …」 |
| list | `createdAt` 缺失 | 不用「等了 2 小时」假时间（`App.tsx` awaiting 行） |
| anomaly | `baseline` | 来自 `detect_anomalies` 的真实 prior attempt / v1 baseline，**禁止**常量 0.5/5 |

- [ ] **Step 1:** 测试：fixture research 的 `view_for('#/research/{id}')` JSON 与 store 中 `RoundV2` 字段一致

- [ ] **Step 2:** 抽取 `_rounds_for_desktop(research) -> list[dict]` 到 `desktop_view.py`，`view_for` 调用

- [ ] **Step 3:** completed 视图增加 `rounds`（及可选 `metrics`）；`App.tsx` 复用 `RunningScreen` 轮次卡片或只读片段

- [ ] **Step 4:** `cd apps/desktop && npm test -- --run` → PASS

- [ ] **Step 5:** Commit `fix(desktop): honest workbench fields from research artifacts`

---

## T5：导出门槛 E2E — 四门栏 + PIT、strategy_pack vs research_record、schema

**Files:**
- Modify: `engine/export.py`（`history/rounds.json`）
- Test: `tests/test_v1_acceptance.py`, `tests/test_export_pack.py`, `tests/test_pit_verifier.py`

**Interfaces:**
- Consumes: `strategy_pack_eligibility`, `build_strategy_pack`, `build_research_record_pack`
- Produces: zip 内 `manifest.json` 通过 `contracts/strategy-pack.schema.json`；不合格时 `why_not_live.json`

- [ ] **Step 1: 写失败测试 schema**

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

- [ ] **Step 2:** 写测试：PIT fail 时 `export_artifact(strategy_pack)` 400；`research_record` 200 且 `why_not_live.json` 含 `pit_executed_and_passed`

- [ ] **Step 3:** `build_strategy_pack` 写入 `history/rounds.json` = `_round_history_with_trials(...)`（仅当 rounds 为 `RoundV2`）

- [ ] **Step 4:** `pytest tests/test_export_pack.py tests/test_v1_acceptance.py tests/test_pit_verifier.py -q` → PASS

- [ ] **Step 5:** Commit `feat(export): rounds history in pack + schema acceptance test`

---

## T6：验收 harness — §2.1 五行 → 测试/脚本

**Files:**
- Create: `tests/test_v1_acceptance.py`
- Create: `scripts/verify_v1_done.sh`

- [ ] **Step 1:** 实现 `scripts/verify_v1_done.sh`（顺序执行下表命令，任一失败 exit 1）

- [ ] **Step 2:** 在 PR/CI 文档中写明：默认 CI = 无 network 子集；发布前跑完整脚本。

| §2.1 Done | 验收命令（实现 P0 后） |
| --- | --- |
| **1** 真实 `ResearchLoop`（非 `FakeBuilder`）→ `COMPLETED` | `ALPHALOOP_ACCEPTANCE_NETWORK=1 pytest tests/test_v1_honest_path.py::test_v1_mean_reversion_reaches_completed_real_ports -v` |
| **2** 运行中/已完成字段来自闭环，无假指标 | `pytest tests/test_v1_acceptance.py::test_running_view_round_fields_from_store tests/test_v1_acceptance.py::test_completed_view_no_placeholder_copy -v` |
| **3** 四门栏 + PIT；否则仅 `research_record` + 缺关说明 | `pytest tests/test_v1_acceptance.py::test_export_strategy_pack_only_when_eligible tests/test_pit_verifier.py -q` |
| **4** zip 通过 schema 且 `live_handoff_eligible: true` | `pytest tests/test_v1_acceptance.py::test_strategy_pack_manifest_validates_against_contract_schema -v` |
| **5** 确定性 reviewer，外部 LLM 不阻塞 | `pytest tests/test_deterministic_reviewer.py tests/test_v1_acceptance.py::test_build_loop_defaults_to_deterministic_reviewer -v` |

**默认 CI（无网络）子集：** `pytest tests/test_deterministic_reviewer.py tests/test_v1_acceptance.py tests/test_export_pack.py tests/test_loop_runtime.py -q`

- [ ] **Step 3:** Commit `test: map v1 cut-line §2.1 to acceptance harness`

---

## 可测 Done 验收清单（复制 v1-cut-line §2.1）

实施完成后，**五条须同时成立**：

1. 锁定五项研究设定，跑通至少一轮真实 `ResearchLoop`（不是 `FakeBuilder`），研究到达已完成（`COMPLETED`）。
2. 运行中 / 已完成工作台上的字段全部来自这一轮闭环。没有空标题，没有假指标。
3. 四条可实盘资格全部通过，含时点第四关，才能导出 `strategy_pack`。缺任何一关，只能导出 `research_record`，并写明缺的是哪一关。
4. 导出的 zip 能通过 `contracts/strategy-pack.schema.json` 校验，且 `live_handoff_eligible: true`。
5. 这条诚实路径钉一个确定性 reviewer（固定 Pass/Fail 策略），接在现有 review 关上。外部大模型的抖动不能卡住 V1 唯一的这条路径。

（与产品设计 §3.7 对齐：UI 展示的四条为「方法全通过 / 无待确认 / 重验成立 / PIT 通过」；引擎 `strategy_pack_eligibility` 另含 `completed` 与 round 存在性，导出 API 在 non-COMPLETED 时本就拒绝 strategy_pack。）

---

## 风险与非目标

**来自 v1-cut-line §3 / §5（不进入 P0 承诺）**

- 开放式 LLM 对话主入口、多策略族挖掘、研究记忆与生产级 harness 工厂、行情终端/实盘下单、替换 Night 七屏、CLI 扩 scope。

**工程风险**

| 风险 | 缓解 |
| --- | --- |
| Review 关仍走 subagent，无 key 时 fail 导致无法 COMPLETED | T1 默认 `deterministic`；CI 断言 `build_loop` 默认 |
| 真实 DataPort 网络 flake | 验收用短窗口 + 1 标的；CI 默认 skip network；重试策略写在 `test_v1_honest_path` |
| `Round`/`RoundV2` 双类型漂移 | T3 单次收敛到 `RoundV2` 入库；export/desktop 同一 helper |
| Scope creep 到 P1 对话 | 仅 keyword `interpret`；不把 P1 归档/消息线程拉入 P0 |
| 桌面视觉改版 | 只删占位文案、补 completed 轮次槽位 |

---

## 建议实施顺序

```text
T0（盘点） → T1（deterministic reviewer） → T2（network acceptance 骨架）
    → T3（RoundV2 持久化 + COMPLETED 数据） → T4（view_for + App fail-closed）
    → T5（export/schema E2E） → T6（harness 与文档命令）
```

T2 与 T3 可并行子代理，但 **T4 依赖 T3** 的真实 round 字段；**T5 依赖 T3** 的 `RoundV2` 导出。

---

## Self-Review（计划自检）

| 检查项 | 结果 |
| --- | --- |
| §2.1 五行均有 T6 命令 | ✓ |
| 未发明第二研究路径 | ✓ 仅扩展 reviewer + 视图映射 |
| 文件路径与 main 一致 | ✓ 已对照 `engine/main.py`, `loop.py`, `export.py` |
| 无 TBD/稍后 | ✓ |
| 不修改 v1-cut-line.md | ✓ |

---

**计划路径:** `docs/plans/2026-10-13-alphaloop-p0-v1-honest-path.md`

**执行选项（实施阶段）：**

1. **Subagent-Driven（推荐）** — 每任务独立子代理 + 任务间审查  
2. **Inline Execution** — 单会话按 `executing-plans` 批量执行并设检查点
