# alphaloop

Local-first overnight research lab for AI-native independent quants.

> Submit in one minute before bed. Leave a local worker running overnight.
> Understand a trustworthy conclusion in five minutes the next morning.

alphaloop does **not** promise alpha, future profitability, or that any
strategy will beat the market. It freezes a constrained hypothesis,
runs it against predeclared hard gates on your machine, and reports one
of three conclusions:

- `FOUND` — every required hard gate is present and passed
- `NO_EVIDENCE` — evidence is complete and at least one hard gate failed
- `INCONCLUSIVE` — data, budget, diagnostics, or a technical failure
  prevented a valid conclusion

Job status (`queued` / `running` / `completed` / `failed` / `cancelled`)
is not the research conclusion. `FOUND` comes only from sealed
`GateEvidence`. An LLM judge, a story, or the Web console cannot
override gates.

It is **not a trading bot**. Paper trading, live trading, brokers, and
promotion belong in the separate AlphaStrategy project.

## Quick start

```bash
pip install alphaloop
alphaloop start --detach
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Paste a research
spec (YAML) on the packaged morning page, or run
`alphaloop dataset PATH` (custom parquet or wide close-only CSV;
prints pasteable `dataset:` YAML; skip for the packaged
`ds_example`), then `alphaloop preview --spec spec.yaml` then
`alphaloop submit --spec spec.yaml`. Leave the host awake. Closing the
browser or terminal does not stop the job; suspending or powering off
the host does.

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
dataset:
  dataset_id: ds_example
  sha256: 03796e74d7eed2595bc882cd345ae7967b1622848a618e437e0847d7bc66bc55
```

The morning page shows the conclusion, sealed gate evidence (including
walk-forward `regime_stable` and median fold Sharpe when present), and
short help. It does not claim alpha.

```bash
alphaloop dataset prices.parquet
alphaloop preview --spec spec.yaml
alphaloop submit --spec spec.yaml
alphaloop status
alphaloop status RUN_ID
alphaloop status RUN_ID --json
alphaloop cancel
alphaloop cancel RUN_ID
alphaloop resume
alphaloop resume RUN_ID
alphaloop replay
alphaloop replay RUN_ID
```

## Honest disclosure

The host must remain awake while a local worker is running. alphaloop
does not promise that overnight search will find alpha, or that a
passing backtest predicts the future.

Methodology you can verify: Deflated Sharpe, walk-forward (mean, median,
and chronological half Sharpes), vs random, vs buy-and-hold, vs
benchmark. Missing datasets fail closed; they do not synthesize prices
or `FOUND`.

## Heritage CLI

`alphaloop loop`, `report`, `fetch`, `backtest`, `optimize`, and `judge`
remain for diagnostics and the v0.7 hybrid DAG. They are **not** the
first-release overnight path. The product path is `start` → optional
`dataset` → preview → submit → morning review → optional `.asb` export.

The Vite + React Quant Lab SPA under `webui/` is frozen heritage. The
product UI is the packaged static page served by `alphaloop start`.

## Next steps

- [CLI reference](cli.md) — overnight-lab commands first; `loop` is heritage.
- [WebUI](webui.md) — packaged morning page, then frozen SPA notes.
- [Product positioning](requirements/product-positioning-requirements.md) — locks.
- [Product design](requirements/product-design-v0_0_1.md) — feature map, screens, flows.
- [Overnight lab architecture](plans/overnight-research-lab-refactor.md).
- [GitHub repo](https://github.com/AlphaStrategyAI/alphaloop).
