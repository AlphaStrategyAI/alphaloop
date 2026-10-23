# alphaloop

在你自己的电脑上，把一项日频股票的均值回归研究跑完，留下试验次数、门禁结果，以及一份可以拿走的记录。alphaloop 不下单，也不替你判断该不该用这个策略。

这是给已经自己做过回测的人用的。你可能用过 Python、一张表，或一个云端平台，手里有一条好看的曲线，但说不清试了多少次，也说不清信号有没有用到当时还没有的价格。0.2.0 能接住的就是这一步：只跑截面均值回归，并把没过的检查写下来。它接不住「把任意想法自动做成策略」，也不连接券商。

没有安装包，没有托管，也没有付费方案。下一步是克隆仓库，让引擎在本机启动，再用桌面应用开一项研究。

## 一个具体的任务

想看的是：近期跌得多的股票，会不会向近期均值靠拢。

常见做法是在笔记本里用收盘价算一个分数，换几组回看天数，把最好看的净值留下来。容易出问题的是三件事。信号和成交用了同一根 K 线的收盘价。试过的次数不在任何文件里。结果留在别人的网站上，带走的是图，不是当时的验证定义。

在 alphaloop 里，对话用来锁定五项设定：赚钱原理、标的、有效研究时间、第一轮验证方法、最低数据覆盖。原理若写成动量、趋势或突破，确认卡和完成页会说明暂不支持；引擎仍只跑截面均值回归，不会改跑别的族。确认开跑之后，信号先算出来，成交用的是上一根 bar 的信号。本版本默认最多自动迭代 5 轮，自动改动只把回看天数加 5。换经济逻辑会停下来等你确认。

做完之后，下面五项同时成立才能导出策略包：研究已完成、当前冻结的验证方法全部通过、没有待确认、当前轮的重新验证通过、时点一致性已执行且通过。缺任何一项，只能导出研究记录，并写明缺的是哪一项。包里的回测是历史假设，不是实盘业绩，也不是对未来的承诺。

没有测量过这能省下多少时间。能看见的变化是：试验次数和没过的门禁留在记录里。

## 现在能做，以及做不到的

**能做**

- 在桌面应用里把五项设定谈完，确认后做历史研究。默认评审器是确定性的，不调用大模型。只有把 `ALPHALOOP_REVIEWER` 设为 `subagent`，并同时提供 `ALPHALOOP_LLM_BASE_URL`、`ALPHALOOP_LLM_API_KEY`、`ALPHALOOP_LLM_MODEL`，才会请求外部模型。缺任何一项就失败关闭，不会把超时当成通过。
- 不写代码时，新研究使用仓库里的生成日名单。美股是 `us_equity_large_cap_v2`：2026-10-16 的标普 500 成分，503 只。A 股是 `cn_equity_large_cap_v2`：2026-10-19 的沪深 300 成份，300 只。已经引用 v1 的研究仍用各自 40 只的旧名单，成员不改。你写出代码可以覆盖默认池。
- 这些名单是生成日的成分，不是历史时点成分。用它们回看更早的日期含有幸存者偏差。记录里的标记是 `survivorship_bias_untested`。这不会因此判时点一致性失败。
- 导出研究记录。五项资格都通过时，才导出策略包。下游要自己实现执行。alphaloop 不连接券商。

**做不到，或还不能当成已经交付**

