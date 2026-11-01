# 对话驱动策略研究实施计划

**状态**　待实施。代码基线为 `main@5866c23`，产品版本为 0.9.5。下列 PR、接口增量、故障注入点和验收数字均为计划项。产品行为见[配套设计](../designs/2026-11-01-dialogue-driven-strategy-research.md)。

**目标**　用户在同一条研究对话中给出想法、核对系统理解、确认运行、查看进展、决定是否改变假设、重验并取走有据可查的结果。首批执行范围为已接通的日频均值回归。

**实现边界**　React/Tauri 负责交互，Python sidecar 独占状态迁移与研究执行，SQLite 保存可恢复的记录。沿用六个研究状态、`ResearchLoop`、冻结定义和导出资格。实现者可按下列 PR 使用 `subagent-driven-development` 或 `executing-plans` 逐项交付。

## 1　从现有主链开始

- **入口。** `apps/desktop/src/desktopApi.ts:createTauriDesktopApi` 调用 `apps/desktop/src-tauri/src/commands.rs`，随后是本地 `POST /commands`、`engine/main.py:ResearchCommandService.handle` 和 `_dispatch`。当前 `send_dialogue` 接收原文。`engine/dialogue/turns.py:process_send_dialogue` 和 `intent.py:interpret` 按槽位取值，非草稿消息进入 `modification.py:process_modification_dialogue`。通用运行问答、结构化提议回执和跨轮指代需新增。
- **开跑。** `engine/research/models.py:ResearchBrief` 已有论点、资产范围、最长有效时长、验证方法、覆盖底线五项。`engine/research/run_gate.py:evaluate_run_gate` 判定家族、标的、来源及必要同意，`ResearchCommandService._confirm_run` 还探测数据覆盖。`state_machine.py:transition` 负责草稿、运行、待确认、暂停、完成、结束六态以及开新版。确认卡、对话里的确认动作必须走同一命令。
- **研究。** `engine/main.py:serve` 每秒顺序推进在库的运行中研究。`engine/research/loop.py:DefaultRoundBuilder.build/retry` 获取输入、形成规格、执行日频模拟和修订号对应的验证，然后 `engine/review/subagent.py:run_review_gate` 评审候选。当前默认候选是 20 日回看，每次修复或后续轮次增加 5 日。`build_loop` 使用确定性 reviewer，只有 `ALPHALOOP_REVIEWER=subagent` 时调用已配置的兼容端点。默认 reviewer 接受受支持家族的候选，方法是否通过仍由验证器判定。
- **数据与判定。** `engine/research/gather.py` 有 Crossref、SEC 发行人目录和本地 Markdown 资料适配器。SEC 这一口仅检索发行人信息。`data_port.py:data_port_for_research` 支持已绑定的 Yahoo/AkShare 来源。`frozen_input.py:ensure_frozen_version_input` 按研究和版本原子保存价格、基准和资料，每轮另有 CSV。`simulate.py:simulate_daily` 通过 `engine/strategy.py:daily_book` 使用前一日信号、持仓与换手成本，输出收益、回撤、分段样本外指标等。`engine/verifiers.py:run_verifiers` 执行固定 Scorecard、所选修订和 PIT。当前 PIT v2 只检查所引资料发布日期是否晚于回测截止日，无引用时可单独通过。无法据此声称股票池、复权或财报修订都满足逐日时点要求。
- **迭代与历史。** `honest_stop.py` 默认每版 5 个实现轮，手动追加 5 轮。相同数据窗口的跨研究累计轮数 M 达到默认 20 时，追加需再确认。`clock.py:TimeBudget` 计有效时长。`SQLiteStore` 已保存研究快照、评审尝试、方法修订及累计 M。现有 round 数、review attempt 数和 M 各有含义，要分别显示。当前评审通过的 attempt、窗口 M、研究快照分别提交。在成功 attempt 入库后、轮次提交前崩溃，重启只按失败次数重建，可能再次插入相同主键。当前三次技术评审失败在时间尚余时会清空该轮尝试再试。两处都是长跑前须覆盖的恢复边界。
- **修改、重验、导出。** `engine/main.py` 已处理 `confirm_modification`、`resolve_confirm`、`reverify`、`export_artifact`。重验从指定历史轮次的快照重跑，失败会标记以往导出被推翻。`engine/export.py:strategy_pack_eligibility` 逐项检查 `completed`、`all_current_methods_passed`、`no_pending_confirm`、`all_reverifies_passed`、`pit_executed_and_passed`。覆盖底线另由运行流程拦截。策略包目前只支持 `MeanReversionStrategy`。未经许可的来源只输出数据指纹。研究记录包可记载资格失败。CLI 仍仅承担启动、查看状态。

