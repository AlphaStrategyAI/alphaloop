# alphaloop

Local-first overnight research lab for AI-native independent quants.

> Submit in one minute before bed. Leave a local worker running overnight.
> Understand a trustworthy conclusion in five minutes the next morning.

alphaloop does **not** promise alpha, future profitability, or that any
strategy will beat the market. It runs a frozen hypothesis against
predeclared hard gates and reports one of three conclusions:

- `FOUND` — every required hard gate is present and passed
- `NO_EVIDENCE` — evidence is complete and at least one hard gate failed
- `INCONCLUSIVE` — data, budget, diagnostics, or a technical failure
  prevented a valid conclusion

Job status (`queued` / `running` / `completed` / `failed` / `cancelled`)
is not the research conclusion. `FOUND` comes only from sealed
`GateEvidence`. An LLM judge, a story, or a Web console cannot override
gates.

It is **not a trading bot**. Paper trading, live trading, brokers, and
promotion belong in the separate AlphaStrategy project. alphaloop can
export a `FOUND` candidate as an immutable YAML-only `.asb` bundle after
human confirmation.

---

## Honest disclosure

**We do not promise**

- that overnight search will find alpha
- that a passing backtest predicts the future
- that the host can sleep while a job is running

**We do promise**

- methodology you can verify (Deflated Sharpe, walk-forward, vs random,
  vs buy-and-hold, vs benchmark)
- results you can reproduce from a content-addressed dataset snapshot
- a process that fails closed instead of inventing prices or `FOUND`

The host must remain awake while a local worker is running. Closing the
browser or terminal does not stop a job, but suspending or powering off
the host stops computation. After a crash or sleep, resume from
checkpoint with `alphaloop resume`.

---

## Quick start

Python 3.9+. Install the package, start the local control plane, paste a
hypothesis, and leave the machine awake.

```bash
git clone https://github.com/AlphaStrategyAI/alphaloop.git
cd alphaloop
pip install -e ".[dev]"

alphaloop start --detach
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Paste YAML into
the home page (or use `alphaloop submit --spec spec.yaml`). The page
polls every two seconds and cannot change hard gates.

```yaml
statement: 12-1 momentum works in US large caps net of costs
economic_logic: past winners continue
signal_mechanism: momentum_12_1
market_scope: AAPL, MSFT
market_profile: us-equity-daily
benchmark: SPY
hard_gates: [dsr, walk_forward, vs_benchmark]
seed: 7
time_budget_s: 3600
cost_budget_usd: 5.0
```

`signal_mechanism` must be a constrained DSL kind (`momentum_12_1`,
`rsi`, `macd`, `roc`, `bollinger_zscore`, `ohlr_4_pct`, `pairs_spread`,
`atr_breakout`). `parkinson_hist_vol` is a volatility feature, not a
directional signal. `obv_slope` needs volume; first-release snapshots
are close-only. Markets `us-equity-daily` and `crypto-daily` are
independent.

If the spec declares a `dataset`, the parquet must exist under
`datasets/<id>/prices.parquet` and match the recorded SHA-256. Missing
or mismatched snapshots do not synthesize prices.

```bash
alphaloop preview --spec spec.yaml   # review grid; does not create a job
alphaloop submit --spec spec.yaml    # freeze after preview
alphaloop status                     # latest job five-minute verdict
alphaloop status RUN_ID              # five-minute verdict for one run
alphaloop status RUN_ID --json       # full morning_view payload for agents
alphaloop cancel                     # latest job
alphaloop cancel RUN_ID
alphaloop resume                     # latest job after a crash or host sleep
alphaloop resume RUN_ID
alphaloop replay                     # latest job; rewrite report.md
alphaloop replay RUN_ID              # rewrite report.md; print the five-minute verdict
alphaloop export CANDIDATE_ID --output strategy.asb
```

Export is allowed only for `FOUND`, only after a human confirms, and the
archive contains no Python.

---

## What this repository is

| Layer | Role |
| --- | --- |
| `alphaloop start` | Loopback Job API + supervisor + packaged morning Web |
| `alphaloop.protocol` | Constrained DSL, lagged strategy returns, hard gates, stop rules |
| `alphaloop.runtime` | Durable jobs, checkpoints, dataset cache, artifacts |
| `alphaloop.diagnostic` | Trust layer: DSR, walk-forward, consistency, three benchmarks |
| `alphaloop.engineer` | Classical factors consumed by the DSL |
| `alphaloop.webui.static` | Morning console (review, YAML submit, progress) |
| `alphaloop.live` | Frozen read-only Alpaca adapter. Not the overnight path. |

`alphaloop.protocol` does not import `live`, `webui`, or `runtime`.

CLI utilities `report`, `fetch`, `backtest`, `optimize`, `loop`, and
`judge` remain for diagnostics and heritage workflows. The overnight
product path is `start` → submit → morning review → optional `.asb`
export.

---

## Tests

```bash
python3 -m pytest -m "not integration and not llm and not e2e" --ignore=tests/integration

# Morning console e2e (real daemon + Chromium)
pip install -e ".[e2e]"
python3 -m playwright install chromium
python3 -m pytest -m e2e
```

Live data, soak, five-minute usability, and AlphaStrategy consumer
import tests are not this repository's CI.

---

## Documentation

- [`docs/requirements/product-positioning-requirements.md`](./docs/requirements/product-positioning-requirements.md) — product locks
- [`docs/cli.md`](./docs/cli.md) — CLI reference
- [`docs/plans/overnight-research-lab-refactor.md`](./docs/plans/overnight-research-lab-refactor.md) — architecture
- [`src/alphaloop/skills/overnight-lab/SKILL.md`](./src/alphaloop/skills/overnight-lab/SKILL.md) — agent skill
- [`src/alphaloop/live/README.md`](./src/alphaloop/live/README.md) — frozen live-adapter wall

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

These references are implemented as plain Python in
[`src/alphaloop/diagnostic/`](./src/alphaloop/diagnostic/) and
[`src/alphaloop/engineer/`](./src/alphaloop/engineer/).