- 不下单，不接券商，不跑模拟盘。命令行只有启动和查看状态。
- 低波、股债再平衡、基本面因子、全天候在代码里有标识和中文名。开跑时返回「这一族还不能开跑。」
- 规格里的本地 CSV 导入、商业数据商连接器，以及设置里的数据源页、大模型页，界面上仍是稍后才会做的页面。现在能用的设置是界面语言：跟随系统、中文或英文。
- 规格要求把 Yahoo 和 AkShare 标成「未经许可」，并要你主动确认之后才能开跑。0.2.0 的代码按标的自动选用 `yahoo_daily` 或 `akshare_sina_daily`，界面写的是「雅虎日线」和「AkShare 日线（新浪优先）」。术语表里有「未经许可」这个词，确认流程里没有那一次勾选。
- 规格把导出资格写成还包含 `coverage_satisfied`。`strategy_pack_eligibility` 里没有这个键。覆盖不够会在运行过程中停下，但那不是导出函数里的一项检查。
- 时点一致性（pit-v2）只检查被当作证据的资料，其发布日是否不晚于回测截止日。没有发布日的资料不当作证据。它不检查标的池是不是时点成分，不检查复权，也不检查财务修订。
- 没有可引用的用户数量、客户或业绩。2026-10-23 查看时，这个公开仓库没有 Release，讨论区关闭，开放 Issue 为空。

## 最快路径

需要 Python 3.12 和 Git。桌面还需要 Node.js 22、Rust，以及系统 WebView。类型检查工作流使用 Node 22。macOS 打包工作流写的是 Node 20，这里没有在 Node 20 上重跑桌面测试。Linux 上，CI 安装 `libwebkit2gtk-4.1-dev` 及其同组依赖。打引擎侧车还需要 `python3.12-venv`：2026-10-23 在没有这个包的机器上，`scripts/build_sidecar.sh` 退出码为 1，原因是虚拟环境里没有 ensurepip。2026-10-23 请求 `https://pypi.org/pypi/alphaloop/json` 返回 404，PyPI 上没有这个包。

```bash
git clone https://github.com/AlphaStrategyAI/alphaloop.git
cd alphaloop
python3 -m pip install -e ".[dev]"
python3 -m apps.cli.main start
python3 -m apps.cli.main status
```

`start` 之后，`status` 打印一行 JSON。2026-10-23 在 Linux 上的一次输出如下，pid 每次不同：

```json
{"awaiting_confirm": false, "has_running_research": false, "owner": "cli", "pid": 11699, "running": true}
```

这只说明引擎进程在。命令行不能新建研究、不能确认、不能导出。没有 `stop` 子命令，结束时结束 `status` 里的 pid。

研究在桌面应用里做。桌面要先打包引擎侧车。这一步会自建 `.venv-sidecar`，并用 PyInstaller 打包，时间取决于机器和网络：

```bash
bash scripts/build_sidecar.sh
python3 scripts/stage_sidecar.py --target linux --source dist/alphaloop-engine --tauri-root apps/desktop/src-tauri
bash scripts/smoke_sidecar.sh
cd apps/desktop
npm ci
npm run tauri dev
```

macOS 把 `--target linux` 换成 `macos`，Windows 换成 `windows`。打开之后，在「研究」里新建一项。对话依次问那五项。要走通当前引擎，原理写成均值回归，资产选美股股票或 A 股股票。五项锁定后出现确认开跑卡。开跑会按标的拉取日线，需要网络。计划窗口是从当天的 UTC 日期倒推 12×365 天。拉不到数据或覆盖跌破你认下的底线时，研究停下来说明原因，不会改用一份仓库里不存在的行情文件。

完成后看完成页。有门禁没过时，能导出的是研究记录，策略包不可用，页面写明缺哪一项检查。五项都过，才导出策略包。

不访问行情的检查：

```bash
python3 -m pytest -q -m "not network"
cd apps/desktop && npm test
```

`pytest` 里有一条 Rust 契约测试。CI 会先放一个空的引擎占位再跑。本机既没有这个占位、也没有 GTK 开发包时，这一条会失败，其余离线测试不依赖它。

Linux 上，数据默认在 `~/.local/share/ai.alphastrategy.alphaloop`，里面有 `research.db`、`materials/`、`exports/`、`snapshots/` 和 `engine.log`。运行时的锁和 `owner.json` 在 `platformdirs` 的 `user_runtime_path("alphaloop")`。没有 `XDG_RUNTIME_DIR` 时会落到临时目录下的 `runtime-<uid>/alphaloop`。可以用 `ALPHALOOP_DATA_ROOT` 和 `ALPHALOOP_RUNTIME_ROOT` 改这两个位置。

