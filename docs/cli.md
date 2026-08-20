# CLI reference

Overnight-lab commands are `start`, `submit`, `preview`, `dataset`, `status`, `cancel`,
`resume`, `replay`, `export`, and `soak`. Run `alphaloop --help` for the live
parser (it is the source of truth — this page mirrors it).

`alphaloop loop` is **heritage** v0.7 hybrid DAG. It is not the
overnight research lab. Do not treat it as a command that finds alpha.

## Global usage

```
alphaloop [-h] {backtest, optimize, fetch, report, export, start, submit, preview, dataset, status, cancel, resume, soak, loop, replay, webui, judge} ...
```

## `alphaloop start`

Start the local alphaloop daemon (Job API + supervisor + packaged morning
Web console).  Binds to loopback by default; the CLI and browser can exit
without stopping jobs.

Open `http://127.0.0.1:8765/` for the morning console.  Paste YAML on
the home page to POST to `/v1/jobs`, or use `alphaloop submit`; the page
polls progress every two seconds.  The home page leads with `FOUND` /
`NO_EVIDENCE` / `INCONCLUSIVE`.  The console cannot override hard gates.

```
alphaloop start [--data-dir DIR] [--host HOST] [--port PORT] [--detach]
```

| Flag | Description |
|------|-------------|
| `--data-dir` | Runs output root (default: `./runs`). |
| `--host`     | Bind address (default: `127.0.0.1`). |
| `--port`     | Listen port (default: `8765`). |
| `--detach`   | Spawn the daemon in the background and print host/port/pid. |

Without `--detach`, the process stays in the foreground until you stop it.

## `alphaloop submit`

Submit a frozen `ResearchSpec` YAML to the daemon.  Returns `run_id`
immediately; the job keeps running after the CLI exits.

```
alphaloop submit --spec PATH [--data-dir DIR]
```

| Flag | Description |
|------|-------------|
| `--spec`     | **Required.** Path to a `ResearchSpec` YAML file. |
| `--data-dir` | Runs output root (default: `./runs`). |

On success prints `run_id` and the host-constraint disclosure.  If the
daemon is not running, the command fails with a hint to run
`alphaloop start`.

## `alphaloop preview`

Review the compiled protocol **without** creating a job. Leads with
`planned_n_trials`, then `spec_id`, statement, signal, hard gates, seed,
time and cost budgets, the method grid, and the host constraint. Does not
claim alpha.

```
alphaloop preview --spec PATH [--data-dir DIR] [--json]
```

| Flag | Description |
|------|-------------|
| `--spec`     | **Required.** Path to a `ResearchSpec` YAML file. |
| `--data-dir` | Runs output root (default: `./runs`). |
| `--json`     | Print the preview payload as JSON. |

Exit 0 only when preflight is `ok`. Missing dataset or other preflight
errors exit 2 and still create no job. When `ok`, the last line is
`Freeze with alphaloop submit --spec PATH`.

## `alphaloop dataset`

Cache a local parquet file or a wide close-only CSV into
`{data-dir}/datasets/<dataset_id>/prices.parquet` using the same hash
identity as the morning console picker. CSV columns are asset ids; the
first column is the date index. Per-symbol OHLCV (open / high / low /
close) is rejected. Does **not** create a job and does not require the
daemon.

```
alphaloop dataset PATH [--data-dir DIR] [--json]
```

| Flag | Description |
|------|-------------|
| `PATH`       | **Required.** Local parquet or wide close-only CSV. |
| `--data-dir` | Runs output root (default: `./runs`). |
| `--json`     | Print `{cached_path, dataset_id, sha256}` as JSON. |

Default stdout is pasteable `dataset:` YAML (`dataset_id` / `sha256`),
then `Cached:`, then `This cache does not claim alpha or future profitability.`
`--json` is for agents. Missing or invalid files exit 2 on stderr.
The command does not claim alpha.

## `alphaloop status`

Show the five-minute morning verdict for a research job.

```
alphaloop status [RUN_ID] [--data-dir DIR] [--json]
```

With no `RUN_ID`, prints the **latest** job (newest `created_at`),
prefixed with `run_id:`. If there is no job yet, prints the locked
empty cue (preview, then freeze; does not claim alpha).

With a `RUN_ID`, default stdout is the conclusion cluster: outcome
token, locked Help gloss, primary evidence, stop reason, optional
next-run and qualifying lines, job status, and the locked no-alpha
sentence. It is not a JSON object and does not claim alpha.

`--json` prints the full `morning_view` payload (`json.dumps`, sorted
keys) for that job, or for the latest job when `RUN_ID` is omitted.
An empty store prints `{"jobs": []}`. Job status is not the research
conclusion.

