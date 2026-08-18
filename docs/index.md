# alphaloop

> **Open-source quantitative investment framework** — a hybrid DAG loop
> that plans, executes, diagnoses, and reports alpha strategies
> autonomously.

---

## One-line

**alphaloop = a research goal in natural language → ranked top-5
strategies with full diagnostic reports, reproducible and self-hosted.**

You give it a goal (e.g. *"find alpha with DSR > 1.0 on liquid US
equities"*) and it runs a 6-node DAG (`load → plan → execute →
diagnose → aggregate → commit`) that returns a sealed run directory
with the top-5 picks, a human-readable `report.md`, a `manifest.yaml`,
and (since v0.7.2) an auto-launched WebUI.

## Install

```bash
pip install alphaloop
```

Verify:

```bash
alphaloop --help
# → {backtest, optimize, fetch, report, loop, replay, webui, judge, ...}
```

For the optional WebUI (v0.7.2 ships a Vite + React SPA):

```bash
# only needed once, after pip install
cd $(python -c "import alphaloop, os; print(os.path.dirname(alphaloop.__file__))")
cd webui && npm install && cd ..
```

## 5-minute quickstart

The fastest path to a real result:

```bash
alphaloop report --strategy buy_hold --start 2020 --end 2025
```

That runs the **single-strategy diagnostic report** path: one strategy,
six diagnostics, one `report.md`. Useful for sanity-checking the
install and calibrating your risk budget without spinning up the full
DAG.

For the full autonomous loop:

```bash
alphaloop loop "find alpha with DSR > 1.0"
# → runs/<rid>/report.md, runs/<rid>/top5.json, ...
# v0.7.2: WebUI auto-opens in your default browser
# Want headless?  alphaloop loop --no-launch "<goal>"
```

## The six diagnostics

Every candidate is gated through these six diagnostics before it can
land in the top-5. A pick that fails any one is **flagged** in
`report.md` and excluded from the share link.

| # | Diagnostic | What it catches |
|---|------------|------------------|
| Q1 | **DSR** (Deflated Sharpe Ratio) | Inflated Sharpe from multiple testing |
| Q2 | **Multiple-testing correction** | Bonferroni / Holm on the candidate pool |
| Q3 | **Autocorrelation** | Stale signals that look profitable in backtest only |
| Q4 | **Drawdown** | Worst peak-to-trough vs. your risk budget |
| Q5 | **Turnover** | Strategies that would erode returns in live trading |
| Q6 | **Cost sensitivity** | Sensitivity to slippage, fees, borrow |

(The full set extends to 7 in `docs/design/` — the 7th, *factor
crowding*, is optional and off by default.)

## What you get

After a full `alphaloop loop`:

```
runs/<run_id>/
├── manifest.yaml        # goal, seed, git_commit, llm_model, data_sha256
├── top5.json            # machine-readable top-5 picks
├── results.parquet      # per-task backtest results
├── report.md            # human-readable narrative + Q1–Q6 flags
├── progress.json        # N1–N6 timing per node
├── .share.json          # (v0.7.2) share tokens
└── .webui-port          # (v0.7.2) port the WebUI listened on
```

## Next steps

- 📘 [CLI reference](cli.md) — every subcommand and flag.
- 🖥  [WebUI](webui.md) — 4 views, 8 animations, the *Quant Lab*
  visual design, keyboard shortcuts.
- 📐 [Design: hybrid DAG](design/v07-hybrid-loop.md) · [LLM judge](design/v06-llm-judge.md) · [WebUI](design/v071-webui.md) — architecture.
- 🧪 [Requirements: product positioning](requirements/product-positioning-requirements.md) · [v0.7.2](requirements/v072-requirements.md) · [v0.8](requirements/v08-requirements.md) — specifications.
- 🔗 [GitHub repo](https://github.com/AlphaStrategyAI/alphaloop) —
  source, issues, releases.