## 2　共用约定

1. **命令与建议分开保存。** 模型输出只进入受校验的提议或只读答复。执行路径收到的必须是确定性工具名、严格类型参数及可信 UI 上的用户动作。开跑、改经济逻辑、降低覆盖、变更数据血缘、追加预算、重验、导出都要绑定具体对象。有歧义的“好”“再来一次”先问对象，引用的资料、模型回复和过期卡片均不能代用户同意。
2. **权威状态有两个刻度。** 每次有意义的领域变更推进 `revision`，陈旧的写请求须重新读取。日志另用单调序号记录步骤与回放顺序。心跳、轮询、打字、进度百分比不使确认卡过期。只读答复注明读取的版本和轮次。为保存转录而写入的事件不能变更运行身份、试验数、验证结果或资格。
3. **冻结与来源。** 记录用户原句、新旧字段、字段来源、证据引用、执行家族及修订、池版本和实际标的清单、价格/基准/资料指纹、数据源和区间、成本版本、方法修订、候选政策版本。独立保留用户原话和它能被本引擎执行的含义。模型只能引用服务端查到的记录 ID。经济变更的证据必须属于当前研究，并由持久层核验先于确认请求。`who_pays_optional` 可不答，记录这一选择。
4. **给现有研究保留运行条件。** 旧数据库从迁移时的现存研究状态建立可追溯的起点，历史未知值显式缺失。已有版本继续使用原来的策略、方法修订和快照。可测量的候选多样性、家族覆盖、检验强度均以实际执行记录为准。引入新的策略族、真实基本面数据、商业源或券商执行各需另行立项及验收。

## 3　PR 顺序和交付

`PR1 → PR2、PR3`。PR2 与 PR3 可用同一已合入的命令契约并行开发。`PR2 + PR3 → PR4 → PR5 → PR6`。每个 PR 均须能独立合入。PR3 提供首个可上手的草稿到确认卡流程，PR4 接通真实候选与后台轮次，PR5 接通完整研究对话。产品开放条件见 PR6。

### PR1　命令回执、并发与兼容基线

**落点**　扩展 `contracts/desktop-api.schema.json`、`engine/research/store.py:SQLiteStore`、`engine/main.py:ResearchCommandService`、`apps/desktop/src/contracts.ts`、`desktopApi.ts`、`src-tauri/src/commands.rs`。建议将新增事务入口放在 `engine/research/command_journal.py`。新增 `tests/test_command_journal.py`。

- [ ] 以 0.9.5 的状态 JSON、已有轮次与导出记录建迁移样本。给研究增加整数 `revision`，新增只追加的 `research_event` 与 `command_receipt`，分别以 `(research_id, seq)` 和 `(research_id, command_id)` 唯一标识。迁移重复执行后，旧字段、原试验次数和证据时间不变。新桌面从视图取到当前 revision。旧客户端仍可按原入口处理其能展示的对象，不能批准新式提议。
- [ ] 首次创建也由客户端预分配 research_id，创建回执和研究行同事务。模拟第一次 create 响应丢失并重启重发，研究列表只能有一条。对研究写命令接入 `command_id` 和 `expected_revision`。`send_dialogue` 另带可选 `reply_to` 指向当前提议。前端在**一次用户操作**生成稳定 UUID，超时重发保留相同 ID 和负载。回执存规范化请求摘要、结果 ID、返回 revision。事务先查同 ID 的回执，再校验版本。同 ID 同负载返回原回执，同 ID 不同负载拒绝，版本冲突返回当前 revision 供展示差异。用户再次确认后才能用新 ID 提交。保留现有 `fetch_view` 及老客户端已支持的按钮入口，显式测试兼容分支，新增对话写路径必须提供这两个字段。
- [ ] 在同一 SQLite 事务完成状态 CAS、领域事件、回执写入。对远端调用先在短事务领取唯一 operation key 并预留预算，同 ID 在途回复 pending。耗时的行情探测、LLM 和文件生成在事务外进行，提交前再次校验绑定的 revision、研究版本或快照。把“开跑”先贯穿三层，既有确认检查继续生效。
- [ ] 新测试覆盖双击、两个客户端同时提交不同 ID、服务端提交后断连接、重启再重放、同 ID 换负载、旧库回读及相同秒内两次写。两次并发开跑只能生成一个版本。回归命令如下。

```sh
python -m pytest -q tests/test_command_journal.py tests/test_desktop_api_schema_contract.py tests/test_engine_http_concurrency.py tests/test_draft_confirm_run_e2e.py
(cd apps/desktop && npm test)
```

### PR2　轮次提交、预算和重启恢复

