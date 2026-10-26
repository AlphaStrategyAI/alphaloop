[English](README.md) | 简体中文

# alphaloop

**一台电脑上的日频股票研究工坊。**

你把一项研究说清楚。alphaloop 在你自己的机器上把轮次跑完，留下一份写明试了多少次、哪道门没过的文件。它不下单，也不替你决定该不该用这个策略。

**0.2.0 能开跑的是均值回归。** 这是今天可以开始的那一种策略。

![研究列表](docs/readme-assets/01-research-list.png)

![一项研究怎么往下走](docs/readme-assets/study-loop.gif)

## 安装

需要 Python 3.12 和 Git。桌面还需要 Node.js 22、Rust、系统 WebView，以及打包引擎时的 `python3.12-venv`。没有安装包。PyPI 上没有 `alphaloop` 这个名字。

```bash
git clone https://github.com/AlphaStrategyAI/alphaloop.git
cd alphaloop
python3 -m pip install -e ".[dev]"
bash scripts/build_sidecar.sh
python3 scripts/stage_sidecar.py --target linux --source dist/alphaloop-engine --tauri-root apps/desktop/src-tauri
cd apps/desktop
npm ci
npm run tauri dev
```

macOS 把 `--target` 换成 `macos`，Windows 换成 `windows`。Linux 的 CI 会安装 `libwebkit2gtk-4.1-dev` 和同组依赖。类型检查用 Node 22。macOS 打包工作流用 Node 20。

如果 `python3 -m apps.cli.main start` 已经在跑，先结束那个进程再开桌面。两边共用一把运行时锁。命令行只能启动引擎、打印状态。研究本身在桌面里做。

## 为什么值得打开

你已经有笔记本、表格，或一个云端回测。还是有三件事经常丢。

| 常见情况 | 0.2.0 会写下的 |
| --- | --- |
| 信号和成交用了同一根收盘价。 | 信号先算出，权重用上一根 bar。 |
| 留下最好看的曲线，试过几次却不在文件里。 | 轮次写进记录并导出。次数变多不会放宽门禁。 |
| 结果留在别人的网站上。 | 研究和导出都在你的磁盘上。没有托管账号。 |

alphaloop 不替代券商、分钟线引擎，也不替代参数扫描。它替代的是这一步：你正要把一条没有试验账本的日频股票曲线当真。

## 0.2.0 能做的事

**说清五项，然后可以离开。** 赚钱原理、标的、时间上限、第一轮验证方法、覆盖底线。暂停和等待确认的时间不计入上限。一条消息可以填上不止一项。

**小步自己继续。** 默认预算 5 轮。每一轮自动把回看天数加 5，这个加数写死在代码里。第一轮从 20 天、入场 z 值 1.0、只做多开始。经济逻辑变了，就停下来等你。

**开跑前能看见数据。** 确认卡写出标的、日期窗口、来源和成本。美股个股单边 5 bp，美股基金 1 bp，A 股个股 20 bp，A 股基金 5 bp。单票 5% 上限只在至少能持有 20 只、且不是基金、也不是多空时生效。

**门禁决定你拿走哪一种文件。** 策略包要同时满足：研究已完成、当前冻结的验证方法通过、没有待确认、除时点以外已记录的重新验证通过、时点一致性已执行且通过。缺任何一项，仍然可以导出研究记录。包里的回测是历史假设，不是实盘业绩，也不是对未来的承诺。

**时点检查只做一件事。** 被引用的资料，发布日不能晚于回测截止日。没有发布日的资料会被丢掉，并不因此判失败。一项研究可以在没有外部资料时通过。它不检查指数成分、复权或财务修订。幸存者偏差不会让它失败。

**美股和 A 股名单在仓库里。** 不输入代码时，新研究用 2026-10-16 的标普 500 成分（503 只）或 2026-10-19 的沪深 300 成份（300 只）。这是名单日的成分，不是当时的成分。更早的历史带有幸存者偏差，界面会写明。输入代码会换掉名单。已经引用旧名单的研究仍用各自 40 只。

## 我们跑过的一次

2026-10-23，维护者在 Linux 上打开桌面，跑了一项研究。窗口是英文。内容是：美股、SPY、均值回归、12 小时、四项验证方法，覆盖底线为至少 1 只、1 年、缺失不超过 20%。确认卡显示 1 只 SPY、Yahoo 日线、2014-10-26 至 2026-10-23、成本 5 bp。因为这句话把它分成了股票而不是基金，所以用的是 5 bp，不是基金的 1 bp。

15:06:47 UTC 点了开跑。库存完成时间是 15:06:54 UTC。屏幕上的有效研究时间是 0.00 小时，因为这几秒不到 0.01 小时；屏幕上是 5/5 轮。市场计分卡、样本外稳定、换手成本没过。分段稳健性检验和集中度过了。时点一致性通过。「每一项已选验证方法都通过」旁边的空心圆是未通过。绿色的重新验证芯片亮着，但这次没有做过重新验证；列表为空时这项算通过。策略包保持锁定。导出的是研究记录。

