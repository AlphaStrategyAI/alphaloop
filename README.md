English | [简体中文](README.zh-CN.md)

# alphaloop

**A local workshop for one daily equity idea.**

You name the study. AlphaLoop runs the rounds on your machine and leaves a file that says how many were tried and which checks failed. It does not send orders, and it does not tell you whether to use the strategy.

**Version 0.2.0 runs mean reversion.** That is the strategy you can start today.

![AlphaLoop research list](docs/readme-assets/01-research-list.png)

![How one study moves](docs/readme-assets/study-loop.gif)

## Install

Python 3.12 and Git. The desktop also needs Node.js 22, Rust, a system webview, and `python3.12-venv` when you build the engine. There is no installer. The name `alphaloop` is not on PyPI.

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

On macOS pass `--target macos`. On Windows pass `--target windows`. Linux CI installs `libwebkit2gtk-4.1-dev` and the related packages. The typecheck workflow uses Node 22. The macOS packaging workflow uses Node 20.

If `python3 -m apps.cli.main start` is already running, stop that process before the desktop app. They share one runtime lock. The command line can only start the engine and print status. The study itself is in the desktop app.

## Why it is worth opening

You already have a notebook, a sheet, or a hosted backtest. Three things still go missing.

| What usually happens | What 0.2.0 writes down |
| --- | --- |
| The signal and the fill use the same close. | The signal is shifted one bar before the weights. |
| You keep the best curve and lose the count of tries. | The round count is stored and exported. A higher count does not loosen a gate. |
| The result lives on someone else's site. | The study and the export stay on your disk. There is no hosted account. |

AlphaLoop does not replace a broker, a minute-bar engine, or a parameter sweep. It replaces the moment you are about to trust a daily equity curve that has no trial ledger.

## What you can do in 0.2.0

**Name five things, then leave it.** Thesis, universe, time cap, first-round verifiers, and a coverage floor. Pauses and time spent waiting do not count against the cap. One message can fill more than one setting.

**It continues the small steps.** The default budget is 5 rounds. Each automatic step adds 5 days to the lookback. That increment is fixed in the code. The first round starts at 20 days, entry z of 1.0, long only. A change of economic logic stops and waits for you.

**You see the data before it runs.** The confirm card shows the names, the date window, the source, and the cost. US equities are charged 5 bp one way, US funds 1 bp, China A-share equities 20 bp, A-share funds 5 bp. A 5% single-name cap applies only when at least 20 names can be held, and not for a fund or a long/short book.

**Gates decide the file.** A strategy pack is exported only when the study is finished, the frozen verifiers on the current round passed, nothing is waiting, recorded reverifications other than point-in-time passed, and point-in-time ran and passed. If any check fails, you still export a research record. The pack's backtest is a historical hypothesis, not live performance and not a forecast.

**Point-in-time means one thing.** Cited material must be published on or before the backtest cutoff. Undated material is dropped and does not fail the check. A study can pass with no external evidence. The check does not cover index membership, price adjustments, or restated financials. Survivorship bias does not fail it.

**US and China A-share lists ship in the repo.** With no tickers typed, a new study uses the S&P 500 membership of 2026-10-16 (503 names) or the CSI 300 membership of 2026-10-19 (300 names). Those are membership on the list date, not membership at the time. Earlier history carries survivorship bias. The on-screen note says so. Typed tickers replace the list. Older studies keep the 40-name lists they already reference.

## A run we made

On 2026-10-23 a maintainer opened the desktop on Linux and ran one study. The window was English. The message asked for US equity mean reversion on SPY, a 12-hour cap, four verifiers, and a coverage floor of 1 name, 1 year, and at most 20% missing. The confirm card showed one name, SPY, Yahoo daily bars from 2014-10-26 to 2026-10-23, and a cost of 5 bp, because the message classified the book as equities rather than a fund.

Run was clicked at 15:06:47 UTC. The stored row completed at 15:06:54 UTC. The screen shows effective time as 0.00 hours, because those seconds are below one hundredth of an hour, and it shows 5/5 rounds. Market scorecard, out-of-sample stability, and turnover cost failed. Subperiod robustness and concentration passed. Point-in-time passed. The empty circle next to "Every selected verification method passed" is the failed state. The green re-verification chip was on even though no re-verification was stored; an empty list passes that check. The strategy pack stayed locked. Export wrote a research record.

The screen said five dated materials were used. They are keyword hits from Crossref, including papers on herbal extraction, switched systems, femoral fractures, and a 1984 film. They are not a review of this strategy. Point-in-time passed because those dates were not after the cutoff.

There was no checkbox for an unlicensed source. Yahoo and AkShare are still selected automatically. This run was the maintainer's own test. It is not permission from Yahoo, and it is not a track record.