**落点**　`engine/research/loop.py:ResearchLoop._run_once_bound`、`store.py`、`clock.py:TimeBudget`、`frozen_input.py`、`data_window.py`、`honest_stop.py`、`engine/review/subagent.py:run_review_gate`、`engine/main.py:advance_running_research`。新增 `tests/test_round_recovery.py`。

- [ ] 新增 `step_run(research_id,version,round,attempt,step,input_hash,status,result_ref)`，前六字段组成唯一执行键。先记待执行候选与输入指纹，再调用模拟。按研究隔离快照及重试路径，采用临时文件、哈希和原子替换。材料按内容摘要写不可变文件，每条引用保存来源、定位、发布日期/精度、获取时间、权利范围及内容摘要。以同 DOI 内容更新为例，V1 与 V2 必须分别能按哈希读回当时的文本。恢复时已存在且哈希匹配的输入直接复用，缺失或损坏时暂停并给出原因，禁止静默换源、换日期或改用模拟数据。
- [ ] 在 SQLite 的单个提交中写接受轮次、所用 attempt、方法使用记录、该轮唯一的窗口计数贡献、停止/确认决定和状态 revision。先前已写下的尝试通过稳定 ID 引用。按唯一轮记录增加 M，重放返回同一结论。同轮的失败尝试保留为历史。技术重试另增计数并限定重试次数，超限转既有暂停态，给出可恢复原因。
- [ ] 首期只运行一个计算 worker，为每项研究隔离计时片和预算预留。以单调时钟每 5 秒持久化有效片段，重启最多漏计一个心跳片段。等待该 worker 的其他 RUNNING 任务不扣时。默认实现轮上限、追加确认和高怀疑提示沿用现有政策。分别记录候选数、已提交轮数、当前窗 M、有效秒数以及模型调用/技术重试限额。在规划、取数、模拟、调用评审前检查剩余量。对未能确认是否已付费的超时调用保守计入上限。暂停、待确认、进程离线不累计。同时排队的两项研究互不借用预算。并发暂停后迟到的 worker 结果按期望版本丢弃或暂存，不得自行复跑或覆盖新状态。
- [ ] 测试子进程在以下屏障发出就绪消息，由父进程杀掉并用同一临时数据库重启。屏障依次位于冻结文件原子替换后、成功评审后但轮次提交前、轮次提交后但收到回执前。另注入重复 tick、损坏快照、数据库繁忙、运行中暂停和删除。每条断言比较记录 ID、CSV 指纹、M、预算和最终回执。同一候选最多有一次已提交结果。本地可重算步骤允许重试。远端付费调用若发送后失联，持久化 unknown 并保守占用预算；有服务商幂等保证才允许按原键恢复，否则重发须另行授权。并发同 ID 的测试直接统计假服务接收到的请求数，再在服务器已收而响应未到时杀掉 sidecar。Windows 子进程使用等价终止 API。

```sh
python -m pytest -q tests/test_round_recovery.py tests/test_loop_runtime.py tests/test_effective_time_budget.py tests/test_cumulative_trials.py tests/test_a1_family_frozen_input.py tests/test_delete_running_research.py
```

### PR3　把自由表达变成可核对的研究提议

**落点**　`engine/dialogue/turns.py`、`intent.py`、`slots.py`、`engine/research/run_gate.py`、`llm_config.py:resolve_llm`，新增 `engine/dialogue/proposal.py`、`tests/test_dialogue_proposals.py`。草稿与确认页面经 `apps/desktop/src/App.tsx`、`screens/ConfirmRunScreen.tsx` 和现有 bridge 接入。

