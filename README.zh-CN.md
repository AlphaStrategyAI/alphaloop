[English](README.md) | 简体中文

# alphaloop

一台电脑上的日频股票研究工坊。你把研究说清楚。alphaloop 在你的机器上把轮次跑完，留下一份写明试了多少次、哪道门没过的文件。它不下单。

现在能开跑的是均值回归。你确认开跑卡，引擎自己迭代，最后要么拿走策略包，要么拿走一份写明为什么包还锁着的研究记录。

![准备新建研究](docs/readme-assets/01-research-list.png)

![说清、确认、迭代、留下文件](docs/readme-assets/study-loop.gif)

## 开始

需要 Python 3.12、Git、Node.js 22、Rust 和系统 WebView。打包引擎还需要 `python3.12-venv`。没有安装包，PyPI 上也没有这个名字。

```bash
git clone https://github.com/AlphaStrategyAI/alphaloop.git
cd alphaloop
python3 -m pip install -e ".[dev]"
bash scripts/build_sidecar.sh
python3 scripts/stage_sidecar.py --target linux --source dist/alphaloop-engine --tauri-root apps/desktop/src-tauri
cd apps/desktop && npm ci && npm run tauri dev
```

macOS 把 `--target` 换成 `macos`，Windows 换成 `windows`。Linux 上先装好 WebKitGTK 4.1。从「新建研究」进入。命令行只能启动引擎并查看状态。如果它还占着锁，先停掉再开桌面。

## 你拿到什么

- **研究留在你的电脑上。** 研究、快照和导出都在本机目录里。没有账号，也没有托管。
- **开跑前看得到这笔交易。** 确认卡写出标的、区间、来源和成本。美股个股单边 5 bp，美股基金 1 bp，A 股个股 20 bp，A 股基金 5 bp。
- **成交用的是上一根 K 线。** 信号先算出来，再错开一根 bar 才变成权重。你不会用刚刚量过的那根收盘价成交。
- **小改动自己继续，换一个想法就停下。** 最多自动跑五轮。每一轮把回看天数加五天，从 20 天、入场 z 值 1.0、只做多开始。经济逻辑变了，就等你确认。
- **文件记得试过几次。** 轮次会存下来，也会进导出。轮次变多不会把门槛放宽。
- **策略包是挣来的。** 只有研究做完、冻结的检查通过、没有待确认、时点检查也跑过并且通过，才能导出策略包。否则你仍然能导出研究记录，上面写着缺哪一项。包里的回测是历史假设，不是预测，也不是实盘结果。

不指定代码时，用仓库里的标普 500 和沪深 300 名单，各取名单生成那天的成分，分别是 503 只和 300 只。这不是当时的成分。更早的历史带有幸存者偏差，界面会写出来。你输入代码，名单就被换掉。只有一只时，用它自己的滚动波动。多只时，做截面比较。

![确认卡上有标的、区间、来源和成本](docs/readme-assets/02-confirm-to-run.png)

## 做完长什么样

一次真实的美股均值回归可以停在这里：三道检查没过，时点通过，策略包仍然锁着，导出的是研究记录。

「每一项已选验证方法都通过」旁边的空心圆表示没过。绿色的重新验证标记即使没有做过重验也会亮，因为空列表算通过。市场计分卡即使你没点名也会跑。

![研究做完，策略包仍然锁着](docs/readme-assets/04-completed-gates.png)

时点检查只问：被引用的资料，是不是在回测结束前已经发表。没有日期的笔记会被丢掉，并不因此失败。一项研究可以在没有外部资料时通过。它不检查指数里有谁、价格怎么复权、财报有没有修订。通过也不表示没有幸存者偏差。

那次运行里的五份有日期的资料，是论文库按关键词命中的结果，不是对这个策略的综述。所以时点通过不等于读过一批相关论文。

## 怎么拼在一起

![桌面、引擎，以及留在磁盘上的文件](docs/readme-assets/architecture.svg)

你在桌面里工作。引擎取日线、做模拟、给一套冻结的检查打分。留下的东西都在你的数据目录里。Linux 上默认是 `~/.local/share/ai.alphastrategy.alphaloop`，也可以用 `ALPHALOOP_DATA_ROOT` 改。

美股日线来自 Yahoo Finance，A 股日线来自 AkShare。论文来自 Crossref。公告来自 SEC EDGAR。你自己的笔记放在本机文件夹。这些来源是非官方的，或只限于研究用途。软件会替你选上，还不会先请你确认。卡片上的名字不是数据许可。

## 现在，以及接下来

![现在能跑的，以及还只是规划](docs/readme-assets/today-and-direction.svg)

**现在。** 美股和 A 股的日频均值回归。五项设定，本机运行，记下轮次，导出时宁可失败也不放行。

**规划，还不能跑。** 一个更粗的想法，可以放很久。低波、股债再平衡、基本面因子、全天候。一套会随研究变厚的验证方法。在那之前不提供动量，也不会悄悄改跑均值回归。下单仍然不做。方向写在[产品定位](docs/requirements/product-positioning.md)。现在做到哪一步，写在[交付说明](docs/requirements/v1-cut-line.md)。

## 什么时候用别的

想要本机上的日频股票研究，并且要一份试验账本，用 alphaloop。

要券商、模拟账户、分钟或 tick，用别的。要扫一大片参数，用 [vectorbt](https://github.com/polakowo/vectorbt) 这种扫描库。研究应该留在浏览器里，用[聚宽](https://www.joinquant.com/)或[米筐](https://www.ricequant.com/doc/quant/)。要自己改一个回测引擎或模型流水线，用 [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded)、[backtrader](https://github.com/mementum/backtrader)、[LEAN](https://github.com/QuantConnect/Lean) 或 [Qlib](https://github.com/microsoft/qlib)。

## 相信一个数字之前

复权价和拿来比较的指数不是同一口径。美股用调整后的 Yahoo 价格，A 股用前复权。基准仍是价格指数。

卡片上的成本和换手检查里的成本不是同一个数。卡片上的成本已经进了收益，检查还会再减一次：美股 10 bp，A 股 20 bp，乘以年化换手。不要把两个比率加在一起。

A 股结果没有模拟次日才能卖，也没有模拟涨跌停。市场上的成交可以更差。做完的那一页会写明。

## 许可

MIT。版权 (c) 2026 AlphaStrategyAI。全文在 [LICENSE](LICENSE)。许可的是这份代码，不是行情。没有付费方案，也没有支持合同。

没有贡献任务列表。如果软件和本页不一致，请开一个 [Issue](https://github.com/AlphaStrategyAI/alphaloop/issues)，附上命令和状态输出。密钥放进桌面的保险库，不要写进 Issue。设置里现在能用的是界面语言。

- [术语表](docs/GLOSSARY.md)
- [设置](docs/requirements/settings-config-v1.md)
- [路径](docs/requirements/paths-contract.md)
