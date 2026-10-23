# alphaloop

AlphaLoop 0.2.0 runs one daily equity mean-reversion study on your own machine and keeps the trial count, the gate results, and a file you can take away. It does not send orders, and it does not decide whether you should use the strategy.

It is for someone who already backtests. You may have a notebook, a spreadsheet, or a hosted platform, and a curve that looks good, without a record of how many variations were tried or whether a signal used a price that did not exist yet. This version does that one job: cross-sectional mean reversion, with failed checks written down. It does not turn an arbitrary idea into a strategy, and it does not connect to a broker.

There is no installer, no hosted service, and no paid plan. Clone the repository, start the engine locally, then open a study in the desktop app.

The Chinese README is [README.md](./README.md). This file states the same facts. The English UI currently shows strategy-family ids as stored, for example `mean_reversion`, rather than a translated name.

## One concrete job

The question is whether stocks that fell recently move back toward a recent mean.

A common approach is to score closes in a notebook, try a few lookback windows, and keep the best equity line. Three things usually go wrong. The signal and the fill use the same bar's close. The number of trials is not in any file. The result stays on someone else's site, and what you take away is a chart rather than the verifier definitions that produced it.

In alphaloop the dialogue locks five settings: the economic thesis, the universe, a cap on effective research time, the first-round verifiers, and a minimum data-coverage floor. If the thesis says momentum, trend, or breakout, the confirm card and the completed screen say that is not supported. The engine still runs only cross-sectional mean reversion. After you confirm, signals are computed and then shifted by one bar before the weights are applied. This version auto-iterates at most 5 rounds by default, and the automatic change adds 5 days to the lookback. A change of economic logic stops and waits.

A strategy pack is exported only when all five of these hold: the study is completed, every frozen verifier on the current round passed, nothing is waiting for confirmation, reverification of the current round passed, and the point-in-time check ran and passed. Otherwise the export is a research record that names the failed check. The backtest in the pack is a historical hypothesis, not live performance and not a forecast.

There is no measured time saving. The visible change is that the trial count and the failed gates stay in the record.

## What works, and what does not

**Works**

- Lock the five settings in the desktop app and run a historical study. The default reviewer is deterministic and does not call a model. An external model is used only when `ALPHALOOP_REVIEWER=subagent` and `ALPHALOOP_LLM_BASE_URL`, `ALPHALOOP_LLM_API_KEY`, and `ALPHALOOP_LLM_MODEL` are all set. If any of those is missing, the review fails closed.
- With no tickers typed, a new study uses a generated-date list shipped in the repo. US: `us_equity_large_cap_v2`, S&P 500 constituents as of 2026-10-16, 503 names. China A-shares: `cn_equity_large_cap_v2`, CSI 300 constituents as of 2026-10-19, 300 names. Studies that already point at v1 keep those 40-name lists. Typed tickers replace the default pool.
- Those lists are membership on the list date, not point-in-time membership. Earlier history carries survivorship bias. The stored flag is `survivorship_bias_untested`. That flag does not fail the point-in-time check.
- Export a research record. Export a strategy pack only when the five checks pass. Whoever receives the pack implements execution. alphaloop does not connect to a broker.

**Not done, or not safe to treat as done**

- No orders, no broker, no paper-trading session. The CLI can only start the engine and show status.
- Low volatility, stock-bond rebalance, fundamental factor, and all-weather have ids and Chinese display names. Starting one returns "这一族还不能开跑。" (this family cannot be run yet).
- Local CSV import, vendor data connectors, and the data-source and model pages in Settings are still the later page. The settings page that works is interface language: follow the system, Chinese, or English.
- The product spec says Yahoo and AkShare must be labeled unlicensed, and that a study cannot start until you acknowledge that. Version 0.2.0 pins `yahoo_daily` or `akshare_sina_daily` from the symbols. The UI says "雅虎日线" and "AkShare 日线（新浪优先）". The glossary contains the word "未经许可". The confirm flow does not ask for that acknowledgement.
- The spec also names an export check `coverage_satisfied`. `strategy_pack_eligibility` has no such key. Coverage can stop a run while it is going; it is not one of the keys in that function.
- Point-in-time (pit-v2) checks whether a cited source's publication date is on or before the backtest cutoff. Undated material is not treated as evidence. The check does not cover index membership, adjustment factors, or restated financials.
- There is no citable user count, customer, or track record. On 2026-10-23 the public repository had no GitHub Release, discussions were disabled, and there were no open issues.

## Fastest path

Python 3.12 and Git. The desktop app also needs Node.js 22, Rust, and a system webview. The typecheck workflow uses Node 22. The macOS packaging workflow says Node 20; desktop tests were not re-run on Node 20 here. On Linux, CI installs `libwebkit2gtk-4.1-dev` and the related packages. Building the engine sidecar also needs the `python3.12-venv` package: on 2026-10-23, `scripts/build_sidecar.sh` exited 1 on a machine without it, because the virtual environment had no ensurepip. On that date, `https://pypi.org/pypi/alphaloop/json` returned 404. The package is not on PyPI.