- [ ] 在现有 `send_dialogue` 路径增加可注入的 `propose(context) -> Proposal` 与带判别字段的封闭 schema。内容至少含提议 ID、基础 revision、用户原话引用、意图、带类型的五项设定变更、每项的来源、未决问题及能力匹配。将用户指定、从数据得出、系统建议和待确认区别显示。未提到时不要填入“用户已同意”。一次追问优先消除会改变策略含义的问题，允许批量补全、纠正、撤回和跨轮指代。
- [ ] 已配置且获准的 LLM 只产出受 schema 限制的对象。草稿调用总时限 12 秒，输入最多 4,000 字。例句中的“只在同行业内比较，第三天卖出”必须把行业数据和卖出机制两条限制逐项对照能力清单。对白解析失败、超时、无密钥、额度不足，交还现有字段级提问，并在对话中显示差异或缺项。模型无权传入 shell、SQL、路径、任意 URL、工具调用或伪造证据。服务端重新解析市场和标的，核对本机支持家族/数据源，核验费用、窗口和覆盖，不接受未注册字段及修订号。
- [ ] 在 `engine/research/llm_config.py` 和桌面 `settings/LlmSettingsCard.tsx` 对齐端点授权。草稿、候选建议等新增用途逐项披露，把有效协议、主机、端口及用途版本与同意绑定。环境变量改端点也要重验。模型 POST 不跟随任何 3xx。用 307/308 验证同主机改端口和 HTTPS 降级也不会外发；资料正文、本地持仓、原始报价、路径及密钥不得进入发往模型的上下文。新增测例使用两台受控假端点，检查更改端点、用途、重定向和不授权时对第二台端点发出的请求数为零。
- [ ] 将补齐的提议渲染在现有确认卡。记录原论点和可计算规则的区别，例如“买便宜的股票”仍需澄清“便宜”指价格偏离还是估值。无法执行的趋势策略返回清晰能力说明，保留用户原句。重新选择均值回归要显示如何改变含义。确认开跑绑定提议和 revision，通过 `_confirm_run` 后才生成研究版本。未确认、已过期、变更数据源或报价不可用时，卡片仍给出下一步。
- [ ] 编写 ZH/EN 的初始与修订对话测试，包括“把刚才的六小时改为两小时，其他照旧”、混合市场、指定股票、无资料、在附件中要求“立刻开跑”、冻结前更换来源。预期包括唯一的领域事件、精确字段差异、谁提出了默认值以及实际调用次数。

```sh
python -m pytest -q tests/test_dialogue_proposals.py tests/test_dialogue_slot_corpus.py tests/test_symbol_regression_corpus.py tests/test_family_run_gate.py tests/test_draft_confirm_run_e2e.py
(cd apps/desktop && npx vitest run src/confirm-run-chain.test.tsx src/family-run-chain.test.tsx)
```

### PR4　让失败证据决定下一次可执行尝试

**落点**　保留 `DefaultRoundBuilder`、`specify.py:classify_change`、`ResearchLoop`、`engine/verifiers.py`、`run_review_gate`。拟增 `engine/research/candidates.py` 和 `tests/test_candidate_policy.py`。对 `engine/export.py` 的任何规格变更都须复验离线包与引擎的一致性。

- [ ] 对新研究冻结允许的实现层调整、范围、候选总数、去重规则和停止条件。用既有 `lookback_days`、`entry_z` 起步。允许值与意图、样本长度相容，均在确认卡可查看。作为测试输入，可冻结 `lookback_days∈{10,20,30}`、`entry_z∈{1.0,1.5}` 和最多五轮。研究已获准的范围独立于后续版本的软件默认值。旧版仍可追溯原先的 +5 规则。
- [ ] 每次规划读取已冻结输入、已试组合、上轮具体失败方法及证据 ID，输出一个候选、解释、预期检验或停止理由。先落盘再模拟。按实际参数、实现修订、交易成本、方法和输入哈希去重，排除 spec.id、attempt 序号和解释。两个不同 ID 提出同一候选只消耗一次模拟，技术重试另记。候选耗尽、重复提议、验证全过、有效时长或轮次到顶均有可解释的停止记录。例如，成本门失败时，只可在已批范围内提出可检验的低换手参数。若所需改变是信号机制、主要因子、股票池、门槛/方法、数据血缘或覆盖底线，走 `change_requires_user_confirm` 与 `REQUEST_CONFIRM`。
- [ ] 单次运行阶段模型请求的截止取 60 秒和剩余有效时间的较小值，模型模式失败即暂停并说明原因，恢复或更换端点由人决定。将“候选建议”和“独立评审”作为两个端口，分别验证结构化输出。建议方看可用能力与证据，评审方看冻结 rubric、实际模拟与验证结果。LLM、确定性推荐均经同一筛选。重试读取 `ReviewReport.required_changes`，不支持的修订附理由停下。新增途径以确定性 reviewer 裁决，模型审阅意见单独存证。模型输出的“通过”不能改变 `run_verifiers`、PIT 或导出结论。资料内容只作数据，持久记录引用 ID、修订和必要摘要，日志沿用现有密钥脱敏。
- [ ] 用同一冻结面板运行“先失败后成功”和“全部失败”两条全链。另一组让模型反复提出相同候选、放宽门槛、选未实现家族、提出未来证据或返回非法 JSON。验收为有不同的已执行 spec、预算与 M 可重算、越界执行数为零，并且无模型配置时仍能通过现有均值回归回归用例。探索段全绿只触发冻结胜者；最终资格由 X2 的行情保留段另验。合格样例的成本计算与导出 runner 比较精度沿用已有测试。

```sh
python -m pytest -q tests/test_candidate_policy.py tests/test_reviewer.py tests/test_honest_stop.py tests/test_economic_confirm_evidence_real_loop.py tests/test_pit_v2.py tests/test_verifier_revision_dispatch.py tests/test_a2_weights_costs.py
```

