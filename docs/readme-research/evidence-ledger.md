# 证据台账

访问日期一律为 2026-10-23，除非某行另写。状态只用：已核验产品事实 / 可追溯用户反馈 / 有依据推断 / 待验证假设 / 未来规划。

可信度：高 = 打开了原始页面或读了当前仓库文件；中 = 检索摘要与原文要点一致，但页面本身返回 403 或只看到摘要；低 = 单点、过时或不能复核。

| 编号 | 主张 | 来源 | 版本或发布时间 | 发现 | 状态 | 可信度与局限 |
| --- | --- | --- | --- | --- | --- | --- |
| E01 | 包版本 0.2.0，Python ≥3.12，未钉死依赖 | `pyproject.toml`、`apps/desktop/package.json` | 仓库 main，2026-10-23 | 项目名 alphaloop，脚本 `alphaloop` 与 `alphaloop-engine` | 已核验产品事实 | 高。另一天安装会解析到不同的传递依赖 |
| E02 | 许可证为 MIT；版权持有人是 AlphaStrategyAI | `LICENSE` | 2026 年；2026-10-23 由维护者把原 `OpenStrategy Team` 改为 AlphaStrategyAI，许可类型与年份未改 | 允许使用、修改、再分发、出售代码副本，保留声明；无担保 | 已核验产品事实 | 高。MIT 不授予行情数据权利。改名是维护者决定，不是另一次法律意见 |
| E03 | 无 Release、讨论区关闭、星标 0、分叉 0、开放 Issue 为空；仅一条已关闭 Issue #111 | `gh repo view`、`gh release list`、`gh issue list`、Discussions API | 查看于 2026-10-23 | API 对 discussions 返回 410。贡献者列表以 cursoragent 为主 | 已核验产品事实 | 高。星标不是质量指标，只说明没有可引用的公开采用 |
| E04 | 引擎只跑 legacy 逐日 z 分数均值回归 | `engine/research/families.py`、`engine/research/loop.py`、`engine/research/a1_copy.py` | 当前 main | 其他族 id 存在；开跑错误文案「这一族还不能开跑。」动量提示「暂不支持」 | 已核验产品事实 | 高 |
| E05 | 新池 503 与 300；旧池各 40 | `engine/research/symbol_pools/*.json`，当场 `len(symbols)` | 生成日 2026-10-16 / 2026-10-19 / v1 为 10-17 与 10-18 | v2 选择说明写明是生成日名单，不是时点成分，含幸存者偏差 | 已核验产品事实 | 高。名单来源是维基百科旧修订与中证指数当日文件，文件本身声明 URL 会被覆盖 |
| E06 | 美股走 yfinance，A 股走 AkShare（新浪优先） | `engine/research/gather.py`、`engine/research/data_port.py` | 当前 main；本次安装 yfinance 1.7.0、akshare 1.19.3 | 未知源 id 不会静默改走 Yahoo | 已核验产品事实 | 高。没有做实盘行情拉取 |
| E07 | 规格中的「未经许可」勾选未进入确认流程 | `docs/requirements/settings-config-v1.md` 对 `engine/` 与 `apps/desktop/src` 的检索 | 规格变更记录 2026-10-19 | 界面展示名是「雅虎日线」「AkShare 日线（新浪优先）」。`未经许可` 只出现在术语 JSON 和规格 | 已核验产品事实 | 高。这是冲突，不是实现 |
| E08 | 策略包资格是函数里的五项，不含 `coverage_satisfied` | `engine/export.py` `strategy_pack_eligibility`；全库测试检索 | 当前 main | 五项：completed、all_current_methods_passed、no_pending_confirm、all_reverifies_passed、pit_executed_and_passed | 已核验产品事实 | 高。规格仍写 coverage_satisfied |
| E09 | 新研究的净收益已扣 schedule_v1，门禁再扣 10/20bp | `engine/portfolio.py`、`engine/strategy.py`、`engine/research/simulate.py`、`engine/verifiers.py` `_cost`、`engine/main.py` 确认开跑 | 当前 main | 美股个股 5bp、美股基金 1bp、A 股个股 20bp、A 股基金 5bp。单票 5% 仅在可持有 ≥20 且非基金、非多空。门禁美 10bp、A 20bp | 已核验产品事实 | 高。术语表仍写收益序列不含逐日费用，该句只还符合 legacy_zero |
| E10 | 时点检查范围有限 | `engine/verifiers.py` `PIT_SCOPE` | pit-v2 | 文案：只查资料发布日 ≤ 回测截止日，不覆盖标的池/复权/财务修订。无日期资料不当证据 | 已核验产品事实 | 高 |
| E11 | 默认预算 5，追加 5，高怀疑阈值 20 | `engine/research/honest_stop.py` | 当前 main | 累计轮次不放宽门槛。自动变更是 lookback + 5 | 已核验产品事实 | 高 |
| E12 | 命令行能启动引擎并返回 JSON | 本次在 Linux 上执行 `python3 -m apps.cli.main start/status` | 2026-10-23 | `{"awaiting_confirm": false, "has_running_research": false, "owner": "cli", "pid": 11699, "running": true}`。无 stop 子命令。结束后再 status 为 running false | 已核验产品事实 | 高。pid 不可复用。数据根被设到 /tmp，不是默认路径的另一次证明 |
| E13 | 离线 pytest | `python3 -m pytest -q -m "not network"` | 2026-10-23，pandas 3.1.0 | 484 passed，2 deselected，1 failed。失败项是 Rust 契约测试：先缺 gdk-3.0，装上 GTK 开发包后改为缺少 CI 使用的空引擎占位。按 CI 放上占位后该测试 1 passed | 已核验产品事实 | 高。没有跑带网络的验收测试 |
| E14 | 桌面测试 | `apps/desktop` 下 `npm ci && npm test` | Node v22.14.0，vitest 4.1.11 | 44 files，169 tests passed，随后 `tsc --noEmit` 通过 | 已核验产品事实 | 高。不是图形界面里点过一遍 |
| E15 | PyPI 无此包 | `https://pypi.org/pypi/alphaloop/json` | 2026-10-23 | HTTP 404 | 已核验产品事实 | 高。只查了这个包名 |
| E16 | 聚宽官方 API 文档警告财务数据的未来函数，且真实价格模式默认关闭 | 抓取的 JoinQuant API PDF 文本 | 抓取于 2026-10-23，文档无单页版本号 | `statDate` 相关段落写「会有未来函数」；`use_real_price` 默认 False，文档建议设为 True | 可追溯的官方产品文档，不是 alphaloop 用户反馈 | 高（对该 PDF 文本）。没有证明聚宽用户因此流失 |
| E17 | 第三方教程把聚宽的 `avoid_future_data` 写成需要手动开启 | https://easyquant.ai/e/joinquant/look-ahead-bias-prevention | 页面标注 2025-11-26 | 教程给出 `set_option("avoid_future_data", True)`。同一选项没有在已抓取的官方 PDF 文本里检索到 | 有依据推断：至少有人认为需要额外开关。不能上升为官方 API 事实 | 中。站点不是聚宽官网 |
| E18 | 英文社区里，用户把前视和「把样本外调到好看」当成自写回测的失败方式 | https://www.reddit.com/r/algotrading/comments/gyvist/ 与 https://www.reddit.com/r/algotrading/comments/qtyuxb/ 与 https://www.reddit.com/r/algotrading/comments/1bp4d8g/ | 帖子时间从 2017 到 2024-03 | 有人写 pandas 向量化容易意外前视；有人描述反复修改直到样本外好看，于是样本外不再是样本外 | 可追溯用户反馈 | 中。r/algotrading 的样本偏向会写代码的人，不是 A 股散户整体 |
| E19 | 中文问答把未来函数、过拟合、幸存者偏差并列成回测陷阱 | https://www.zhihu.com/question/1994727269365724898 的检索摘要；https://www.zhihu.com/en/answer/30092403 | 知乎页面未能全文打开，使用检索摘要 | 摘要把未来函数定义为使用了交易时点尚不可得的信息，并建议信号与成交分开两根 bar | 可追溯用户反馈（摘要级） | 中。未读到完整回答与作者身份，不引用具体人数 |
| E20 | 多重检验下只报告最好的回测会抬高预期 | Bailey & López de Prado, *The Deflated Sharpe Ratio*, Journal of Portfolio Management 40(5), 2014；SSRN abstract_id=2460551；作者 PDF https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf | 2014；SSRN 页显示 last revised 2014-11-11 | 摘要：不控制试验次数会导致过于乐观。DSR 同时校正选择偏差与非正态 | 可追溯的论文主张 | 高（对摘要）。alphaloop 没有实现 DSR。论文不证明有人会为本仓库付费 |
| E21 | vectorbt 社区版鼓励大规模参数扫描，并与 PRO 分开卖；许可证含 Commons Clause | https://raw.githubusercontent.com/polakowo/vectorbt/master/README.md | 抓取于 2026-10-23 的 master README | README 给出扫描示例和当时的数值输出；声明教育用途；Commons Clause 禁止把主要就是该软件的产品出售 | 已核验的上游文档 | 高（对该 README 快照）。示例里的收益数字会随行情变，不引用到 alphaloop 的 README |
| E22 | zipline-reloaded 处于维护状态 | https://github.com/stefan-jansen/zipline-reloaded 与 3.2.0 release 说明 | 3.2.0 发布于 2026-10-18 | Apache 2.0。新功能指向 ML4T Backtest。3.2 说明不支持 pandas 3 | 已核验的上游文档 | 高（对检索到的 release 说明）。未克隆该仓库复跑 |
| E23 | backtrader 上游发布停在 2023-04 | https://pypi.org/project/backtrader/ | 1.9.78.123，上传时间 2023-04-19 | GPLv3+。PyPI 版本历史最后一项是该版。GitHub releases 页为空，提交历史在检索结果中停在同一天 | 已核验的上游发布记录 | 高（对 PyPI 日期）。社区 fork 的后续发布不改变上游这个日期 |
| E24 | 米筐文档区分基础版与企业版，基础版模拟交易名额为 0 | https://www.ricequant.com/doc/quant/ 与研究文档、RQData PDF | 抓取于 2026-10-23 | 研究在浏览器 Notebook。PDF 写试用账户一个月、可用基础数据。正式账户写「付费开通」，无公开价目表 | 已核验的官方文档 | 高（对这些页）。论坛里「4000 元」未当价格使用 |
| E25 | 聚宽 2024-12-30 社区通知写了会员调价 | 检索摘要指向 https://www.joinquant.com/community/post/detailMobile?postId=51515 | 通知日期写 2024-12-30；直接抓取返回 403 | 摘要中的数字：VIP 月 128 / 年 999，SVIP 月 378 / 年 2799，自 2025-01-01 | 待验证假设（金额） | 低到中。README 因此不写这些金额。通知正文未能打开 |
| E26 | yfinance 自称不隶属 Yahoo，并指向 Yahoo 条款；个人使用 | https://raw.githubusercontent.com/ranaroussi/yfinance/main/README.md | 抓取于 2026-10-23 | 同时声明 Apache 许可证属于该库本身，数据权利另说 | 已核验的上游 README | 高。不是律师对 Yahoo 条款的结论。另抓到的 Yahoo API 条款页是带 API Key 的旧式条款，不能直接当成「yfinance 抓取被该页逐条禁止」 |
| E27 | AkShare 声明学术研究用途 | https://raw.githubusercontent.com/akfamily/akshare/main/README.md | 抓取于 2026-10-23；声明 Python 3.11+ | 致谢里写明新浪财经与东方财富。不构成投资建议 | 已核验的上游 README | 高。未逐个核对 alphaloop 调用的函数是否仍在 |
| E28 | 信号延迟一根 bar | `engine/strategy.py` `daily_book` | 当前 main | `generate_signals(...).shift(1)`。另用合成价格跑过一次：40 行价格，权重首行为全 0 | 已核验产品事实 | 高。合成净值不是策略业绩，不写入 README |
| E29 | Qlib 是 MIT 的模型研究平台，数据另备 | https://github.com/microsoft/qlib/ | 检索于 2026-10-23 | README 给出 `pip install pyqlib` 和 `qrun` 工作流。星标数字会变，不写入 README | 已核验的上游 README 快照 | 高（对抓取文本）。其「全链路」表述是项目自我描述 |
| E30 | LEAN 引擎 Apache 2.0，云是另一套订阅 | https://github.com/QuantConnect/Lean 与 https://www.lean.io/pricing 的检索结果 | 检索于 2026-10-23 | 引擎页写可在本地运行、Apache 2.0。标价页的检索结果列出方案名称，没有可引用的货币数字 | 已核验的上游说明（引擎许可）；价格未核验 | 中。未逐行读完标价页的动态表格 |
| E31 | 定位文档比实现宽 | `docs/requirements/product-positioning.md` | 文档无单行版本，仓库内文件 | 「随时丢进大致方向、长时间自主研究」 | 未来规划（相对 0.2.0） | 高。它是内部定位，不是已交付能力 |
| E32 | 默认路径 | `docs/requirements/paths-contract.md`；本次 `platformdirs` 打印 | 2026-10-23 | Linux 数据根 `~/.local/share/ai.alphastrategy.alphaloop`。无 XDG_RUNTIME_DIR 时运行时根落到 `/tmp/runtime-<uid>/alphaloop` | 已核验产品事实 | 高。macOS / Windows 的具体路径没有在本机打印 |
| E33 | 桌面生产依赖的 npm audit 为 0 | `npm audit --omit=dev --json` | 2026-10-23，锁文件当时状态 | 含 dev 时 2 moderate、2 high。未打开每条公告 | 已核验的命令输出 | 中。audit 数据库会变，且不是渗透测试 |
| E34 | 默认不调用大模型 | `engine/main.py` 评审器分支 | 当前 main | `ALPHALOOP_REVIEWER` 默认 deterministic。subagent 缺配置则 FailClosedLLM | 已核验产品事实 | 高 |
| E35 | 设置的数据源与大模型页未做 | `apps/desktop/src/settings/SettingsPage.tsx`、`apps/desktop/src/i18n/catalog.ts` | 当前 main | 非 general 页显示 later 文案。通用页可以切换语言 | 已核验产品事实 | 高 |
| E36 | 没有 alphaloop 自己的用户原话 | Issue 列表 E03 | 2026-10-23 | 不能把 E16–E19 说成「alphaloop 用户这样说」 | 已核验产品事实 | 高 |
| E37 | 成功 README 的可借鉴处与不可借鉴处 | Qlib、vectorbt、zipline-reloaded 的 README（E21、E22、E29） | 2026-10-23 | Qlib：首屏说清对象、一条安装、一条工作流、许可证；信任很大程度来自微软与论文，alphaloop 没有对等品牌。vectorbt：命令旁有输出；但输出依赖实时行情，且页面在卖 PRO。zipline：首屏写明维护范围和新项目该去哪。三者都不证明 README 本身带来付费 | 有依据推断 | 中。只读了 README，没有读它们的转化数据 |