屏幕说用了 5 份有发布日的资料。它们是 Crossref 按词命中的论文，题目涉及金银花提取、切换系统、股骨骨折，以及一篇 1984 年的薄膜。不是对这项策略的综述。时点通过，是因为这些日期不晚于截止日。

界面上没有「未经许可」的勾选。Yahoo 和 AkShare 仍会被自动选上。这次是维护者自己的测试，不是 Yahoo 的许可，也不是业绩。

![SPY 研究的确认卡](docs/readme-assets/02-confirm-to-run.png)

![运行中，仍在取数](docs/readme-assets/03-running.png)

![完成。三道门没过。策略包仍然锁着。](docs/readme-assets/04-completed-gates.png)

![已导出研究记录](docs/readme-assets/05-export-record.png)

截图没印出的库存是：回看停在 40 天，入场 z 仍为 1.0，只做多。市场计分卡即使你没点名也会跑。导出包里 `live_handoff_eligible` 为 false，失败项是 `all_current_methods_passed`。

## 它怎么拼在一起

![桌面、引擎和你的磁盘](docs/readme-assets/architecture.svg)

活在桌面里。引擎取日线、做模拟、给冻结的检查打分。SQLite、快照和导出都在你的数据目录。Linux 默认是 `~/.local/share/ai.alphastrategy.alphaloop`。可以用 `ALPHALOOP_DATA_ROOT` 改。上面那一次用了临时目录，所以最后一张图的路径以 `/tmp` 开头。

## 今天有的，以及方向里还没有的

![0.2.0 已经有的，以及定位文档写了但这一版不会跑的](docs/readme-assets/today-and-direction.svg)

右边一栏是产品方向，不是 0.2.0 的功能。低波、股债再平衡、基本面因子、全天候在代码里有名字，开跑会被拒绝。动量不会被拿来顶替。定位见 [docs/requirements/product-positioning.md](docs/requirements/product-positioning.md)。这一版承诺什么，看 [V1 交付收口](docs/requirements/v1-cut-line.md)。

## 这些情况用别的

- 要分钟或 tick、要券商、要模拟账户。alphaloop 不连接这些。
- 要扫成千上万组参数并留下夏普最高的一组。[vectorbt](https://github.com/polakowo/vectorbt) 就是为扫描做的。这里记的是少量轮次。
- 要在浏览器里研究，并用别人整理好的财务数据。[聚宽](https://www.joinquant.com/)和[米筐](https://www.ricequant.com/doc/quant/)是托管的研究平台。会员价格没有抄到这里。
- 要一个自己改代码的事件驱动回测库。[zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) 和 [backtrader](https://github.com/mementum/backtrader) 是那种库。[LEAN](https://github.com/QuantConnect/Lean) 是开源引擎，另有可以下单的托管产品。[Qlib](https://github.com/microsoft/qlib) 是模型流水线。它们都不是这份试验账本。

## 相信一个数字之前

- 个股按复权价请求。美股用调整后的 Yahoo 价格，A 股用前复权。基准仍是价格指数：`SPX` 取数时换成 `^GSPC`，`000300.SH` 取指数。这不是同一种口径。
- 回测里的成本和换手门禁不是同一个数。上面的成本已经进了收益之后，门禁还会再减一次：美股 10 bp、A 股 20 bp，乘以年化换手。换手等于 1 时，美股门禁再减 0.001。不要把 5 和 10 加成 15。
- A 股不模拟 T+1 和涨跌停，真实成交可能更差。完成页会写。确认卡上是成本那一行。
- 默认名单不是时点成分。时点通过并不排除幸存者偏差。
- Yahoo Finance 和 AkShare 是非官方或学术用途的数据。0.2.0 开跑前不会请你确认这一点。条款请自己判断。界面上的来源名不是数据许可。
- 没有可引用的用户数、客户或业绩。上面的 SPY 研究没有通过门禁。那就是结果，不是承诺。

## 许可，以及怎么参与

MIT。版权 (c) 2026 AlphaStrategyAI。全文在 [LICENSE](LICENSE)。许可覆盖的是这份代码，不包括行情数据的权利。没有付费方案，没有托管，没有支持合同。

没有贡献指南，也没有可领的任务。如果软件和本页不一致，请开 [Issue](https://github.com/AlphaStrategyAI/alphaloop/issues)，写上日期、命令和状态 JSON。不要只为了把这一版还不会跑的策略族或知情确认补进去而提补丁。以代码和本页为准，不以还没落地的规格句子为准。

桌面可以把密钥放进系统钥匙串；没有钥匙串时，可以只留在本次会话，或放进口令加密的文件。不要把密钥写进 Issue。设置里现在能用的是界面语言。数据商和大模型页面还没有做。

## 接着读

- [V1 交付收口](docs/requirements/v1-cut-line.md)：这一版承诺什么。
- [产品定位](docs/requirements/product-positioning.md)：方向。它比 0.2.0 宽。
- [术语表](docs/GLOSSARY.md)
- [设置规格](docs/requirements/settings-config-v1.md)
- [路径](docs/requirements/paths-contract.md)