### PR5　把运行问答、修改、重验与导出接回同一条对话

**落点**　拟增 `engine/dialogue/actions.py`、`tests/test_dialogue_actions.py`。复用 `ResearchCommandService.view_for/_dispatch`、`engine/research/confirm_evidence.py`、`state_machine.py`、`engine/export.py`。桌面复用 `ResearchListScreen`、`RunningScreen`、`AwaitingConfirmScreen`、`CompletedScreen`，按钮与对话提交 PR1 同一命令。

- [ ] 将“现在在做什么”“哪一关没过”“已经试过多少个”“和上一版有何差别”路由至只读投影。用记录 ID 引用具体版本、轮次、方法修订、实际值、阈值或最后一次动作。缺数据答“尚无已提交轮次/无此指标”。问答和建议能在六态发生，允许的执行命令由状态机逐一列举。运行中“先看看”只读。“改逻辑”生成待核对提议，用户确认暂停并改版后执行，当前运行里的活动 brief 不被悄悄修改。
- [ ] 待确认卡携带服务端持久化的 `request_id`，展示改前/改后、影响、确认前证据、“谁持续支付收益”可选回答及拒绝路径。批准、保持原逻辑、暂停分别复用 `resolve_confirm` 的既有选择。超时后重放绑定原 ID。旧版本卡片或跨研究引用拒绝。相同参数的“继续迭代”消耗本版追加配额。改经济逻辑、血缘、经确认的覆盖或验证定义开新版，冻结历史可在同一研究中查到。
- [ ] “重验上一轮的稳定性”先解析唯一 `round_id/method_id/revision`，歧义时给候选选择。复用 `reverify` 验证快照哈希、原资料与原方法修订，写入重验记录。失败按版本/轮次/方法修订/输入哈希关联受影响的策略包。修复现有资格检查排除 PIT 重验、mark_exports_overturned 无差别标记所有包的问题。断言“原 PIT 过、该轮 PIT 重验不过”拒绝交接，“无依赖的旧轮失败”不误标其他包，开新版后仍查得到旧审计。重验不得增加实现轮数或窗口 M。“导出”显示当前可导出的类型和失败检查，确认策略包时服务器再次执行 `strategy_pack_eligibility`。给该函数增设独立的 `coverage_satisfied` 检查，从冻结底线和当前有效的实测覆盖计算。现有五个布尔项保留并按 E3 修正重验语义。新自适应版本还核验 X2 的证据分级与最终评价，任何缺项均列出具体理由。历史记录缺少覆盖实测值时保留原因，只提供研究记录。新增测例构造其余五项都通过且覆盖不足的状态，直接调用 API 仍应拒发策略包。同一导出请求只保留一个回执和文件指纹，现有来源许可、两种包 schema、运行脚本均须满足。
- [ ] 导出用命令 ID 标识私有暂存文件和最终路径。在提交授权前再次按修订和依赖核验全部资格，SQLite 短事务登记授权发布快照/指纹，此刻算交接。之后才原子更名到可见目录，记录发布回执。恢复须有授权行且哈希匹配，绝不能单凭已有 ZIP 完成请求。注入“私有文件就绪→PIT 失败→恢复”，可见目录没有策略包；再注入“已授权→崩溃”，只恢复原回执；已交接后翻案则标记其历史包。文件缺失或内容不符返回可诊断错误。拒绝资格时先写原因，不创建可交接包。已分发包以历史指纹引用，推翻信息在本地研究账本可查。
- [ ] 对话可检索并建议方法库内可执行的 `MethodRef`，方法定义通过 `engine/research/methods.py` 的创建、修订、使用记录接入。引入已登记算子时先用金标准输入跑通过/失败两组样例，新版批准后冻结新修订。未实现的算法存为建议，不能执行或计作通过。对此加测旧版重验复现旧阈值、跨研究显式选择新修订、未登记修订拒执行。
- [ ] 双语桌面测试把自由文字和原按钮跑出相同状态变化。E2E 固定一条研究 ID，经确认、运行、暂停恢复、查看失败证据、批准新版、重验、导出。分别加载资格全过和资格失败两种确定性数据，比较包内方法、数据指纹和轮数与对话所报的一致性。

```sh
python -m pytest -q tests/test_dialogue_actions.py tests/test_modification_confirm_dialogue.py tests/test_b4_sqlite_confirm.py tests/test_reverification_version_reset.py tests/test_research_record_export.py tests/test_export_pack.py tests/test_unlicensed_source.py
(cd apps/desktop && npm test)
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
```

### PR6　留出评测、安装包、启用及回退