## 凭什么相信，以及不要相信什么

可以核对的是仓库、许可证和一次本机运行。没有第三方审计，没有业绩案例。

MIT 许可证的版权行是 `Copyright (c) 2026 OpenStrategy Team`。GitHub 组织名是 AlphaStrategyAI。MIT 允许使用、修改、再分发这份代码，包括商用，前提是保留版权和许可声明。它不保证软件正确，也不授予任何行情、财报或指数成分数据的权利。

美股日线经过 [yfinance](https://github.com/ranaroussi/yfinance)。该项目的 README 写明它不隶属 Yahoo，供研究与教育使用，并要求读者自己看 Yahoo 的使用条款。A 股日线经过 [AkShare](https://github.com/akfamily/akshare)，优先新浪，失败再试东财。AkShare 的 README 写明数据仅供学术研究，不构成投资建议，部分接口可能被移除。两个来源都可能失败或变更。产品规格要把它们标成未经许可；上面已经写了，0.2.0 的界面还没做到。

公开论文走 Crossref。发行人材料走 SEC EDGAR，请求使用固定的 User-Agent：`alphaloop/0.2 research@example.invalid`。这不是你的联系邮箱。本机 Markdown 放在数据目录的 `materials/`。

股票基准是价格指数：美股 `SPX`（标普 500），A 股 `000300.SH`（沪深 300）。策略收益来自价格序列的涨跌。上游若给的是复权价，它和价格指数不是同一口径。

新研究在确认开跑时把成本模型设为 `schedule_v1`。回测净收益按换手扣除：美股个股单边 5bp，美股基金 1bp，A 股个股 20bp，A 股基金 5bp。可持有的标的不少于 20 只、且不是基金、也不是多空时，单票权重上限是 5%。换手成本这道门禁是另一层计算：美股用 10bp，A 股用 20bp，从年化超额里减去「年化换手 × bp / 10000」。净收益已经扣过 `schedule_v1` 时，这道门禁仍会再减一次。术语表里「回测收益序列本身不含逐日费用」说的是旧的 `legacy_zero` 路径；旧的 A 股记录在用冻结快照重新验证时仍走那条路径。A 股确认卡会写：「未模拟 T+1 与涨跌停，实际成交可能更差。」

同一数据窗口上的累计轮次写入 SQLite，并写入导出的 `history/rounds.json`。累计变大不会放宽门槛。默认预算用尽后，每次继续迭代都要你确认。累计达到 20 轮时还要再确认一次。这三个数（5、5、20）是 `engine/research/honest_stop.py` 的默认值，分别可用 `ALPHALOOP_MAX_TRIALS`、`ALPHALOOP_TRIAL_BUDGET_INCREMENT`、`ALPHALOOP_HIGH_SUSPICION_ROUNDS` 修改。

异常好的结果先展开数据出处、覆盖是否缩过、试了多少次、用的哪一版验证定义。这是检查清单，不是庆祝。

## 和现有做法比

下面是 2026-10-23 能核对到的文档，不是功能勾选表。没打开的页面不转写成数字。

| 做法 | 它实际提供的 | 它不替你做的 |
| --- | --- | --- |
| 自己的 Python 或表格 | 完全按你的代码跑。前视要你自己处理。 | 试验次数通常不进文件，也没有统一的导出资格。 |
| [vectorbt](https://github.com/polakowo/vectorbt) | 在本机扫描大量参数。README 把社区版和付费的 VectorBT PRO 分开。许可证是 Apache 2.0 加 Commons Clause。 | 扫描本身不记录你丢弃了多少组。 |
| [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) 3.2.0（2026-10-18） | 事件驱动回测，Apache 2.0。维护者写明只做缺陷和兼容性修复，新功能在 ML4T Backtest。3.2 说明不支持 pandas 3。 | 不是一份带导出门禁的研究记录。 |
| [backtrader](https://github.com/mementum/backtrader) 1.9.78.123 | 事件驱动框架，GPLv3+。PyPI 上这一版发布于 2023-04-19。库内带券商接入。 | 上游发布停在该版本。它是交易框架，不是试验账本。 |
| [聚宽](https://www.joinquant.com/) | 在浏览器里研究、回测、模拟。官方 API 文档写明：财务数据按报告期查询会有未来函数；`use_real_price` 默认是 False。 | 研究在对方服务器上。收费页本次返回 403，这里不写会员价格。 |
| [米筐量化平台](https://www.ricequant.com/doc/quant/) | 浏览器里的研究，数据来自 RQData。文档中的基础版没有模拟交易名额，企业版有。官方 PDF 写试用账户一个月。 | 正式数据价格要联系销售。这里不采用论坛里的报价。 |
| [LEAN](https://github.com/QuantConnect/Lean) | 引擎 Apache 2.0，可以在本机跑。QuantConnect 云是另一套带实盘的订阅。 | 本次没有从标价页核对到可以引用的金额。它的目标包含下单。 |
| [Qlib](https://github.com/microsoft/qlib) | 微软的 MIT 平台，覆盖数据、模型训练和回测。`pip install pyqlib` 之后还要自己准备数据。 | 它是模型流水线，不回答「这一次研究试了几轮、哪道门没过」。 |

这些做法仍然更合适的情况很具体：你要做分钟或 tick，要接券商，要低波、股债、基本面或全天候，或者要别人维护好的财务数据。0.2.0 都不提供。若目标是扫很多组参数并留下夏普最高的一组，vectorbt 直接做这件事；alphaloop 不提供这种扫描。

## 许可、费用与参与

没有收费层，没有付费支持，也没有托管实例。可以做的是：在本机安装并跑一项研究；对不对的行为开 [Issue](https://github.com/AlphaStrategyAI/alphaloop/issues)；或者提 Pull Request。

仓库里没有 `CONTRIBUTING`。讨论区关闭。标签里有 `good first issue`，2026-10-23 没有使用这个标签的开放 Issue。改代码之前先读 [V1 交付收口](./docs/requirements/v1-cut-line.md)。已经交出去的均值回归路径，不因为后面的规格而改写。五个策略族的规格在 [策略族 v1](./docs/requirements/strategy-families-v1.md)，那是规格，不是当前能开跑的清单。

没有公开的招聘。这份说明不是在招人。

英文对照是 [README.en.md](./README.en.md)，事实与本文件相同。英文界面里，策略族的显示名目前是标识本身，例如 `mean_reversion`。

## 已知限制

- 自动迭代的默认预算是 5 轮。设计稿若画了更多轮，以代码为准。
- 数据窗口键包含确认日。同一个想法隔天再开，是一个新窗口。
- 自动迭代不搜索入场阈值，也不换策略族。
- 「分段稳健性检验」是把一条已经算好的收益按时间切开比较，不是重新估计参数的 walk-forward。「集中度」看的是持仓权重，不是市场成交拥挤。对话里仍可输入旧称「走样检验」「拥挤度」。
- 回测里的 5bp 和门禁里的 10bp 不是同一个成本。见上面的成本两层。
- `pyproject.toml` 没有钉死依赖版本。2026-10-23 这次安装得到 pandas 3.1.0、yfinance 1.7.0、akshare 1.19.3。另一天安装，解析结果可能不同。
- 同日 `npm audit` 报告开发依赖中有 2 个中等、2 个高危问题；加上 `--omit=dev` 之后是 0。这不是安全审计结论。

## 文档

- [产品定位](./docs/requirements/product-positioning.md)：产品想成为什么。它比 0.2.0 宽，不能当成已实现功能。
- [V1 交付收口](./docs/requirements/v1-cut-line.md)：这一版承诺交到哪里。
- [术语表](./docs/GLOSSARY.md)
- [设置功能规格](./docs/requirements/settings-config-v1.md)：规格，不是已全部实现的界面。
- [路径约定](./docs/requirements/paths-contract.md)

## License

MIT。全文见 [`LICENSE`](./LICENSE)。