## `alphaloop cancel`

Request cancellation of a running job.

```
alphaloop cancel [RUN_ID] [--data-dir DIR] [--json]
```

With no `RUN_ID`, cancels the **latest** job (newest `created_at`) and
prefixes human stdout with `run_id:`. If there is no job yet, stderr is
`error: no overnight job yet` and the command exits 2 (does not claim
alpha). Daemon-unavailable stays the start hint.

With a `RUN_ID`, default stdout is the five-minute verdict cluster (same
as `alphaloop status RUN_ID`) and does not prefix `run_id:`. `--json`
prints the full `morning_view` payload. Cancel before a sealed `FOUND`
is `INCONCLUSIVE`. A sealed `FOUND` stays `FOUND`.

## `alphaloop resume`

Resume a job from its last checkpoint after a supervisor restart or
host wake.

```
alphaloop resume [RUN_ID] [--data-dir DIR] [--json]
```

With no `RUN_ID`, resumes the **latest** job and prefixes human stdout
with `run_id:`. Empty store and daemon-unavailable match `cancel`.

With a `RUN_ID`, default stdout is the five-minute verdict cluster and
does not prefix `run_id:`. `--json` prints the full `morning_view`
payload. Job status is not the research conclusion.

## `alphaloop export`

Export a sealed `FOUND` candidate as an immutable `.asb` zip.  YAML/DSL
is canonical; the archive contains no Python files.  Human-triggered
only.

```
alphaloop export CANDIDATE_ID [--run-id RUN_ID] [--data-dir DIR] --output PATH [--json]
```

| Flag | Description |
|------|-------------|
| `CANDIDATE_ID` | Trial-ledger `trial_id` of the sealed candidate. |
| `--run-id`     | Job id returned by `submit`. Omit to use the latest job. |
| `--data-dir`   | Runs output root (default: `./runs`). |
| `--output, -o` | **Required.** Destination `.asb` path. |
| `--json`       | Print `{candidate_id, exported_path, research_outcome}` as JSON. |

After a successful write, default stdout is a four-line receipt: `FOUND`,
`Qualifying: {candidate_id}`, `Exported: {path}`, and
`This export does not claim alpha or future profitability.`
`--json` is for agents. Failures stay on stderr and exit 2.
Non-`FOUND` jobs and unknown ledger ids exit 2. The command does not
claim alpha.

## `alphaloop soak`

Print the first-release overnight soak and five-minute review checklist.
Does **not** start workers, submit jobs, or compute a 95% pass rate.
This is a release-process aid, not CI.

```
alphaloop soak [--emit-plan]
```

The text includes the locked host constraint, two independent profiles
(`us-equity-daily`, `crypto-daily`), the three research outcomes, and
`kill -9` resume notes. It does not claim alpha.

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

## `alphaloop loop` (heritage v0.7 DAG)

Heritage hybrid DAG. Not the overnight-lab path. Use `alphaloop start`
and `alphaloop submit` for first-release research jobs.

Default form (alias for `loop run`):

```
alphaloop loop "<goal>" [flags]
```

The DAG is **N1 load → N2 plan → N3 execute → N4 diagnose → N5 aggregate →
N6 commit**. Termination gates run between nodes; a single hard fail
stops the loop and writes a sealed partial report. This path does not
promise alpha.

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
| `--no-launch`    | Do not auto-open the heritage WebUI after the loop. |
| `--git-repo-dir` | Git rev-parse HEAD capture root. |

## `alphaloop fetch` (heritage)

Heritage per-symbol OHLCV download. It is **not** the overnight-lab
snapshot path. Cache parquet or a wide close-only CSV with
`alphaloop dataset`. Fetch CSV is OHLCV and dataset ingest rejects it.
This command does not claim alpha.

## `alphaloop replay`

Rewrite `report.md` from sealed `gates.json` **without** re-running
gates or requiring the daemon. The morning console **Replay report**
control uses the same rewrite. Default stdout is the same five-minute
verdict as `status RUN_ID` (outcome token first). `--json` prints the
artifact view for agents.

```
alphaloop replay [RUN_ID] [--data-dir DIR] [--json]
```

With no `RUN_ID`, replays the **latest** job (newest `created_at`) and
prefixes human stdout with `run_id:`. `--json` includes `run_id` in the
artifact view. If there is no job yet, stderr is
`error: no overnight job yet` and the command exits 2 (does not claim
alpha).

With a `RUN_ID`, default stdout is the five-minute verdict cluster and
does not prefix `run_id:`.

Useful for:

- regenerating the report after a docs / diagnostics change,
- reading the morning cluster after rewriting `report.md`.

This command does not claim alpha or future profitability.

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