**落点**　`tests/data/dialogue_slot_corpus.json` 和 `symbol_regression_corpus.json` 用作现有开发回归。另建人工标注的多轮留出集与拟增的 `tests/test_research_dialogue_holdout.py`。更新 `docs/requirements/release-acceptance-v1.md`、Windows 安装包测试 `apps/desktop/e2e/windows_gui_e2e.py` 的功能行。验收记录保存构建 SHA、模型/提示词/能力表修订、运行模式、样本分母和失败样本 ID。

- [ ] **冻结留出集。** 建议初始门槛为 120 条完整会话，草稿补充/更正、能力不符/歧义、运行问答、经济/血缘/覆盖确认、重验/导出、断线重放各 20 条。每组中英各 10。按作者和意图模板分组切分，重复改写归同一组。评测负责人在调提示词前封存标签及 SHA，开发阶段只看开发集。每条标出预期字段来源、允许工具、必须追问/禁止动作、下一状态、引用对象。分歧复核后锁版。失败例进入下一版开发集时另补同类留出。
- [ ] **可量化出口。** 建议首轮要求每组至少 18/20 会话完成标注的全段状态序列，总计至少 114/120。所有危险反例、跨研究引用、陈旧确认、工具越权、虚报收益和未获准开跑/改版目标准确拦截率 100%。同一留出集先评 0.9.5 规则基线，再评新解释器，报告字段采纳/纠正准确率、错误启动率、额外追问次数及 p50/p95 延迟。逐语言、逐类列分母和误判例。按未配置、模拟端点、真实获准端点分别报告。保留原始 schema 判定及后端真实事件。真实模型变更、提示词或工具契约变化后复测。以上是发布门槛建议，非本次已获得成绩。
- [ ] **从安装包验收。** 对同一构建，Linux 与 macOS 运行现有完整矩阵，分别至少一次用真实美股和 A 股来源经确认取得数据，另用可控面板稳定复现成功与失败导出。Windows 运行安装包 GUI 加强项并记录 CI 作业。单测/合成离线数据和真实行情验收分别列出。真机再跑一条获准使用真实模型的会话与一条无端点会话，保存脱敏的对话、回执、快照及导出摘要。重新打开桌面验证旧记录、暂停任务、未决卡片、重放请求，测断网、端点超时、sidecar 终止重启。一致性以 SQLite 和包指纹为准。
- [ ] **灰度与回退。** 新对话能力初期显式启用，方式随同本 PR 写进设置/打包说明。功能关闭时用旧规则入口和既有按钮。运行中的版本沿用冻结 planner/方法修订，未知修订安全暂停。升版前用 SQLite 一致性备份并保存关联快照，校验备份可在临时数据目录恢复。先在内部安装包跑完整矩阵，再给自愿用户启用，最后才考虑默认开启。一次越权执行、重复开版/未授权重复外发/重复累计 M、冻结数据漂移或丢失已提交回执即关闭新增写入口并保留 journal。恢复旧二进制前验证它能安全读写迁移库。未验证则只回退功能开关，或在副本恢复升版前备份并单独保全升版后记录。

```sh
# 在已装项目 dev 依赖的 Python 3.12 环境执行。新测试随对应 PR 加入。
python -m pytest -q -m "not network"
python -m pytest -q tests/test_research_dialogue_holdout.py
(cd apps/desktop && npm test && npm run build)
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
ALPHALOOP_ACCEPTANCE_NETWORK=1 python -m pytest -q tests/test_v1_honest_path.py
```

最终验收以安装包中的同一条研究为单位。能从对话读回用户批准的明确规则、后台实际尝试、失败证据、预算余额与导出回执，并能在进程重启后核对同一份数据和结论，才勾选交付完成。

## 工程评审记录与实施任务

两个评审对象均为本日期的配套设计与本计划，基线已与 origin/main 核对。范围沿用“一个人、一台机器、桌面对话到可导出研究”；实盘交易、全市场数据授权和通用代码沙箱另有边界。工程问题按用户要求依据产品定位及第 1 节调研自主决定。本节的“已采纳”指写入实现规格，完成实现时须留下测试证据。

