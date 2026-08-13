---
tags: [changelog, v1.1, alphaloop]
---

# Changelog

All notable changes to alphaloop are documented in this file.

## [1.1.3] - 2026-07-12

### Added (M1 — diagnostic package)
- `alphaloop.diagnostic` package with 4 modules:
  - `deflated_sharpe()` / `expected_max_sharpe()` — DSR for multiple-testing correction
  - `walk_forward_cv()` — rolling-window out-of-sample CV
  - `data_source_consistency()` — multi-source disagreement check
  - `vs_random()` / `vs_buy_hold()` / `vs_spy_buyhold()` — 3 benchmark comparisons
- 49 unit tests

### Added (M2 — engineer package)
- `alphaloop.engineer` package with 10 alpha factors:
  - Momentum: `rsi`, `macd`, `roc`, `momentum_12_1`
  - Mean Reversion: `bollinger_zscore`, `ohlr_4_pct`, `pairs_spread`
  - Volatility: `atr_breakout`, `parkinson_hist_vol`
  - Volume: `obv_slope`
- 33 unit tests
- `examples/alpha_comparison_demo.py`

### Added (M3 — live trading)
- `alphaloop.live` package with hard-walled `AlpacaAdapter`:
  - Default: paper trading (`https://paper-api.alpaca.markets`)
  - Live: requires both `paper=False` AND `confirm_live=True` (double opt-in)
  - Zero live-account network calls in tests
  - 39 unit tests covering safety interception + mock HTTP

### Added (v1.1.1 — no_lookahead)
- `@no_lookahead` decorator: validates factor has no look-ahead bias
  via two-shock test (second half + first half)
- `alphaloop.engineer.audit` module: `audit_factors()` driver
  and `python3 -m alphaloop.engineer.audit` CLI
- pytest `no_lookahead` marker registered
- 20 new tests; 10/10 factors PASS audit

### Added (v1.1.2 — integration tests)
- `tests/integration/` with 4 data source test files (yahoo, akshare,
  ccxt, openbb). Default skip; enable with `OPENSTRATEGY_INTEGRATION=1`.
- OpenBBSource wired-in gap documented via `pytest.xfail`.

### Added (finalize)
- `alphaloop report` CLI: answers the 6 v1.0 acceptance questions
  on synthetic data; writes Markdown report via `--output`.
- Streamlit WebUI (`src/alphaloop/ui.py`): 4 pages
  (Home / Overfit Check / vs Buy & Hold / vs SPY), offline-only.
- `examples/comparison_demo.py`: 5-strategy head-to-head.

### Documentation
- `docs/lessons/m1-retrospective.md`
- `docs/lessons/m2-retrospective.md`
- `docs/lessons/m3-retrospective.md`
- `docs/lessons/v1.1.1-retrospective.md`
- `docs/lessons/v1.1.2-retrospective.md`
- `docs/v1.0-wrapping-report.md`

### Fixed
- `data_source_consistency` look-ahead bug (M1 retro)
- `atr_breakout` rolling-window look-ahead bug (M2 retro)
- `pairs_spread` window > overlap bug (M2 retro)
- `deflated_sharpe` `None`-fill semantic confusion (M2 retro)
- `test_akshare_not_installed_raises` skip-when-installed
  logic (v1.1.2 retro)

### Test results
- v1.0: 171/171 pass
- v1.1.1: 191/191 pass
- v1.1.2: 190 passed + 1 skipped + 11 deselected (unit) /
  5 passed + 2 xfailed + 4 failed (integration, sandbox-limited)

## [1.0.0] - 2026-07-09 (c95a6bd)

### Added
- 4 data sources: Yahoo Finance, AKShare, CCXT, OpenBB
- 11 base strategies (BuyHold, Rebalance, etc.)
- Core backtest engine
- CLI: `backtest`, `optimize`, `fetch`
- 33 unit tests

[1.0.0]: https://github.com/fpc0000/alphaloop/releases/tag/v1.0.0
[1.1.3]: https://github.com/fpc0000/alphaloop/releases/tag/v1.1.3
