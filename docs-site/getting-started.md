# Getting started

This guide walks through installing alphaloop, running your first
loop, and exploring the WebUI. Total time: **~10 minutes** on a
laptop with Python 3.11 and Node 20+.

## Prerequisites

- Python **3.11+** (3.12 also works)
- Node.js **20+** (for the WebUI only — not required for the CLI or
  the headless loop)
- ~500 MB free disk for the venv + `node_modules/`

## 1. Install

```bash
# From PyPI
pip install alphaloop

# Or from source (recommended for development)
git clone https://github.com/AlphaStrategyAI/alphaloop.git
cd alphaloop
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify the install:

```bash
alphaloop --help
```

You should see the subcommands: `backtest`, `optimize`, `fetch`,
`report`, `loop`.

## 2. (Optional) Install the WebUI dependencies

```bash
cd webui
npm install
cd ..
```

> This step is optional. The CLI works without Node — only the WebUI
> needs Node. v0.7.2 will skip the WebUI if you pass `--no-launch`.

## 3. Run your first loop

```bash
alphaloop loop "find alpha with DSR > 1.0"
```

What's happening:

1. **N1 — Load data.** A small synthetic snapshot is materialized
   (the demo path). In production, plug in your own data source via
   `--data-dir`.
2. **N2 — Plan.** The LLM (or the offline planner) proposes a list of
   4–16 strategy candidates.
3. **N3 — Execute.** Each candidate is backtested in a multiprocessing
   pool.
4. **N4 — Diagnose.** Each result is scored through 7 diagnostics.
5. **N5 — Aggregate.** The top-5 are written to `top5.json` and
   `report.md`.
6. **N6 — Commit.** A `manifest.yaml` is sealed with the goal, seed,
   model, git commit, and data snapshot hash.

When the loop finishes, **v0.7.2 auto-launches the WebUI** in your
default browser. To disable:

```bash
alphaloop loop --no-launch "find alpha with DSR > 1.0"
```

## 4. Explore the WebUI

The WebUI has 4 views:

| View | URL | What it shows |
|------|-----|---------------|
| Top-5            | `/`                  | The 5 picks + share button |
| Run diagnostics  | `/run/:rid`          | Q1–Q7 radar + manifest |
| Replay DAG       | `/replay/:rid`       | 6-node DAG + per-node timing |
| Strategy detail  | `/strategy/:sid`     | Equity curve + per-metric breakdown |

### Keyboard shortcuts

Press `?` for the in-app help. The shortcuts:

| Key | Action |
|-----|--------|
| `1` | Top-5 view |
| `2` | Run diagnostics |
| `3` | Replay DAG |
| `4` | Strategy detail |
| `r` | Rerun (with confirm) |
| `?` | Toggle help |
| `Esc` | Close any modal |

### Dark / light theme

Click the 🌙/☀ button in the top-right. The choice is remembered
across visits via `localStorage["alphaloop.theme"]`.

## 5. Share a result

Click the **🔗 Share** button on the Top-5 view. A URL is copied to
your clipboard. Anyone who opens the URL sees the same top-5 +
diagnostics (read-only). Default TTL: 90 days.

## 6. Where to go next

- Run `alphaloop loop --help` to see every flag.
- Read the [CLI reference](reference.md) for the full subcommand list.
- Read the [WebUI docs](webui.md) for the 8 animations and the
  visual design system.
- Tweak the 7 diagnostics in `src/alphaloop/diagnostic/` to fit your
  own risk budget.