- [ ] **E1 / PR1–2**　未取得研究 ID 时也能重放创建。先领取远端调用、预留预算，unknown 状态未经授权不得再次付费外发。对照 `main.py:1116`，用“创建已存但回执丢失”和“命令已外发但进程被杀”分别验收。
- [ ] **E2 / PR4**　候选使用规范化参数与冻结输入标识。替换 attempt ID 与模型措辞时只执行一次。证据为 `loop.py:304` 的 retry 路径。
- [ ] **E3 / PR5**　改变 `engine/export.py:162` 的 PIT 重验归属以及第 222 行的全量 overturn。核对本轮 PIT 失败、无依赖的旧版和当前版各一份包，预期只阻断/标记实际受影响的交接物。
- [ ] **E4 / PR1–2、5**　为 `running_ids` 和列表/时间线创建轻量投影及索引，心跳不序列化历史。测试 100 项研究 × 每项 1,000 个事件，在同机建立 0.9.5 基线，观测列表、状态、翻页 p95 和峰值内存。正常路径一次限量读，检查 EXPLAIN QUERY PLAN 与解码次数；候选门槛为本机状态读取 p95 < 250 ms。该值为拟定预算。
- [ ] **O1 / PR2、5**　为首次模拟、重验、包运行器共享带口径修订的规范市场日历。在满足回看期的长样本中放入三个基准日、资产缺中间日的片段，用 100/110/121 检查三条路径同得 21% 并核对超额和门禁。来源为 `engine/research/simulate.py:29` 与 `engine/main.py:1412`。
- [ ] **O2 / PR2、5**　对 `engine/export.py:_material_sources` 的两类包分别按权利和实际引用白名单投影。并置本机未引用私密笔记、仅元数据许可摘要、允许再分发的材料，在解压后的所有文件匹配私密哨兵和局部绝对路径，均必须零命中。同时校验获准公开的字段确实存在且本机能找回原件。勾选再分发行情不能扩大材料许可。

验证链　创建与重放 → 草稿字段纠错 → 人工确认 → 实际候选 → 材料/行情快照 → 模拟/重验/导出一致。PR1 与 PR2 的存储协议由同一负责人串行合并。PR2 的运行时与 PR3 的草稿工作可并行，涉及 `main.py`、请求 schema 与模型类型时由接口负责人整合。预期六批次的额外审查和合并成本换取故障隔离及可逐批回退。所有性能与留出分数均是验收目标。

## 独立第三方审查的实施增量

以下验收补充相应 PR 的出口，优先于同一条旧路径中较宽的通过条件。

- [ ] **X1 / PR2、4、5，完整定义逐版继承。** 在 `state_machine.py:_open_version`、`specify.py:specify` 及 `DefaultRoundBuilder.build` 接上 effective_spec_snapshot、parent_digest 和确认差异。开新版的完整 spec、卡片、冻结输入和 ZIP 共用父版所有未改的字段。分别让用户批准、拒绝及撤回。固定 V1 −25%、V2 −10%、V3 只延时，模拟 −18% 回撤。重启后 V3 仍按 −10% 失败，拒绝路径不创建版本。
- [ ] **X2 / PR2、4、5、6，独立行情检验。** 给新自适应路径加探索/最终评价两种数据视图，持久化分段策略、训练/验证边界、隔离间隔、候选冻结指纹、已见区间及一次性评价回执。PR2 准备冻结与可见性，PR4 让候选仅读探索数据，PR5 的卡片和两类包携带 evidence_grade、日期及开封状态，PR6 增加真实 GUI/直接 API 对照。选择纯探索或无法证明未见时只交研究记录。资格全过还需要预注册最终评价通过。升级前的旧研究明确展示其原检验范围。新增价格留出测试，与对话的 120 条留出分开计分：两份面板探索段相同、保留段一胜一败，开封前所有候选、问答、工具摘要及搜索侧输入指纹必须相同。私有保留段完整性哈希可不同且不进入搜索上下文；开封后失败者即使旧门禁全绿也只交研究记录。复制、改源、重试、跨版本复用重叠窗口都不能再次获得盲测资格。
- [ ] **X3 / PR2、3，公开资料查询只发授权的词。** 在 `frozen_input.py:ensure_frozen_version_input` 与 `gather.py:PapersAdapter.fetch/SecEdgarAdapter.fetch` 边界分离本地自由论点与公开查询。白名单投影之后再组装 HTTP 请求，失败不可将原始 thesis 拼回 URL。扩展取材用例，用持仓、路径和秘密哨兵尝试关闭模型后开跑，捕获 Crossref、SEC 假端点的 URL/正文及错误日志。正常、失败、恢复三条路径均零哨兵，准许的公开词仍能命中并落证据。

第二轮独立复查把保护边界前移到两个真实入口。以下是 X2/X3 的必测分支。

