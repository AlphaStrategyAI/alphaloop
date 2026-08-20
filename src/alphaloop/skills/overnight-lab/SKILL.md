---
name: overnight-lab
description: >
  Formulate, preflight, submit, and poll alphaloop overnight research jobs.
  Interpret FOUND / NO_EVIDENCE / INCONCLUSIVE. Do not block overnight.
  Do not override hard gates. Export only FOUND with human approval.
---

# alphaloop overnight research lab

You are helping an independent quant use alphaloop as a **local-first overnight research lab**. It is not a trading bot, not a backtest library, and not a broker.

## Promise

Submit in one minute. Leave a local worker running overnight. In the morning, understand a trustworthy conclusion in five minutes. **Do not claim alpha.** A passing story or LLM judge is not evidence.

## Host constraint

The host must remain awake while a local worker is running. Closing the browser or terminal does not stop a job, but suspending or powering off the host stops computation. Disclose this during preflight. After a sleep/crash, resume from checkpoint with `alphaloop resume`.

## Workflow

1. Write a frozen `ResearchSpec` YAML: statement, economic logic, `signal_mechanism` (a constrained DSL kind such as `momentum_12_1`), comma-separated `market_scope` tickers, `market_profile` (`us-equity-daily` or `crypto-daily`), benchmark, hard gates, seed, time and cost budgets.
2. If the daemon is not up, run `alphaloop start --detach` (loopback Job API + packaged morning Web at `/`).
3. **Preview** with `alphaloop preview --spec PATH` (does not create a job). Then freeze with the morning page YAML box at `/` **or** `alphaloop submit --spec PATH`; both return `run_id` immediately. The packaged morning page can POST YAML to `/v1/jobs`, polls progress every two seconds, and cannot change hard gates.
4. **Poll** the morning page or `alphaloop status` (latest job) or `alphaloop status RUN_ID`. Parse JSON with `alphaloop status --json` or `alphaloop status RUN_ID --json`. Stop or resume the latest job with `alphaloop cancel` / `alphaloop resume`; pass `RUN_ID` for an explicit job. Do not block a chat, CLI, or MCP tool call for hours. There is no overnight MCP session.
5. Open the morning console at `http://127.0.0.1:8765/` or inspect artifacts under the run directory. `alphaloop replay` rewrites `report.md` from sealed artifacts for the latest job and prints the same five-minute verdict as `status`. Pass `RUN_ID` for an explicit job. Parse JSON with `alphaloop replay --json` or `alphaloop replay RUN_ID --json`. The morning **Replay report** control does the same rewrite without leaving the page. It does not re-run gates.

## Outcomes

Job status (`queued` / `running` / `completed` / `failed` / `cancelled`) is not the research conclusion. The conclusion is exactly one of:

- `FOUND` — every required hard gate is present and passed. Sealed evidence only.
- `NO_EVIDENCE` — evidence is complete and at least one hard gate failed.
- `INCONCLUSIVE` — evidence missing, corrupt, budget exhausted without a complete set, or the job failed/cancelled without a sealed `FOUND`.

Do not claim alpha after a failed gate. `NO_EVIDENCE` and `INCONCLUSIVE` are valid, successful product outcomes.

## Hard gates

Deterministic diagnostics own `FOUND`. You cannot override hard gates from the Web console, an agent narrative, or by editing `evidence/gates.json`. Never tell the user to PATCH gates or force `FOUND`.

Method repairs may continue only while evidence is incomplete and budget remains. Changing economic logic, `signal_mechanism`, market scope, benchmark, or the hard-gate set requires a **new spec** and **human approval**. Queue that idea; do not mutate the running job.

## Export

`alphaloop export CANDIDATE_ID --output strategy.asb` is allowed only for `FOUND`, only for a candidate in the trial ledger, and only after **human** confirmation. Omit `--run-id` to use the latest job; pass `--run-id RUN_ID` for an explicit job. A successful export prints `FOUND`, `Qualifying:`, `Exported:`, and `This export does not claim alpha or future profitability.` Parse JSON with `alphaloop export CANDIDATE_ID --output strategy.asb --json`. The `.asb` is YAML/DSL data. Do not add Python files. Do not send fills or telemetry back to alphaloop.

## Forbidden

- Do not keep an MCP tool call open overnight. MCP is not required.
- Do not execute arbitrary generated Python as the strategy.
- Do not connect to a broker or hold credentials in alphaloop.
- Do not promise that overnight search will find alpha.
