# alphaloop v0.5

> **AI-automated quant research loop.**
> Jeff Dean style: "design loops that prompt your agents" — but for quant.
> Honest, verifiable, agent-friendly. **alpha → loop → report → iterate**.

alphaloop is an open-source framework for individual investors and small
research teams who want to evaluate trading strategies honestly AND run them
inside an AI-driven research loop.

It ships:

- 4 data sources (Yahoo Finance, AKShare, CCXT, OpenBB)
- 10 alpha factors across 4 families (momentum, mean-reversion,
  volatility, volume)
- 6 diagnostic tools (Deflated Sharpe Ratio, walk-forward CV,
  cross-source consistency, vs random, vs buy-and-hold, vs SPY)
- A read-only broker adapter (Alpaca paper-by-default, hard-walled
  against accidental live trading)
- A CLI (`alphaloop report`) that generates a Markdown acceptance
  report answering the 6 v1.0 questions for any strategy
- **Coming in v0.6+**: `alphaloop loop` — autonomous research loop
  driven by LLM agents. See [ROADMAP.md](ROADMAP.md) for details.

**It does not promise alpha. It does not promise you'll beat the
market. It promises 3 things: methodology you can verify, results
you can reproduce, and a process you can trust.**

---

## Honest disclosure

**We do not promise:**
- That any strategy will beat the market
- That you'll find alpha
- That backtests predict the future

**We promise:**
- The tools will identify strategies that "look good but are
  overfit"
- Comparisons between strategies are honest (no survival bias,
  no in-sample/out-of-sample leakage)
- Six months from now you can re-run the same code and get the
  same numbers

If you're looking for a tool that tells you your strategy is
amazing, this isn't it. If you're looking for a tool that tells
you the truth about your strategy — even when the truth is
uncomfortable — read on.

---

## The 6 v1.0 acceptance questions

Before trusting any backtest, alphaloop can answer these in
under 30 minutes:

1. **Overfit?** Has the strategy's Sharpe ratio survived
   Deflated Sharpe Ratio correction for the number of trials?
2. **Data sources consistent?** Does the same symbol give
   consistent prices across Yahoo vs AKShare (or whichever
   sources you use)?
3. **Out-of-sample valid?** Does walk-forward CV show positive
   Sharpe in held-out windows?
4. **Beats a random strategy?** Is your Sharpe significantly
   above block-shuffled baselines (max-drawdown test)?
5. **Beats passive buy-and-hold?** Does your strategy beat
   passive holding of the same instrument?
6. **Beats SPY buy-and-hold?** Does your strategy beat SPY
   over the same window? (The hardest benchmark. Most individual
   strategies fail this one.)

If any answer is "no", the strategy doesn't ship.

---

## Quick start

```bash
# Install (Python 3.11+)
git clone https://github.com/AlphaStrategyAI/alphaloop.git
cd alphaloop
pip install -e .

# Run the acceptance report on synthetic data
alphaloop report

# Or save to a file
alphaloop report --output my-report.md

# Run the 5-strategy comparison demo
python3 examples/comparison_demo.py

# Run the 6-question diagnostic demo
python3 examples/diagnostic_demo.py

# Launch the WebUI
streamlit run alphaloop/ui.py
```

---

## 5-strategy comparison (synthetic data)

The honest output of `examples/comparison_demo.py`:

```
Strategy                 Sharpe  vs Buy & Hold     vs SPY   vs Random     Max DD
--------------------------------------------------------------------------------
buy_and_hold              +0.43           fail       fail        PASS    -26.22%
rsi_momentum              -0.16           fail       fail        PASS    -35.89%
bollinger_meanrev         +0.79           PASS       fail        PASS     -7.82%
atr_breakout              -0.58           fail       fail        fail     -4.10%
obv_volume                +0.03           fail       fail        fail    -33.97%

Of 5 strategies tested, 0 beat SPY buy-and-hold.
This is on a synthetic random walk; real markets may differ.
The point of this demo is to show that the tools work — not
to declare a winner.
```

**Reading this table honestly**:
- `buy_and_hold` is the *same universe as the strategies*, not
  SPY. Of course it loses to SPY in this test setup — that's the
  point: random-walk universes don't match the real market.
- The 4 strategies mostly fail `vs_random` because on a random
  walk, there's nothing to extract. Real markets have non-random
  structure (which is why SPY exists and grows).
- The tool worked. It reported 4/5 strategies as FAIL on most
  benchmarks. That's the honest answer.

---

## What v1.0 does NOT do

These are explicit non-goals, deferred to v2.0:

- **ML models** (XGBoost, deep RL). The 10 alpha factors are
  classical; ML adds overfit risk that v1.0 deliberately avoids.
- **NLP factors** (sentiment from earnings calls / news).
- **100+ factors**. v1.0 ships 10; each is tested, documented,
  and known to work.
- **Live trading**. The Alpaca adapter is implemented but defaults
  to paper. Going live requires both `paper=False` AND
  `confirm_live=True`. Even then, v1.0 only exposes read-only API.
- **Web services, SaaS, paid plans**. v1.0 is local-only.

See [`docs/lessons/`](./docs/lessons/) for retrospectives on each
milestone and the failure patterns we hit and learned from.

---

## Architecture

```
alphaloop/
├── data/          # 4 data sources (Yahoo, AKShare, CCXT, OpenBB)
├── engineer/      # 10 alpha factors (pure functions: Series -> weights)
├── diagnostic/    # 6 tools: DSR, walk-forward CV, consistency, 3 benchmarks
├── live/          # Alpaca adapter (paper-by-default, hard-walled)
├── cli/           # `alphaloop` CLI (backtest, optimize, fetch, report)
└── ui.py          # Streamlit WebUI (single file)
```

Each subpackage is independently importable. Pure functions where
possible. Tests at every level.

---

## Running the tests

```bash
# All tests
python3 -m pytest tests/ -v

# Just the diagnostic package
python3 -m pytest tests/diagnostic/ -v

# Just the safety tests for the live trading adapter
python3 -m pytest tests/live/test_safety.py -v
```

**Current status**: 154 tests pass.

---

## Documentation

- [`docs/lessons/m1-retrospective.md`](./docs/lessons/m1-retrospective.md)
  — Failure patterns from M1 (diagnostic package)
- [`docs/lessons/m3-retrospective.md`](./docs/lessons/m3-retrospective.md)
  — Failure patterns from M3 (live trading)
- `src/alphaloop/live/README.md` — Hard wall design for live trading
- `examples/diagnostic_demo.py` — 6-question diagnostic walkthrough
- `examples/alpha_comparison_demo.py` — 10-factor vs buy-and-hold
- `examples/comparison_demo.py` — 5-strategy head-to-head

---

## License

MIT. See [`LICENSE`](./LICENSE).

---

## Acknowledgments

- Bailey & Lopez de Prado (2014) — Deflated Sharpe Ratio
- Jegadeesh & Titman (1993) — 12-1 momentum
- Bollinger (1992) — Bollinger Bands
- Wilder (1978) — RSI, ATR
- Parkinson (1980) — Historical volatility estimator

These references are implemented as plain Python (no proprietary
math) in [`src/alphaloop/diagnostic/`](./src/alphaloop/diagnostic/)
and [`src/alphaloop/engineer/`](./src/alphaloop/engineer/).