```bash
git clone https://github.com/AlphaStrategyAI/alphaloop.git
cd alphaloop
python3 -m pip install -e ".[dev]"
python3 -m apps.cli.main start
python3 -m apps.cli.main status
```

After `start`, `status` prints one JSON line. This is one Linux run from 2026-10-23. The pid changes every time:

```json
{"awaiting_confirm": false, "has_running_research": false, "owner": "cli", "pid": 11699, "running": true}
```

That means the engine process is up. The CLI cannot create a study, confirm it, or export it. There is no `stop` subcommand. Stop the pid shown by `status`.

A study runs in the desktop app, which first needs a packaged engine sidecar. The build creates `.venv-sidecar` and runs PyInstaller. How long it takes depends on the machine and the network:

```bash
bash scripts/build_sidecar.sh
python3 scripts/stage_sidecar.py --target linux --source dist/alphaloop-engine --tauri-root apps/desktop/src-tauri
bash scripts/smoke_sidecar.sh
cd apps/desktop
npm ci
npm run tauri dev
```

Use `--target macos` or `--target windows` on those systems. In the app, create a study under Research. The dialogue asks for the five settings. To get through the engine that exists today, state a mean-reversion thesis and choose US equities or A-share equities. When the five settings are locked, the confirm card appears. Starting the run downloads daily bars and needs a network. The planned window is 12×365 days back from today's UTC date. If the download fails or coverage falls through the floor you accepted, the study stops and says why. It does not switch to a price file that is not in the repository.

On the completed screen, a failed gate exports a research record only. The strategy pack stays unavailable and the screen names the missing check. All five checks have to pass before a strategy pack is exported.

Checks that do not hit the market:

```bash
python3 -m pytest -q -m "not network"
cd apps/desktop && npm test
```

One pytest item is a Rust contract test. CI plants an empty engine placeholder before running it. Without that placeholder and without the GTK development packages, that one test fails. The other offline tests do not need it.

On Linux, data defaults to `~/.local/share/ai.alphastrategy.alphaloop` (`research.db`, `materials/`, `exports/`, `snapshots/`, `engine.log`). The lock and `owner.json` use `platformdirs` `user_runtime_path("alphaloop")`. With no `XDG_RUNTIME_DIR`, that falls under a temp `runtime-<uid>/alphaloop`. Override either root with `ALPHALOOP_DATA_ROOT` or `ALPHALOOP_RUNTIME_ROOT`.

## What to trust, and what not to

What you can check is the repository, the license, and a local run. There is no third-party audit and no performance case study.

The MIT copyright line is `Copyright (c) 2026 OpenStrategy Team`. The GitHub organization is AlphaStrategyAI. MIT allows use, modification, and redistribution of this code, including commercial use, if the copyright and license notice are kept. It does not warranty the software, and it does not grant rights to market, filing, or index data.

