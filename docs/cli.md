# CLI reference

The full CLI reference for `alphaloop` v0.7.2.  Run `alphaloop --help`
for the live version (it's the source of truth — this page mirrors it).

## Global usage

```
alphaloop [-h] {backtest, optimize, fetch, report, loop, replay, webui, judge} ...
```

## `alphaloop report`

Build the v1.0-style diagnostic report for a single strategy.

```
alphaloop report --strategy NAME --start YYYY --end YYYY
                 [--data-dir DIR] [--output DIR] [--no-launch]
```

| Flag | Description |
|------|-------------|
| `--strategy`     | **Required.** Strategy id, e.g. `buy_hold`, `mom_12_1`, `meanrev_zscore`. |
| `--start`        | Start year (default: `2020`). |
| `--end`          | End year (default: current year − 1). |
| `--data-dir`     | Data snapshot root. |
| `--output, -o`   | Output directory (default: `runs/<rid>/`). |
| `--no-launch`    | Do not auto-open the WebUI after the report. |

The five-minute sanity check:

```bash
alphaloop report --strategy buy_hold --start 2020 --end 2025
```

## `alphaloop loop "<goal>"`

The autonomous hybrid DAG loop.  Default form (alias for `loop run`):

```
alphaloop loop "<goal>" [flags]
```

The DAG: **N1 load → N2 plan → N3 execute → N4 diagnose → N5 aggregate →
N6 commit**.  Termination gates run between nodes; a single hard fail
stops the loop and writes a sealed partial report.

| Flag | Description |
|------|-------------|
| `goal`           | **Required.** Research goal in natural language. |
| `--seed`         | Random seed (default: time-derived). |
| `--budget`       | Cost cap in USD (default `5.0`). |
| `--timeout`      | Wall-clock cap in seconds (default `21600` = 6 h). |
| `--target-dsr`   | Target DSR for gate A (default `1.0`). |
| `--model`        | LLM model name (default: `$LLM_MODEL`). |
| `--data-dir`     | `runs/` output root (default `./runs`). |
| `--max-tasks`    | Hard cap on N2 planned tasks. |
| `--dry-run`      | Only run N1 + N2; skip N3–N6. |
| `--no-launch`    | **v0.7.2.** Do not auto-open the WebUI after the loop. |
| `--git-repo-dir` | Git rev-parse HEAD capture root. |

## `alphaloop replay <run_id>`

Re-emit the summary from a persisted run.  Reads `runs/<rid>/` and
writes a fresh `report.md` **without** re-running any backtest.

```
alphaloop replay <run_id> [--data-dir DIR] [--output DIR]
```

Useful for:

- regenerating the report after a docs / diagnostics change,
- regenerating a share-link snapshot after a TTL bump,
- reproducing an internal-review narrative.

## `alphaloop webui`

Start the FastAPI backend + Vite dev server, then open the SPA in your
default browser.

```
alphaloop webui [--port N] [--host HOST] [--no-browser]
```

| Flag | Description |
|------|-------------|
| `--port, -p`    | Backend port (default `8765`). |
| `--host`        | Bind address (default `127.0.0.1` — never public). |
| `--no-browser`  | Skip the auto-open. |

The WebUI consumes the **most recent** run under `--data-dir` by
default.  Pass `--data-dir runs/<rid>` to pin it.

## `alphaloop judge --calibration`

Calibration sweep for the LLM judge.  Loads the v0.8 prompt registry,
runs a labeled calibration set, and reports accuracy + drift vs. the
last calibration.

```
alphaloop judge --calibration [--prompt-set NAME] [--reviewers N]
                                [--output DIR] [--compare-last]
```

Output is a `calibration_<ts>/` directory containing:

- `scores.csv` — long-form per-dimension scores,
- `metrics.json` — accuracy / drift / reviewer agreement,
- `report.md` — human-readable summary.

| Flag | Description |
|------|-------------|
| `--prompt-set`   | Prompt registry name (default `v0.8-default`). |
| `--reviewers`    | Run N independent reviewers per label (default `3`). |
| `--compare-last` | Diff vs. the previous calibration run. |
| `--output, -o`   | Output directory (default `calibration/<ts>/`). |

## Common flags

A few flags appear across most subcommands:

| Flag | Description |
|------|-------------|
| `--data-dir DIR` | Root for `runs/`, `data/`, `calibration/`. |
| `--output, -o`   | Per-command output override. |
| `--no-launch`    | Skip the v0.7.2 auto-WebUI launch. |
| `--seed N`       | Deterministic seed for replays. |
| `--quiet`        | Suppress progress logs (JSON-only). |
| `--verbose, -v`  | Verbose logging. |
| `--help, -h`     | Per-subcommand help. |

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `LLM_MODEL`        | `gpt-4o-mini` | Used by the planner + judge. |
| `OPENAI_API_KEY`   | —             | Required for the LLM calls. |
| `ALPHALOOP_DATA`   | `./data`      | Default data snapshot root. |
| `ALPHALOOP_RUNS`   | `./runs`      | Default runs output root. |
| `NO_COLOR`         | unset         | Disables the colored progress bars. |
