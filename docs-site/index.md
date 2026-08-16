# alphaloop

> **Open-source quantitative investment framework** — a hybrid DAG loop
> that plans, executes, diagnoses, and reports alpha strategies
> autonomously. Ships with a self-hosted WebUI for browsing top-5 picks
> and diagnostics.

---

## What is alphaloop?

alphaloop is the open-source port of the **openstrategy** framework that
an AlphaStrategyAI team uses internally for end-to-end quant research.
You give it a **goal** in natural language — "find alpha with DSR > 1.0
on liquid US equities" — and it runs a 6-node DAG (load → plan → execute
→ diagnose → aggregate → commit) that returns a ranked top-5 set of
strategies with full diagnostic reports.

It is **not** a black-box LLM.  It is a hybrid loop where the LLM
proposes strategies and judges qualitative factors, but every numeric
result is computed deterministically and every claim is backed by a
diagnostic check (Q1–Q7).

## Why use it?

- **End-to-end in one command.** `alphaloop loop "find momentum alpha"`
  runs the full DAG and writes a self-contained report under
  `runs/<rid>/`.
- **Self-hosted WebUI.** A `npm run dev` and a `uvicorn` later you have
  a dark "Quant Lab" SPA with 4 views (Top-5, Diagnostics, Replay,
  Strategy Detail), 8 Framer Motion animations, and a share-link button.
- **Reject the obvious frauds.** Every pick is gated through 7
  diagnostics (DSR, multiple-testing, autocorrelation, drawdown,
  turnover, factor crowding, cost sensitivity). A pick that fails any
  gate is flagged.
- **Reproducible.** Runs write a `manifest.yaml` with the goal, seed,
  git commit, LLM model, and data snapshot SHA-256. Replay regenerates
  the report from the same artifacts.

## Quick start

```bash
# 1. Install
pip install alphaloop

# 2. (Optional) one-time UI setup
cd $(python -c "import alphaloop, os; print(os.path.dirname(alphaloop.__file__))")
cd webui && npm install && cd ..

# 3. Run a loop (v0.7.2 automatically opens the WebUI when done)
alphaloop loop "find alpha with DSR > 1.0"

# 4. Or, run headless:
alphaloop loop --no-launch "find alpha with DSR > 1.0"
```

## What you get

After the loop finishes you will have:

```
runs/<run_id>/
├── manifest.yaml        # goal, seed, git_commit, llm_model, ...
├── top5.json            # machine-readable top-5 picks
├── results.parquet      # per-task backtest results
├── report.md            # human-readable narrative
├── progress.json        # N1–N6 timing per node
├── .share.json          # (v0.7.2) share tokens
└── .webui-port          # (v0.7.2) port the WebUI listened on
```

## Next steps

- [Getting started](getting-started.md) — install + first run.
- [CLI reference](reference.md) — every subcommand and flag.
- [WebUI](webui.md) — the 4 views, animations, and share-link UX.