![Confirm card for the SPY study](docs/readme-assets/02-confirm-to-run.png)

![Running, still gathering](docs/readme-assets/03-running.png)

![Completed. Three gates failed. The strategy pack stayed locked.](docs/readme-assets/04-completed-gates.png)

![Research record exported](docs/readme-assets/05-export-record.png)

The stored study, not the pictures, ended at a lookback of 40 days and kept entry z at 1.0, long only. The market scorecard runs even when you did not name it. The export zip sets `live_handoff_eligible` to false and names `all_current_methods_passed` as the failed check.

## How it fits together

![Desktop, engine, and your disk](docs/readme-assets/architecture.svg)

The desktop is the place you work. The engine gathers bars, simulates, and scores frozen checks. SQLite, snapshots, and exports stay under your data directory. On Linux that default is `~/.local/share/ai.alphastrategy.alphaloop`. Override it with `ALPHALOOP_DATA_ROOT`. The run above used a temporary override, which is why the export path in the last picture starts with `/tmp`.

## Today, and what the direction describes

![What 0.2.0 ships, and what the positioning document describes but this build does not run](docs/readme-assets/today-and-direction.svg)

The right-hand column is the product direction. It is not a feature of 0.2.0. Low volatility, stock-bond rebalance, fundamental factor, and all-weather have names in the code and refuse to start. Momentum is not offered as a substitute. The positioning document is [docs/requirements/product-positioning.md](docs/requirements/product-positioning.md). Read the [V1 cut line](docs/requirements/v1-cut-line.md) for what this version promises.

## Use something else when

- You need minute or tick bars, a broker, or a paper account. AlphaLoop does not connect to one.
- You want to sweep thousands of parameters and keep the highest Sharpe. A library such as [vectorbt](https://github.com/polakowo/vectorbt) is built for that sweep. This project records a small number of rounds instead.
- You want the study in a browser, with someone else's cleaned fundamentals. [JoinQuant](https://www.joinquant.com/) and [RiceQuant](https://www.ricequant.com/doc/quant/) are hosted research platforms. Their membership prices were not copied here.
- You want an event-driven backtester you extend in code. [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) and [backtrader](https://github.com/mementum/backtrader) are that kind of library. [LEAN](https://github.com/QuantConnect/Lean) is an open engine with a separate hosted product that can send orders. [Qlib](https://github.com/microsoft/qlib) is a model pipeline. None of them is this trial ledger.

## Before you trust a number

- Equity bars are requested adjusted. US names use adjusted Yahoo prices. A-share names use forward-adjusted prices. The benchmark is still a price index: `SPX` fetched as `^GSPC`, and `000300.SH` fetched as an index. Those are not the same measure.
- The backtest cost and the turnover gate are different numbers. After the cost above is already in the return series, the gate subtracts again: 10 bp for the US and 20 bp for A-shares, times annualized turnover. If that turnover equals 1, the US gate subtracts another 0.001. Do not add 5 and 10 and call it 15.
- A-share results do not model the one-day settlement rule or price limits. Real fills can be worse. The completed screen says so. The confirm card shows the cost line.
- The default lists are not point-in-time membership. A point-in-time pass does not clear survivorship bias.
- Yahoo Finance and AkShare are unofficial or academic-use feeds. Version 0.2.0 does not ask you to acknowledge that before a run. Judge the terms yourself. The label on screen is not a data license.
- There is no published user count, customer, or track record. The SPY study above failed its gates. That is the result. It is not a promise.

## License and how to take part

MIT. Copyright (c) 2026 AlphaStrategyAI. Full text in [LICENSE](LICENSE). The license covers this code. It does not grant rights to market data. There is no paid plan, no hosted service, and no support contract.

There is no contributor guide and no open task list. If the app disagrees with this page, open an [issue](https://github.com/AlphaStrategyAI/alphaloop/issues) with the date, the command, and the status JSON. Do not send a patch whose only purpose is to implement the families or the acknowledgement that 0.2.0 does not run. The code and this page win over a spec sentence that has not shipped.

The desktop can store a secret in the system keychain, or, if you have none, in memory for the session or in a passphrase-encrypted file. Do not put a secret in an issue. The settings page that works is the interface language. Data-vendor and model pages are not built yet.

## Further reading

- [V1 cut line](docs/requirements/v1-cut-line.md) is what this version promises.
- [Product positioning](docs/requirements/product-positioning.md) is the direction. It is wider than 0.2.0.
- [Glossary](docs/GLOSSARY.md)
- [Settings spec](docs/requirements/settings-config-v1.md)
- [Paths](docs/requirements/paths-contract.md)