- [ ] **X2a / PR2、3、4**　先将探索/保留切分写入草稿授权，再把受限 DataPort 传入 `view_for → refresh_symbol_probe` 以及 `_confirm_run → ensure_runnable_universe → _shrink_universe_symbols`。未确定边界前只展示静态标的池。构造两份逐日面板，探索段完全一样，某股票仅在 A 的保留段才有价格。确认卡、缺失/缩量标记、冻结池、门禁、候选序列均须相同；记录提供方收到的最大探测日期，不能超出探索截止日。仅在胜者冻结、窗口原子开封之后才允许最终覆盖判定不同。
- [ ] **X3a / PR2、5**　修正 `specify.py:specify → export.py:build_strategy_pack` 直接序列化 `thesis_locked` 的路径。创建“本机完整定义 → 可交付执行字段”的白名单投影，并在研究记录使用同样的文本边界。分别在原话、本机笔记和路径埋不同哨兵，逐文件扫描两类 ZIP 的 spec、manifest、历史、材料与错误说明，三者均零命中。同时断言规范化规则与允许的证据仍在，真实运行器按指纹复现相同的持仓/收益/验证结果。X1 的跨版继承验证对比执行字段与本机快照，不要求 ZIP 含有原话。

第三轮独立复核确认 X1、X3、X3a 已具可执行验收，X2a 对报价探测的约束成立。末轮另发现成分名单自身可能晚于探索截止日，以下为按该意见补入的最后一项资格门禁。

- [ ] **X2b / PR2、3、5、6**　在 `universe_pool.py:materialize_default_pool` 与 `symbol_pool.py:pool_for_market` 增加带 as-of 上界的选版。冻结成员清单、来源指纹和有据可查的 actual_available_at。对于生成日成分，不能把今天知道的成分当作过去可得。用完全相同的行情和方法，分别给出截止前已知、截止后才形成、实际日期未知的三个名单。前者允许进入一次性最终评价，后两者在草稿卡、直接 API、交接资格及 ZIP 中都只能是探索级，说明原因。即使其它门禁全绿也不得导出策略包。没有可用旧池时如实降级，不必接入新数据商。

## Binding decisions

实际判定依次参照用户委托、产品定位、当前策略族与设置规格、上游源码。开跑、经济变更、降低覆盖和延长预算由用户决定，结论和交接资格由本机验证。在已定范围内把工程复核的修改列入相应 PR。不需要在本次设计中实现新市场或真实交易。

```text
REALITY: premise-table pass 草稿/循环/资格的当前行为和拟建契约在第1节分栏核对。engine/main.py:1012
REALITY: already-done pass 已刷新 origin/main，针对指定入口和关键词的当日 git log 无新增。5866c23
REALITY: surface-check pass 已有 POST /commands、confirm_run 和 run_once 可在本地入口定位；新增协议列为拟建。engine/main.py:1625
REALITY: binding-decisions pass 已读分支决定记录与产品定位，经济逻辑确认优先。docs/requirements/product-positioning.md:74
REALITY: numbers pass 当前预算以源码为准；心跳、语料、响应时间为拟定指标。[estimated] engine/research/honest_stop.py:17
REALITY: deferred-asks pass 已逐项核对六步委托，另行立项的只有本次未要求交付的实施、券商与新增市场，不推迟设计或复核。docs/requirements/product-positioning.md:148
REALITY: pr-count pass 六个批次拆分理由、依赖和合并成本见工程评审记录。[estimated] docs/plans/2026-11-01-dialogue-driven-strategy-research.md:25
REALITY: transaction-semantics finding SQLite 整轮提交与当前分开提交的窗口须经真实断电屏障验收。engine/research/loop.py:545
REALITY: units pass 缺失率按百分数、回撤按有符号比例、时间按有效秒分别核验。engine/research/simulate.py:76
REALITY: perf-table finding [re-measure before gate] 同台机器、相同 SQLite 版本记录 CPU/内存、数据量、EXPLAIN、冷暖各三十次交错测量并报告 p50/p95。engine/research/store.py:711
```

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---:|---|---|
| /plan-eng-review | 用户指定 | 架构、质量、测试、性能 | 3 | 第三轮复核通过 | R1 五项归入 E1–E4，R2 一项导出发布竞态归入 PR5，另明确 PR3 原有授权约定的 3xx 测试边界，均有反例 |
| OUTSIDE COVERAGE | 技能附加挑战 | 从输入和导出反证 | 3 | 同宿主只读 sub-agent 已复核 | O1、O2、发布前翻案和端点改写均有反例。跨厂商覆盖未取得 |
| 独立 sub-agent review | 用户指定 | 三次独立只读反证，审查者未参与撰写 | 3 | 修订已归入六批实施 | R1 → X1–X3，R2 → X2a/X3a，R3 → X2b。末项已按反例补入并核对当前代码入口，未进行第四轮复审 |
| VERDICT | 工程复审 | 已核对导出授权时点、3xx 及 E1–E4/O1/O2 | 3 | CLEAR（方案） | 末轮新增阻断 0，计划待实施 |

NO UNRESOLVED DECISIONS