US daily bars go through [yfinance](https://github.com/ranaroussi/yfinance). That project's README says it is not affiliated with Yahoo, is meant for research and education, and tells you to read Yahoo's terms yourself. A-share daily bars go through [AkShare](https://github.com/akfamily/akshare), Sina first, Eastmoney if Sina fails. AkShare's README says the data is for academic research, is not investment advice, and that some interfaces may be removed. Either source can fail or change. The product spec wants both labeled unlicensed. As written above, the 0.2.0 UI does not do that yet.

Papers are fetched from Crossref. Issuer filings are fetched from SEC EDGAR with a fixed User-Agent: `alphaloop/0.2 research@example.invalid`. That is not your contact address. Local Markdown belongs in the data directory's `materials/`.

The equity benchmark is a price index: `SPX` for the US, `000300.SH` for A-shares. Strategy returns are percentage changes of the price series. If the upstream series is split-adjusted, it is not the same measure as the price index.

Confirming a new run sets the cost model to `schedule_v1`. Net backtest returns are charged on turnover: 5 bp one way for US equities, 1 bp for US funds, 20 bp for A-share equities, 5 bp for A-share funds. A 5% single-name weight cap applies when at least 20 names can be held and the book is not a fund and not long/short. The turnover gate is a second calculation: 10 bp for the US and 20 bp for A-shares, subtracted from annualized excess as annualized turnover times bp/10000. When the return series is already net of `schedule_v1`, the gate still subtracts again. The glossary sentence that says the return series itself has no daily costs describes the older `legacy_zero` path. An old A-share record reverified from a frozen snapshot stays on that path. The A-share confirm card says that T+1 and price limits are not simulated, so real fills can be worse.

Rounds on the same data window accumulate in SQLite and in exported `history/rounds.json`. A larger count does not loosen a threshold. After the default budget is spent, every further round needs your confirmation. At 20 accumulated rounds it asks again. Those defaults (5, 5, and 20) live in `engine/research/honest_stop.py` and can be changed with `ALPHALOOP_MAX_TRIALS`, `ALPHALOOP_TRIAL_BUDGET_INCREMENT`, and `ALPHALOOP_HIGH_SUSPICION_ROUNDS`.

An unusually good result is shown as a checklist of provenance, whether coverage was shrunk, how many trials ran, and which verifier revision was used. It is not a celebration.

## Compared with what people already use

Checked against documents retrieved on 2026-10-23. Pages that did not open are not turned into numbers.

| Approach | What it actually offers | What it does not do for you |
| --- | --- | --- |
| Your own Python or a spreadsheet | It runs exactly the code you wrote. Look-ahead is yours to avoid. | Trial counts usually never land in a file, and there is no shared export gate. |
| [vectorbt](https://github.com/polakowo/vectorbt) | Large parameter sweeps on your machine. The README separates the community edition from paid VectorBT PRO. The license is Apache 2.0 with the Commons Clause. | A sweep does not record how many combinations you threw away. |
| [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) 3.2.0 (2026-10-18) | Event-driven backtests, Apache 2.0. Maintainers limit the project to bug and compatibility fixes and point new work at ML4T Backtest. Release 3.2 does not support pandas 3. | Not a research record with an export gate. |
| [backtrader](https://github.com/mementum/backtrader) 1.9.78.123 | An event-driven framework, GPLv3+. That PyPI release is dated 2023-04-19. Broker integrations are in the library. | Upstream releases stop at that version. It is a trading framework, not a trial ledger. |
| [JoinQuant](https://www.joinquant.com/) | Research, backtest, and paper trading in the browser. The official API document says that querying fundamentals by reporting period can introduce future data, and that `use_real_price` defaults to false. | The study lives on their servers. Their pricing page returned 403 here, so no membership price is stated. |
| [RiceQuant](https://www.ricequant.com/doc/quant/) | Browser research on RQData. The docs' basic tier has no paper-trading slots; the enterprise tier does. Their PDF says the trial account lasts one month. | Formal data prices are via sales. A forum quote is not used here. |
| [LEAN](https://github.com/QuantConnect/Lean) | The engine is Apache 2.0 and can run locally. QuantConnect's cloud is a separate subscription that includes live trading. | No currency figure from the pricing page was verified, so none is quoted. The product includes order routing. |
| [Qlib](https://github.com/microsoft/qlib) | Microsoft's MIT platform for data, model training, and backtesting. `pip install pyqlib` still leaves data preparation to you. | It is a model pipeline. It does not answer how many rounds this study tried or which gate failed. |

Stay with those tools when you need minute or tick bars, a broker, low-volatility, stock-bond, fundamental, or all-weather research, or fundamentals someone else maintains. Version 0.2.0 does none of that. If the job is to sweep many parameters and keep the highest Sharpe, vectorbt does that sweep. alphaloop does not.

## License, money, and participation

There is no paid tier, no paid support, and no hosted instance. What you can do is install it and run one study, open an [issue](https://github.com/AlphaStrategyAI/alphaloop/issues) when the behavior is wrong, or open a pull request.

There is no `CONTRIBUTING` file. Discussions are disabled. The `good first issue` label exists, and on 2026-10-23 no open issue used it. Read the [V1 cut line](./docs/requirements/v1-cut-line.md) before changing code. The mean-reversion path that already shipped is not rewritten by later specs. The five strategy families are specified in [strategy families v1](./docs/requirements/strategy-families-v1.md). That document is a spec, not the list of families the engine can run.

There is no public hiring notice. This page is not a recruiting pitch.

## Known limits

- The default automatic budget is 5 rounds. If a design mock shows more, the code is what runs.
- The data-window key includes the confirmation date. Opening the same idea the next day starts a new window.
- Automatic iteration does not search the entry threshold and does not change family.
- "分段稳健性检验" splits an already computed return series in time. It is not a walk-forward that refits parameters. "集中度" is position weight, not market crowding. The old phrases still parse in the dialogue.
- The 5 bp inside the backtest and the 10 bp inside the gate are not the same cost. See the two cost layers above.
- `pyproject.toml` does not pin dependency versions. The install on 2026-10-23 resolved pandas 3.1.0, yfinance 1.7.0, and akshare 1.19.3. Another day can resolve differently.
- On that date `npm audit` reported 2 moderate and 2 high issues in dev dependencies, and 0 with `--omit=dev`. That is not a security audit.

## Docs

- [Product positioning](./docs/requirements/product-positioning.md): what the product is meant to become. It is wider than 0.2.0 and is not a feature list.
- [V1 cut line](./docs/requirements/v1-cut-line.md): what this version promises.
- [Glossary](./docs/GLOSSARY.md)
- [Settings spec](./docs/requirements/settings-config-v1.md): a spec, not a finished settings UI.
- [Path contract](./docs/requirements/paths-contract.md)

## License

MIT. Full text in [`LICENSE`](./LICENSE).