| E38 | 导出里没有 `survivorship_bias_untested` 这个键 | 全库检索 `survivorship`；`engine/research/pool_display.py`；`docs/requirements/default-universe-v1.md` | 2026-10-23 | 池 JSON 有中文 survivorship 句子。界面注记是「非时点成分」。规格要求记录存该 id。引擎与桌面源码不写这个 id | 已核验产品事实 | 高。第一稿 README 把规格 id 写成了已落库字段，已改 |
| E39 | 个股请求的是复权价，基准是价格指数 | `engine/research/gather.py` | 当前 main | yfinance `auto_adjust=True`；AkShare `adjust="qfq"`；`SPX` 换成 `^GSPC`；`000300.SH` 走指数日线 | 已核验产品事实 | 高 |
| E40 | `docs/GLOSSARY.md` 不含「未经许可」 | 该文件与 `apps/desktop/src/i18n/locked-glossary.json` | 2026-10-23 | 词在 i18n 术语 JSON 和 `docs/requirements/i18n-glossary-v1.md` | 已核验产品事实 | 高 |
| E41 | 聚宽会员收费页抓取返回 403 | https://www.joinquant.com/view/vip/charge | 抓取于 2026-10-23 | WebFetch 状态码 403。首页 https://www.joinquant.com/ 同日 HEAD 为 200。E25 的 403 是另一条社区通知，金额仍不引用 | 已核验产品事实（对该次请求） | 高。页面可能对其他网络开放 |
| E42 | 侧车能完成握手 | 本次 `scripts/build_sidecar.sh` 与 `scripts/smoke_sidecar.sh` | 2026-10-23，PyInstaller 6.22.3 | 缺 venv 包时构建失败；装上之后构建退出码 0，smoke 打印 `engine handshake ok: ready` | 已核验产品事实 | 高。不是图形界面里的一次研究 |

| E43 | 2026-10-23 桌面里跑完一项 SPY 均值回归，门禁未全过，导出了研究记录 | 本次 `npm run tauri dev` 截图 `docs/readme-assets/`；SQLite `/tmp/alphaloop-readme-demo/research.db` 研究 `56026da0-bedd-4db8-b2d6-e4a36f617cff`；导出 zip 的 `manifest.json` 与 `why_not_live.json` | 点 Run 15:06:47Z，完成记录 15:06:54Z | 英文界面。确认卡：1 只 SPY、雅虎日线、2014-10-26 至 2026-10-23、成本 5 bp。5 轮，回看 40，入场 z 1.0，只做多。未过：市场计分卡、样本外稳定、换手成本。通过：分段稳健性、集中度、时点一致性。策略包锁定。没有未经许可勾选。数据根是环境变量覆盖，不是默认路径 | 已核验产品事实 | 高。一次维护者测试，不是业绩，也不是用户许可。截图未裁掉失败门禁 |

不存在的证据，明确空着：用户访谈、付费意愿、节省时间的测量、业绩、认证、市场规模、本仓库的客服或销售对话。默认数据根上的桌面点击还没有做。
