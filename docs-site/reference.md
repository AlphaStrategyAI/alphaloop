# CLI reference

This is the full CLI reference for `alphaloop` v0.7.2. Run
`alphaloop --help` for the live version.

## Global usage

```
alphaloop [-h] {backtest,optimize,fetch,report,loop} ...
```

## `alphaloop backtest`

Run a single backtest against a config file.

```
alphaloop backtest --config CONFIG [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                              [--output DIR]
```

| Flag | Description |
|------|-------------|
| `--config, -c`  | **Required.** YAML or JSON config file. |
| `--start, -s`   | Start date (default: from config). |
| `--end, -e`     | End date (default: from config). |
| `--output, -o`  | Output directory (default: from config). |

## `alphaloop optimize`

Parameter sweep over a config.

```
alphaloop optimize --config CONFIG [--method grid|bayesian] [--max-eval N]
```

| Flag | Description |
|------|-------------|
| `--config, -c`     | **Required.** Config file. |
| `--method, -m`     | `grid` (default) or `bayesian`. |
| `--max-eval`       | Max evaluations (default: 100). |

## `alphaloop fetch`

Fetch data from a public source.

```
alphaloop fetch --symbol SYMBOL [--source yahoo|akshare|ccxt|openbb]
                          [--exchange NAME] [--period P]
                          [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                          [--output FILE]
```

| Flag | Description |
|------|-------------|
| `--symbol`      | Asset code (e.g. `AAPL`, `BTC/USDT`). |
| `--source`      | Data source (default `yahoo`). |
| `--exchange`    | CCXT exchange (default `okx`). |
| `--period`      | Shortcut period (`1d`, `5d`, `1mo`, …). |
| `--start`       | Start date. |
| `--end`         | End date. |
| `--output, -o`  | Output file (`.csv` or `.json`). |

## `alphaloop report`

Build the v1.0 acceptance report for a run.

```
alphaloop report --run-id RID [--data-dir DIR]
```

## `alphaloop loop`

The hybrid DAG loop. Subcommands: `run`, `replay`, `inspect`, `list`.

### `alphaloop loop run`

```
alphaloop loop run "<goal>" [--seed N] [--budget USD] [--timeout S]
                           [--target-dsr F] [--model NAME]
                           [--data-dir DIR] [--dry-run] [--no-launch]
```

| Flag | Description |
|------|-------------|
| `goal`          | **Required.** Research goal (e.g. `"find alpha with DSR > 1.0"`). |
| `--run-id`      | Explicit run_id (default: auto-generated). |
| `--seed`        | Random seed (default: time-derived). |
| `--budget`      | Cost cap in USD (default: 5.0). |
| `--timeout`     | Wall-clock cap in seconds (default: 21600 = 6 h). |
| `--target-dsr`  | Target DSR for gate A (default: 1.0). |
| `--model`       | LLM model name (default: `$LLM_MODEL`). |
| `--data-dir`    | `runs/` output root (default: `./runs`). |
| `--max-tasks`   | Hard cap on N2 planned tasks. |
| `--dry-run`     | Only run N1+N2; skip N3-N6. |
| `--git-repo-dir` | Git rev-parse HEAD capture root. |
| `--no-launch`   | **v0.7.2.** Do not auto-open the WebUI after the loop. |

> Default form: `alphaloop loop "<goal>"` is equivalent to
> `alphaloop loop run "<goal>"`.

### `alphaloop loop replay`

Re-emit the summary from a persisted run.

```
alphaloop loop replay --run-id RID [--data-dir DIR]
```

### `alphaloop loop inspect`

Print a human-readable summary of a run.

```
alphaloop loop inspect --run-id RID [--data-dir DIR]
```

### `alphaloop loop list`

List all run_ids under `--data-dir`.

```
alphaloop loop list [--data-dir DIR]
```

## v0.7.2 endpoints

The v0.7.2 FastAPI backend adds two share-link endpoints (used by the
WebUI share button):

```
POST /api/runs/<rid>/share?ttl_days=NN    → {token, url, expires_at, ...}
GET  /api/share/<token>                   → self-contained read-only HTML
```

The default TTL is 90 days (max 365). Share links are unlisted
(URL-only). The server binds to `127.0.0.1` — share links do not
expose your machine to the public internet.
