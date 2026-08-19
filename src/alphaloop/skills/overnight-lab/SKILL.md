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
3. Submit with `alphaloop submit --spec PATH`. It returns `run_id` immediately.
4. **Poll** `alphaloop status RUN_ID`. Do not block a chat, CLI, or MCP tool call for hours. There is no overnight MCP session.
5. Open the morning console at `http://127.0.0.1:8765/` or inspect artifacts under the run directory.

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

`alphaloop export CANDIDATE_ID --run-id RUN_ID --output strategy.asb` is allowed only for `FOUND`, only for a candidate in the trial ledger, and only after **human** confirmation. The `.asb` is YAML/DSL data. Do not add Python files. Do not send fills or telemetry back to alphaloop.

## Forbidden

- Do not keep an MCP tool call open overnight. MCP is not required.
- Do not execute arbitrary generated Python as the strategy.
- Do not connect to a broker or hold credentials in alphaloop.
- Do not promise that overnight search will find alpha.
