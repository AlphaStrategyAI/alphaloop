# alphaloop 技术设计 v0.1

## 元信息

**执行模式：** 本计划适用于 subagent-driven-development。各任务可由独立 subagent 并行执行，仅在有依赖时顺序进行。状态机测试必须先于其他任务完成。

**目标：** 实现 alphaloop v0.0.1：一个本机优先的投资策略工坊。用户提交模糊方向，系统长时间自主研究，产出经过验证的详细策略包。桌面应用承载全部交互，CLI 仅提供 `start` 和 `status` 两条命令。

**架构概述：** Tauri 2 桌面壳 + React/TypeScript 前端 + Python 3.12 sidecar 引擎。引擎以守护进程运行，关闭桌面不中断研究。前后端通过 JSON Schema 契约通信。

**技术栈：**
- 桌面：Tauri 2 + React 18 + TypeScript 5
- 引擎：Python 3.12 sidecar daemon
- 契约：JSON Schema 定义所有 IPC 消息
- 存储：SQLite + 本地文件系统
- 通知：OS 原生通知（Tauri notification API）
- CLI：仅 `start` 和 `status`，封闭清单

**参考来源：**
- [产品定位](../requirements/product-positioning.md)
- [产品设计 v0.0.1](../requirements/product-design-v0_0_1.md)
- [界面设计 v0.0.1](../requirements/ui-design-v0_0_1.md)
- [Figma 设计稿](https://www.figma.com/design/JXelV0rnUUv5U5w9ur7jtk)
- [Issue #111](https://github.com/AlphaStrategyAI/alphaloop/issues/111)

---

## 全局约束（来自 Issue #111 + 界面设计）

| 约束 | 值 |
|------|-----|
| 画幅 | 1440×900 |
| Rail 宽度 | 148px |
| Logo | 148×148 正方形，与栏同宽 |
| Logo + 导航 | 作为一组纵向居中 |
| Token 集合 | Night / Dark only |
| void | `#07090C` 页面/栏底 |
| glass | `#12161C` 卡片、选中 |
| ink | `#E8EEF5` 主文字 |
| mute | `#8B97A8` 次要文字 |
| line | `#1E2530` 描边分割 |
| cyan | `#5EEAD4` **仅** awaiting_confirm + confirm_run |
| run | `#60A5FA` 运行中 |
| ok | `#34D399` 已完成/通过 |
| stop | `#F87171` 已结束（未通过） |
| hold | `#FBBF24` 已暂停 |
| 交易 UI | 无，不存在下单入口 |
| 有效研究时间 | 仅 running 消耗 |
| 方法编辑 | 生成新 revision，不改旧记录 |
| CLI | 仅 `start` `status` |
| v1 市场 | US + CN |
| v1 资产 | equity / bond / fund |

---

## 架构

### 运行模型

```
┌─────────────────────────────────────────────────────────────┐
│  Desktop (Tauri 2 + React)                                  │
│  ┌─────────┐  ┌──────────────────────────────────────────┐  │
│  │  Rail   │  │  Content Area (七屏)                     │  │
│  │  148px  │  │  - 研究列表 / 草稿 / 确认开跑            │  │
│  │         │  │  - 运行中 / 等待确认 / 已完成            │  │
│  │  Logo   │  │  - 验证方法库                            │  │
│  │  Nav    │  │                                          │  │
│  │  Status │  │                                          │  │
│  └─────────┘  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
        │
        │ JSON Schema IPC (Tauri commands)
        ▼
┌─────────────────────────────────────────────────────────────┐
│  Engine Daemon (Python 3.12 sidecar)                        │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────┐  │
│  │ dialogue  │ │ research  │ │  methods  │ │    clock    │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────┘  │
│  ┌───────────┐ ┌───────────┐ ┌───────────────────────────┐  │
│  │  notify   │ │  export   │ │          store            │  │
│  └───────────┘ └───────────┘ └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  Storage: SQLite + Local Files                              │
│  - research.db (researches, versions, rounds, methods)      │
│  - materials/ (本机材料)                                     │
│  - exports/ (策略包、研究记录包)                              │
└─────────────────────────────────────────────────────────────┘
```

**关键设计：** 关闭桌面应用不停止研究。Engine daemon 独立运行，桌面仅为观察/干预窗口。

### 包结构

```
alphaloop/
├── apps/
│   ├── desktop/           # Tauri 2 + React + TypeScript
│   │   ├── src-tauri/     # Rust 壳 + sidecar 启动
│   │   └── src/           # React 前端
│   └── cli/               # Rust CLI (start, status)
├── engine/
│   ├── dialogue/          # 对话处理、意图识别、slot 管理
│   ├── research/          # 研究循环、版本/轮次管理
│   ├── methods/           # 验证方法库、revision 管理
│   ├── clock/             # TimeBudget、有效研究时间计量
│   ├── notify/            # OS 通知
│   └── export/            # 策略包/研究记录包导出
├── store/                 # SQLite schema、迁移、数据访问
├── contracts/             # JSON Schema 定义（IPC 消息）
└── tests/                 # 测试套件
```

---

## 对话流程控制

### 研究状态机

一条对话 = 一次 Research。六个状态，confirm_run 是 draft 的视图而非第七状态。

```
          ┌─────────────────────────────────────────────────────┐
          │                                                     │
          ▼                                                     │
┌──────────────┐  all slots locked   ┌──────────────────┐       │
│    draft     │ ─────────────────▶  │   [confirm_run   │       │
│              │                     │      VIEW]       │       │
└──────────────┘ ◀───────────────── └──────────────────┘       │
        │           unlock_slot              │                  │
        │                                    │ confirm          │
        │                                    ▼                  │
        │                           ┌──────────────┐            │
        │                           │   running    │────────────┤
        │                           └──────────────┘            │
        │                             │    │    │               │
        │         economic_claim      │    │    │ completed     │
        │         coverage_breach     │    │    ▼               │
        │                             │    │  ┌──────────────┐  │
        │                             │    │  │  completed   │──┘
        │                             │    │  └──────────────┘
        │                             │    │
        │                             ▼    │ budget_exhausted
        │                   ┌──────────────────┐
        │                   │ awaiting_confirm │
        │                   └──────────────────┘
        │                        │    │    │
        │            agree       │    │    │ pause
        │         (new version)  │    │    ▼
        │                        │    │  ┌──────────────┐
        │                        │    │  │   paused     │
        │                        │    │  └──────────────┘
        │                        │    │        │
        │                        │    │        │ resume / modify
        │                        │    │        ▼
        │                        │    │  (back to running)
        │                        │    │
        │                        │    │ reject (continue same version)
        │                        │    └──────────────────────────────▶ running
        │                        │
        │                        └───────────────────────────────────▶ running
        │
        │ budget_exhausted (from running, no pass)
        ▼
┌──────────────┐
│    ended     │
└──────────────┘
```

**状态定义：**

| 状态 | 描述 | 消耗有效时间 |
|------|------|-------------|
| draft | 对话中，设定未齐 | 否 |
| running | 自主研究推进中 | **是** |
| awaiting_confirm | 等待人工确认经济逻辑 | 否 |
| paused | 用户主动暂停 | 否 |
| completed | 产出通过验证的策略 | 否 |
| ended | 时间耗尽/未通过 | 否 |

**confirm_run 不是状态：** 它是 draft 状态下所有五个 slot 都 locked 时的视图。路由 `/research/:id` 根据 `status + brief` 决定渲染哪个屏。

### 路由

```typescript
// 路由表
/research                    // 研究列表屏
/research/:id                // 根据 status + slots 渲染:
                             //   - draft + !all_locked → 草稿屏
                             //   - draft + all_locked  → 确认开跑屏
                             //   - running             → 运行中屏
                             //   - awaiting_confirm    → 等待确认屏
                             //   - paused              → 运行中屏 (暂停态)
                             //   - completed           → 已完成屏
                             //   - ended               → 已结束屏
/methods                     // 验证方法库屏
```

### 两种卡片（绝不合并）

| 卡片 | 出现时机 | 内容 | 选项 |
|------|----------|------|------|
| **ConfirmRun** | draft + all slots locked | 五条设定摘要 + 自主边界说明 | 确认开跑 / 再改改 |
| **AwaitingConfirm** | running → awaiting_confirm | 改什么 / 为什么 / 变成什么样 | 同意开新版 / 不同意继续 / 暂停 |

这是两个独立的 UI 组件和状态转换点，不能合并成一个 modal。

### 五个 Slot

```typescript
interface ResearchSlots {
  thesis: {
    value: string | null;      // 大致原理
    locked: boolean;
  };
  universe: {
    value: {
      market: 'US' | 'CN';
      asset: 'equity' | 'bond' | 'fund';
    } | null;
    locked: boolean;
  };
  max_effective_hours: {
    value: number | null;      // 最长有效研究时间（小时）
    locked: boolean;
  };
  round1_methods: {
    value: MethodRef[] | null; // 第一轮验证方法
    locked: boolean;
  };
  coverage_floor: {
    value: {
      min_years: number;           // 最少历史年数
      max_missing_pct: number;     // 最大允许缺失比例 (0-100)
      required_assets: string[];   // 必须覆盖的资产列表
    } | null;
    locked: boolean;
  };
}

interface MethodRef {
  method_id: string;
  revision_hash: string;       // 冻结的版本
}
```

**侧栏是摘要，不是表单。** 对话区负责收集信息，侧栏只读显示当前状态。

### Draft 阶段意图

| Intent | 描述 | 效果 |
|--------|------|------|
| fill_slot | 填充某个 slot | 更新 slot value |
| lock_slot | 锁定某个 slot | 设置 locked = true |
| unlock_slot | 解锁某个 slot | 设置 locked = false |
| pick_methods | 从方法库选择验证方法 | 更新 round1_methods |
| smalltalk_offtopic | 跑题闲聊 | 拒绝，引导回研究 |
| abandon | 放弃研究 | 仅能从列表删除 |

### confirm_run 原子操作

```python
def confirm_run(research_id: str) -> Result:
    research = get_research(research_id)
    
    # 前置检查
    if research.status != 'draft':
        return Error(409, "research not in draft")
    if not all_slots_locked(research.slots):
        return Error(409, "not all slots locked")
    
    # 原子事务
    with transaction():
        # 1. 状态转换
        research.status = 'running'
        
        # 2. 创建 version 1 快照
        version = create_version(
            research_id=research_id,
            version_number=1,
            slots_snapshot=research.slots,
            created_by='confirm_run'
        )
        
        # 3. 启动研究循环
        start_research_loop(research_id)
        
        # 4. 启动时钟
        start_clock(research_id)
    
    return Ok(research)
```

**授权边界：** confirm_run 授权当前设定，不覆盖后续经济逻辑变更。

### Running 阶段意图

| Intent | 描述 | 处理 |
|--------|------|------|
| pause | 暂停研究 | status → paused, clock.pause() |
| resume | 继续研究 | status → running, clock.resume() |
| change_strategy | 用户要求改策略 | 不在 running 中吸收，需先 pause |
| extend_quota | 延长时间额度 | 更新 max_effective_hours |
| reverify | 对某步重新验证 | 触发 reverify 流程 |
| export | 导出 | 检查资格后导出 |
| economic_claim | 用户提出经济逻辑变更 | **必须**创建 ConfirmRequest |

**关键：** 用户在运行中说「改成加拥挤过滤」属于 economic_claim，不是 smalltalk。必须生成 ConfirmRequest 进入 awaiting_confirm。

### AwaitingConfirm 选项表

| 用户选择 | 效果 |
|----------|------|
| agree | status → running, 创建 version n+1, 应用变更 |
| reject | status → running, 维持当前 version, 仅自动轮次继续 |
| pause | status → paused |

**无超时自动同意。** 用户不在，研究就等着。

**coverage_floor 确认：** 同样的卡片结构，但选项含义不同：
- agree = 接受更低的覆盖底线，开新版
- reject = 不接受，研究寻找其他出路
- pause = 暂停，用户自己处理

### Version vs Round

| 概念 | 触发条件 | 意义 |
|------|----------|------|
| Version | 人工确认经济逻辑变更 | 策略的"这已经是另一回事"边界 |
| Round | 自动的研究/建模/参数迭代 | 同一经济逻辑内的优化尝试 |

```typescript
interface Version {
  version_number: number;
  slots_snapshot: ResearchSlots;
  created_by: 'confirm_run' | 'economic_confirm';
  created_at: timestamp;
  rounds: Round[];
}

interface Round {
  round_number: number;
  changes: RoundChange[];       // 参数/方法微调
  simulation_result: SimResult;
  verification_results: VerifyResult[];
}
```

---

## 研究方法

### 研究循环

```python
def research_loop(research_id: str):
    while is_running(research_id) and has_budget(research_id):
        # 1. Gather
        materials = gather(research_id)
        
        # 2. Specify
        spec = specify(research_id, materials)
        
        # 3. Simulate
        sim_result = simulate(research_id, spec)
        
        # 4. Verify
        verify_results = verify(research_id, sim_result)
        
        # 5. Decide
        decision = decide(research_id, verify_results)
        
        match decision:
            case Decision.COMPLETED:
                complete_research(research_id)
                return
            case Decision.AWAITING_COVERAGE:
                await_confirm(research_id, 'coverage_breach')
                return
            case Decision.AWAITING_ECONOMIC:
                await_confirm(research_id, 'economic_change')
                return
            case Decision.ENDED:
                end_research(research_id, 'budget_exhausted')
                return
            case Decision.CONTINUE:
                append_round(research_id)
                continue
```

### StrategySpec 字段

```typescript
interface StrategySpec {
  thesis_locked: string;           // 不可被 specify() 改变
  universe: Universe;              // 不可被 specify() 改变
  method_set: MethodRef[];         // 不可被 specify() 改变
  
  signal_definition: SignalDef;    // specify 可调整
  entry_rules: EntryRule[];
  exit_rules: ExitRule[];
  position_sizing: PositionSizing;
  parameters: Record<string, any>;
}
```

**specify() 约束：** 不得改变 thesis_locked、universe、method_set。这三者变更必须走 economic confirm。

### Gather 预设

| 预设 | 描述 | 自动切换条件 |
|------|------|-------------|
| lit.public | 公开文献资料 | 默认 |
| data.profile | 数据画像分析 | 需要定量分析时 |
| local.reuse | 复用本机已有材料 | same thesis + same universe |

**自动切换仅在 same thesis and universe 时允许**，否则属于经济逻辑变更。

### 模型家族

| 家族 | 典型方法 | 约束 |
|------|----------|------|
| model.reversion | 均值回归、配对交易 | 不可滑向其他家族 |
| model.momentum | 动量、趋势跟踪 | 不可滑向其他家族 |
| model.spread | 价差、套利 | 不可滑向其他家族 |

**禁止跨家族滑动。** 从 reversion 变成 momentum = 经济逻辑变更，必须确认。

### 变更分类器（必须单元测试）

| 变更类型 | 分类 | 处理 |
|----------|------|------|
| 参数微调 | auto | 自动继续 |
| 同家族特征调整 | auto | 自动继续 |
| 切换 gather 预设 | auto | 自动继续 |
| 在 floor 内缩减覆盖 | auto | 自动继续（记录） |
| reversion + crowding filter 且改变盈利机制 | **economic** | 必须确认 |
| 市场/资产变更 | **economic** | 必须确认 |
| 添加/替换/移除验证器 | **economic** | 必须确认 |
| 调整验证阈值 | **economic** | 必须确认 |
| 会突破 coverage floor | **stop** | 停止，等待确认 |

```python
def classify_change(change: Change) -> ChangeType:
    """
    必须 100% 单元测试覆盖
    """
    if is_param_tweak(change):
        return ChangeType.AUTO
    
    if is_same_family_feature(change):
        return ChangeType.AUTO
    
    if is_gather_switch(change):
        return ChangeType.AUTO
    
    if is_coverage_shrink_within_floor(change):
        record_coverage_shrink(change)
        return ChangeType.AUTO
    
    if changes_profit_mechanism(change):
        return ChangeType.ECONOMIC
    
    if changes_market_or_asset(change):
        return ChangeType.ECONOMIC
    
    if changes_verifiers_or_thresholds(change):
        return ChangeType.ECONOMIC
    
    if would_breach_coverage_floor(change):
        return ChangeType.STOP
    
    return ChangeType.AUTO
```

### decide() 伪代码

```python
def decide(research_id: str, verify_results: list[VerifyResult]) -> Decision:
    research = get_research(research_id)
    
    # 1. 全部验证通过 + 覆盖 OK → completed
    if all(r.passed for r in verify_results) and coverage_ok(research):
        return Decision.COMPLETED
    
    # 2. 会突破 floor → awaiting coverage
    if would_breach_floor(research):
        return Decision.AWAITING_COVERAGE
    
    # 3. 需要经济逻辑变更 → awaiting
    if needs_economic_change(research):
        return Decision.AWAITING_ECONOMIC
    
    # 4. 预算耗尽 → ended
    if get_remaining_budget(research_id) <= 0:
        return Decision.ENDED
    
    # 5. 继续迭代
    return Decision.CONTINUE
```

---

## 验证方法

### 不可变 Revision

```sql
CREATE TABLE methods (
    method_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE method_revisions (
    method_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,  -- sha256(canonical_spec_json)
    spec_json TEXT NOT NULL,      -- 完整的验证方法定义
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (method_id, revision_hash),
    FOREIGN KEY (method_id) REFERENCES methods(method_id)
);

CREATE TABLE research_methods (
    research_id TEXT NOT NULL,
    method_id TEXT NOT NULL,
    revision_hash TEXT NOT NULL,  -- 冻结的版本
    PRIMARY KEY (research_id, method_id),
    FOREIGN KEY (method_id, revision_hash) 
        REFERENCES method_revisions(method_id, revision_hash)
);
```

**revision_hash 计算：**
```python
def compute_revision_hash(spec: dict) -> str:
    canonical = json.dumps(spec, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()
```

**编辑方法 = 插入新行：** 旧 revision 永远存在，已完成研究和已导出策略包引用的是冻结的 hash。

### 运行中方法变更

**属于经济确认：**
- 添加验证方法
- 替换验证方法
- 移除验证方法
- 修改验证阈值

**确认同意后：**
1. 开新 version
2. 可选：标注 origin=research:id（来自某研究的沉淀）
3. **旧轮次的通过结果不延续**，需用新方法集重新验证

### 四个预设验证器

| 验证器 | 描述 | 通过规则 |
|--------|------|----------|
| overfit.walk | 滚动样本外验证 | `sharpe_oos / sharpe_is >= 0.6` AND `sharpe_oos > 0` |
| stability.oos | 样本外稳定性 | `>=3 OOS segments` AND `same_sign_ratio >= 2/3` |
| crowding.load | 拥挤度负载 | top 20% crowding bucket 不拖累 full-sample sharpe < 0 |
| cost.turnover | 换手成本 | 扣除成本后指标仍 > 0 (US: 10bp, CN: 20bp) |

```python
@dataclass
class VerifierSpec:
    id: str
    name: str
    pass_rule: Callable[[SimResult], bool]
    default_params: dict

PRESET_VERIFIERS = {
    'overfit.walk': VerifierSpec(
        id='overfit.walk',
        name='Walk-Forward Overfit Check',
        pass_rule=lambda r: (
            r.sharpe_oos / r.sharpe_is >= 0.6 and r.sharpe_oos > 0
        ),
        default_params={'n_splits': 5}
    ),
    'stability.oos': VerifierSpec(
        id='stability.oos',
        name='OOS Stability',
        pass_rule=lambda r: (
            len(r.oos_segments) >= 3 and
            sum(1 for s in r.oos_segments if s.sign == r.oos_segments[0].sign) / len(r.oos_segments) >= 2/3
        ),
        default_params={}
    ),
    'crowding.load': VerifierSpec(
        id='crowding.load',
        name='Crowding Load',
        pass_rule=lambda r: r.top_20_crowding_sharpe_impact >= 0,
        default_params={'bucket_pct': 20}
    ),
    'cost.turnover': VerifierSpec(
        id='cost.turnover',
        name='Turnover Cost',
        pass_rule=lambda r: r.net_of_cost_metric > 0,
        default_params={'us_bp': 10, 'cn_bp': 20}
    )
}
```

### Re-verify 规则

```python
def reverify(research_id: str, round_id: str, method_id: str) -> VerifyResult:
    """
    重新验证必须使用冻结的 hash 和冻结的数据
    """
    research = get_research(research_id)
    method_ref = get_method_ref(research_id, method_id)
    
    # 使用冻结的方法定义
    frozen_spec = get_method_revision(method_ref.method_id, method_ref.revision_hash)
    
    # 使用冻结的数据
    frozen_data = get_frozen_data(research_id, round_id)
    
    # 执行验证
    result = execute_verification(frozen_spec, frozen_data)
    
    # 失败 = 立即撤销资格
    if not result.passed:
        revoke_export_eligibility(research_id, reason={
            'round_id': round_id,
            'method_id': method_id,
            'reverify_failed': True
        })
    
    return result
```

**失败后果：** 立即撤销策略包导出资格，无"忽略"开关。

### 导出资格

```python
def check_export_eligibility(research_id: str) -> ExportEligibility:
    research = get_research(research_id)
    
    # 必须是 completed 状态
    if research.status != 'completed':
        return ExportEligibility(
            eligible=False,
            kind='research_record',
            tradable=False,
            reason='status_not_completed'
        )
    
    # 三关检查
    checks = {
        'all_methods_passed': all_current_methods_passed(research_id),
        'no_pending_confirm': not has_pending_confirm(research_id),
        'all_reverifies_passed': all_reverifies_passed(research_id)
    }
    
    if all(checks.values()):
        return ExportEligibility(
            eligible=True,
            kind='strategy_pack',
            tradable=True
        )
    else:
        return ExportEligibility(
            eligible=False,
            kind='research_record',
            tradable=False,
            failed_checks=[k for k, v in checks.items() if not v]
        )
```

### 策略包内容（自足）

```typescript
interface StrategyPack {
  // 元信息
  kind: 'strategy_pack';
  tradable: true;
  exported_at: timestamp;
  research_id: string;
  
  // 策略本体
  spec: StrategySpec;
  conclusions: string;
  
  // 冻结的方法定义 blob
  method_definitions: {
    [method_id: string]: {
      revision_hash: string;
      spec_json: string;  // 原样冻结
    }
  };
  
  // 数据溯源冻结
  data_provenance: {
    sources: DataSource[];
    coverage: {
      assets: string[];
      date_range: [string, string];
      missing_pct: number;
    };
    floor_at_confirm: CoverageFloor;
    shrink_log: ShrinkEvent[];
  };
  
  // 版本/轮次历史
  version_history: Version[];
  
  // 声明
  disclaimer: string;  // 标准文案：研究成果，非投资建议
}
```

---

## TimeBudget

```python
class TimeBudget:
    def __init__(self, research_id: str, max_hours: float):
        self.research_id = research_id
        self.max_seconds = max_hours * 3600
        self.used_seconds = 0
        self.running = False
        self._last_tick = None
    
    def start(self):
        """confirm_run 时调用"""
        self.running = True
        self._last_tick = time.time()
    
    def pause(self):
        """暂停或进入 awaiting_confirm 时调用"""
        if self.running:
            self._accumulate()
            self.running = False
    
    def resume(self):
        """从 paused 或 awaiting_confirm 恢复时调用"""
        self.running = True
        self._last_tick = time.time()
    
    def tick(self):
        """running 状态下周期性调用"""
        if self.running:
            self._accumulate()
    
    def _accumulate(self):
        now = time.time()
        if self._last_tick:
            self.used_seconds += now - self._last_tick
        self._last_tick = now
    
    @property
    def remaining(self) -> float:
        return max(0, self.max_seconds - self.used_seconds)
    
    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0
```

**仅 running 消耗时间。** draft、awaiting_confirm、paused、completed、ended 都不消耗。

---

## v1 通知

仅两类本机系统通知：

| 事件 | 通知内容 |
|------|----------|
| 进入 awaiting_confirm | "研究 [name] 需要你确认" |
| completed / ended | "研究 [name] 已完成/已结束" |

```python
def send_notification(event: NotifyEvent):
    match event.type:
        case 'awaiting_confirm':
            notify_os(
                title='alphaloop',
                body=f'研究「{event.research_name}」需要你确认'
            )
        case 'completed':
            notify_os(
                title='alphaloop',
                body=f'研究「{event.research_name}」已完成'
            )
        case 'ended':
            notify_os(
                title='alphaloop',
                body=f'研究「{event.research_name}」已结束'
            )
```

---

## 七屏与 API 映射

| # | 屏 | Figma node | 主要 API |
|---|-----|------------|----------|
| 01 | 研究列表 | [1:119] | `GET /researches`, `DELETE /researches/:id` |
| 02 | 草稿 | [12:13] | `GET /researches/:id`, `POST /researches/:id/dialogue`, `PATCH /researches/:id/slots` |
| 03 | 确认开跑 | [5:32] | `POST /researches/:id/confirm` |
| 04 | 运行中 | [9:13] | `GET /researches/:id/progress`, `POST /researches/:id/pause` |
| 05 | 等待确认 | [6:61] | `GET /researches/:id/pending_confirm`, `POST /researches/:id/confirm_response` |
| 06 | 已完成 | [10:13] | `GET /researches/:id/results`, `POST /researches/:id/reverify`, `POST /researches/:id/export` |
| 07 | 验证方法库 | [11:13] | `GET /methods`, `POST /methods`, `PATCH /methods/:id` (creates new revision) |

---

## 文件树

```
alphaloop/
├── apps/
│   ├── desktop/
│   │   ├── src-tauri/
│   │   │   ├── Cargo.toml
│   │   │   ├── tauri.conf.json
│   │   │   ├── src/
│   │   │   │   ├── main.rs
│   │   │   │   ├── commands.rs      # IPC 命令
│   │   │   │   └── sidecar.rs       # Python 进程管理
│   │   │   └── icons/
│   │   ├── src/
│   │   │   ├── App.tsx
│   │   │   ├── routes/
│   │   │   │   ├── ResearchList.tsx
│   │   │   │   ├── ResearchView.tsx
│   │   │   │   └── MethodsLibrary.tsx
│   │   │   ├── components/
│   │   │   │   ├── Shell/
│   │   │   │   │   ├── Rail.tsx
│   │   │   │   │   ├── Logo.tsx
│   │   │   │   │   ├── Nav.tsx
│   │   │   │   │   └── HostStatus.tsx
│   │   │   │   ├── Research/
│   │   │   │   │   ├── DraftScreen.tsx
│   │   │   │   │   ├── ConfirmRunCard.tsx
│   │   │   │   │   ├── RunningScreen.tsx
│   │   │   │   │   ├── AwaitingConfirmCard.tsx
│   │   │   │   │   ├── CompletedScreen.tsx
│   │   │   │   │   └── SlotsSummary.tsx
│   │   │   │   └── Methods/
│   │   │   │       ├── MethodList.tsx
│   │   │   │       └── MethodDetail.tsx
│   │   │   ├── hooks/
│   │   │   ├── stores/
│   │   │   └── styles/
│   │   │       └── tokens.css       # Night/Dark tokens
│   │   ├── package.json
│   │   └── vite.config.ts
│   └── cli/
│       ├── Cargo.toml
│       └── src/
│           └── main.rs              # start, status 命令
├── engine/
│   ├── dialogue/
│   │   ├── __init__.py
│   │   ├── intents.py
│   │   ├── slots.py
│   │   └── classifier.py
│   ├── research/
│   │   ├── __init__.py
│   │   ├── loop.py
│   │   ├── state_machine.py
│   │   ├── version.py
│   │   └── round.py
│   ├── methods/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── revision.py
│   │   └── presets.py
│   ├── clock/
│   │   ├── __init__.py
│   │   └── budget.py
│   ├── notify/
│   │   ├── __init__.py
│   │   └── os_notify.py
│   └── export/
│       ├── __init__.py
│       ├── strategy_pack.py
│       └── research_record.py
├── store/
│   ├── __init__.py
│   ├── schema.sql
│   ├── migrations/
│   └── access.py
├── contracts/
│   ├── research.schema.json
│   ├── methods.schema.json
│   ├── dialogue.schema.json
│   └── export.schema.json
└── tests/
    ├── test_state_machine.py        # 必须首先完成
    ├── test_classifier.py           # 变更分类器 100% 覆盖
    ├── test_dialogue.py
    ├── test_methods.py
    ├── test_research_loop.py
    └── test_export.py
```

---

## 实现任务

按依赖顺序，状态机测试必须先行：

- [ ] **1. 状态机测试** — `tests/test_state_machine.py`，覆盖全部六状态 + confirm_run 视图，全部转换路径
- [ ] **2. 变更分类器测试** — `tests/test_classifier.py`，100% 覆盖分类表，auto/economic/stop 分类准确
- [ ] **3. 对话模块** — `engine/dialogue/`，意图识别、slot 管理、五条设定收集
- [ ] **4. 验证方法模块** — `engine/methods/`，revision 管理、四个预设验证器、hash 计算
- [ ] **5. 研究循环** — `engine/research/`，gather→specify→simulate→verify→decide 循环
- [ ] **6. 时钟模块** — `engine/clock/`，TimeBudget 仅 running 计时
- [ ] **7. UI 壳** — `apps/desktop/`，Rail + Logo + Nav + HostStatus，Night/Dark tokens
- [ ] **8. 七屏实现** — 按 Figma 顺序：列表 → 草稿 → 确认开跑 → 运行中 → 等待确认 → 已完成 → 方法库
- [ ] **9. 导出模块** — `engine/export/`，策略包/研究记录包，资格检查
- [ ] **10. CLI** — `apps/cli/`，仅 `start` 和 `status`
- [ ] **11. 通知集成** — `engine/notify/`，awaiting_confirm + completed/ended 两类

---

## 自检表：产品条款 → 技术设计

| 产品条款 | 设计位置 |
|----------|----------|
| 一条对话一次研究 | 研究状态机、路由 |
| 六个状态 | ResearchStatus enum |
| confirm_run 不是第七状态 | 视图定义、路由逻辑 |
| 五个 slot | ResearchSlots interface |
| 确认开跑原子操作 | confirm_run() 函数 |
| 经济逻辑必须确认 | 变更分类器、AwaitingConfirmCard |
| 验证方法变更 = 经济 | classify_change() |
| 版本 vs 轮次 | Version/Round 数据模型 |
| 方法 revision 不可回改 | method_revisions 表、hash |
| 重验失败撤销资格 | reverify() 函数 |
| 策略包自足 | StrategyPack interface |
| 仅 running 消耗时间 | TimeBudget 类 |
| CLI 仅两条命令 | apps/cli 实现 |
| v1 两类通知 | notify 模块 |
| 无交易 UI | 全局约束、已完成屏 |
| Night/Dark tokens | tokens.css |
| cyan 仅两处 | 全局约束、组件实现 |
| Rail 148 + Logo 148×148 | Shell 组件 |
| 两张卡片不合并 | ConfirmRunCard + AwaitingConfirmCard |
