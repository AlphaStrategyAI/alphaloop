---
title: "alphaloop — Product Positioning Requirements (PRD)"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-18"
supersedes: "none — first product-positioning requirements document"
---

# alphaloop Product Positioning Requirements

**Date:** 2026-08-18
**Status:** Draft for written review
**Scope:** Product positioning and target architecture

## 1. Executive summary

alphaloop is a **local-first overnight research lab for AI-native
independent quantitative researchers**. A user submits a constrained
investment hypothesis before going to sleep. alphaloop runs a durable,
evidence-driven research process on the user's own machine and presents
one of three conclusions the next morning:

- `FOUND`: at least one candidate passed every predeclared hard gate.
- `NO_EVIDENCE`: the research completed, but the evidence did not support
  the frozen hypothesis.
- `INCONCLUSIVE`: data, budget, diagnostics, or technical failures
  prevented a valid conclusion.

The product promise is:

> Submit in one minute before bed; run reliably overnight; understand a
> trustworthy conclusion in five minutes the next morning.

alphaloop does not promise alpha or future profitability. Its value is
making agent-assisted strategy research reproducible, auditable, and
resistant to automated p-hacking.

The product uses a Web console as its primary long-running-task
experience, a durable Job API as its architectural boundary, and local
workers as its default execution environment. CLI and Agent Skills are
local entry points. MCP may later expose short asynchronous job-control
operations, but it is not the runtime for a multi-hour tool call.

When a candidate passes all gates, alphaloop can export an immutable
**Strategy Candidate Bundle** for the separate AlphaStrategy project.
AlphaStrategy alone owns paper trading, live trading, broker integration,
account risk, and promotion decisions.

## 2. Current context

The repository currently contains three partially overlapping stories:

1. The OpenStrategy heritage: honest quantitative diagnostics that reject
   overfit strategies.
2. The alphaloop direction: a natural-language-driven autonomous research
   DAG.
3. The Quant Lab WebUI: a human interface for inspecting and sharing
   results.

The target positioning unifies these stories:

- Honest diagnostics are the trust layer and primary differentiator.
- The loop automates research without automating away scientific
  discipline.
- The WebUI is the human control and review surface for long-running jobs.

As of 2026-08-18, the public AlphaStrategy repository does not yet define a
specialized execution architecture or a strategy import contract. It is
still based on the older OpenStrategy code and a read-only broker adapter.
The bundle contract in this design is therefore a new boundary that both
projects must implement independently.

This document defines the target product. Existing version metadata,
packaging, docs, CLI behavior, and WebUI behavior must be reconciled
against it in later implementation projects.

## 3. Positioning

### 3.1 Category

**Local-first agentic quantitative research lab.**

alphaloop is not positioned as:

- an AI trading bot;
- a signal-selling product;
- another general-purpose backtesting library;
- a broker or execution system;
- a guarantee of market outperformance.

### 3.2 Target user

The first user is an AI-native independent quantitative researcher:

- comfortable with Python, Git, and a terminal;
- already using a coding agent to design or test strategies;
- running experiments that take hours or overnight;
- concerned about overfitting, leakage, and irreproducible results;
- unwilling to upload strategy code or datasets to a third-party SaaS by
  default;
- lacking a dedicated platform engineering team.

The first release serves one person running research on one machine. It
does not include team permissions, collaborative approval workflows, or
institutional platform integration.

### 3.3 Primary job

The user submits an economically meaningful hypothesis, not a request to
"find something profitable." For example:

> In low-volatility regimes, does 12-1 momentum produce net-of-cost,
> out-of-sample excess returns in US large-cap equities?

alphaloop freezes the economic hypothesis, turns it into a structured
research protocol, generates candidates through a constrained strategy
DSL, runs deterministic experiments, diagnoses the evidence, and stops
when additional computation can no longer increase confidence.

### 3.4 Success criteria

The first release succeeds when:

- at least 95% of jobs in the release's fixed overnight benchmark suite
  complete without operator intervention on every platform that release
  explicitly supports;
- a crashed daemon or worker can resume from the latest complete
  checkpoint;
- every conclusion is reproducible from its frozen plan, data snapshot,
  engine version, seed, and trial ledger;
- no missing diagnostic or incomplete evidence set can produce `FOUND`;
- a user can identify the conclusion, primary evidence, and stop reason
  from the morning home page in five minutes.

The percentage of runs that find alpha is explicitly not a product
success metric.

## 4. Core experience

### 4.1 Before bed

1. The user opens the local Web console or submits through the CLI.
2. The user states a hypothesis and chooses a market profile.
3. alphaloop preflights the data, benchmark, costs, search space, disk,
   compute budget, and time budget.
4. The user reviews and freezes the research protocol.
5. Submission returns a `run_id` immediately.

The host must remain awake while a local worker is running. Closing the
browser or terminal does not stop a job, but suspending or powering off
the host stops computation. The product must disclose this during
preflight and resume from a checkpoint after an interruption. Cloud
workers are the future option for users who cannot leave a host awake.

### 4.2 Overnight

1. A local supervisor keeps the job alive independently of the browser
   and submitting shell.
2. Workers generate only DSL-constrained candidates.
3. Deterministic engines run backtests and evidence checks.
4. A trial ledger records every experiment and methodological revision.
5. The loop continues while a revision can add credible evidence and the
   time/cost budget remains.
6. Checkpoints make the job recoverable.

### 4.3 The next morning

The home page leads with one conclusion:

- `FOUND`
- `NO_EVIDENCE`
- `INCONCLUSIVE`

It then presents:

1. qualifying candidates and supporting evidence;
2. the candidate elimination funnel and dominant failure reasons;
3. methodological revisions made during the run;
4. evidence-backed suggestions for a future hypothesis.

A new economic hypothesis is never executed silently during the same
overnight run. It is queued for human review.

## 5. Architecture

```text
Web / CLI / Skill / optional thin MCP
                  |
                  v
          Local Job API
                  |
                  v
        Worker Supervisor
                  |
                  v
          Research Workers
                  |
                  v
   Local State DB + Artifact Store
```

The Job API, run state machine, worker protocol, and artifact schema are
stable boundaries. A future user-owned cloud worker must implement these
same contracts. Local execution remains the default.

### 5.1 Local Control Plane

- Starts with `alphaloop start`.
- Hosts the Job API and packaged static Web application.
- Creates, cancels, resumes, and queries jobs.
- Enforces budgets and the run state machine.
- Tracks worker heartbeats and recovery attempts.
- Binds locally by default and does not expose research data to the
  network without explicit configuration.

### 5.2 Web Console

- Is the primary product interface.
- Ships as built static assets; end users do not install Node.
- Supports preflight, submission, progress, evidence inspection, and
  morning review.
- Does not execute research and cannot override evidence gates.

### 5.3 Worker Supervisor

- Runs independently of the browser and submitting shell.
- Starts and monitors local research workers.
- Isolates candidate failures.
- Restarts recoverable work from durable checkpoints.
- Converts unrecoverable technical failure into a failed job with an
  inconclusive research outcome.

### 5.4 Research Engine

- Compiles a frozen protocol into the constrained DSL.
- Generates and evaluates candidates.
- Runs quantitative diagnostics.
- Applies epistemic stopping rules.
- Cannot execute arbitrary agent-generated Python.

### 5.5 Market Profiles

The first release supports two independent profiles:

- `us-equity-daily`
- `crypto-daily`

They share the engine contract but separately define:

- trading calendar;
- dataset requirements;
- benchmark;
- transaction-cost assumptions;
- liquidity rules;
- survivorship and availability checks.

Candidates from the two profiles are not placed in one default ranking.
Cross-market analysis is a portability test, not a direct comparison of
absolute Sharpe ratios.

### 5.6 Persistence

A lightweight local transactional database stores job indexes, states,
leases, and heartbeats. The filesystem stores immutable or append-only
research artifacts. The exact database engine is selected in the local
runtime implementation spec; the boundary in this design is its
transactional behavior, not a vendor.

## 6. Research protocol

### 6.1 Immutable hypothesis

The following are frozen when a run starts:

- economic logic;
- signal mechanism;
- market scope;
- benchmark;
- success criteria.

The loop may repair experimental methodology, including:

- incomplete or invalid data;
- ambiguous implementation details;
- missing cost assumptions;
- insufficient but relevant parameter coverage;
- recoverable experiment implementation errors.

Each repair is recorded and included in the multiple-testing accounting.

Changing the economic logic, signal mechanism, market scope, or success
metric creates a new hypothesis. The agent may recommend it, but the new
hypothesis requires human approval in a future run.

### 6.2 Epistemic stopping

The loop may continue until its time or cost budget is exhausted, but
only when the next experiment can credibly add evidence.

The following do not justify further parameter search:

- negative out-of-sample performance;
- failure after transaction costs;
- failure of DSR or another predeclared gate;
- instability across required regimes;
- improvement possible only by expanding an already failed parameter
  search.

This prevents "continue until profitable" behavior.

### 6.3 Job status versus research outcome

Job status and research conclusion are separate:

| Job status | Meaning |
| --- | --- |
| `queued` | Accepted but not executing |
| `running` | Active or recovering |
| `completed` | Research process ended normally |
| `failed` | Unrecoverable technical failure |
| `cancelled` | Explicit user cancellation |

| Research outcome | Meaning |
| --- | --- |
| `FOUND` | At least one candidate passed every frozen hard gate |
| `NO_EVIDENCE` | The completed evidence did not support the hypothesis |
| `INCONCLUSIVE` | Available evidence cannot support a valid judgment |

A completed job may have any of the three research outcomes. A failed or
cancelled job cannot claim `FOUND`; unless a previously sealed result
already exists, it is inconclusive.

## 7. Run artifacts

```text
runs/<run_id>/
├── research-spec.yaml
├── manifest.yaml
├── trial-ledger.jsonl
├── checkpoints/
├── candidates.parquet
├── evidence/
├── recommendations.json
└── report.md
```

- `research-spec.yaml` stores the frozen hypothesis and protocol.
- `manifest.yaml` stores code, engine, environment, data hashes, model,
  seed, and budget metadata.
- `trial-ledger.jsonl` records all candidates, experiments, and allowed
  methodological revisions.
- `checkpoints/` contains restart-safe worker state.
- `candidates.parquet` contains candidate definitions and metrics.
- `evidence/` contains the raw inputs to hard-gate decisions.
- `recommendations.json` contains unexecuted future hypotheses.
- `report.md` contains the human-readable conclusion.

The report is a view of the evidence, not the source of truth.

Every run references an immutable dataset snapshot through a
content-addressed dataset ID and hash. The snapshot may live in a shared
local cache rather than be duplicated under every run, but replay must
fail closed if the exact content is unavailable or its hash differs.

## 8. AlphaStrategy handoff

### 8.1 Boundary

alphaloop owns research and candidate qualification. AlphaStrategy owns:

- paper, shadow, and live execution;
- broker adapters and order construction;
- account-level risk controls;
- promotion and demotion decisions;
- execution monitoring and kill switches.

The integration is strictly one-way in the first design:

```text
alphaloop -> Strategy Candidate Bundle -> AlphaStrategy
```

AlphaStrategy does not send fills, performance, drift, or other
telemetry back to alphaloop.

### 8.2 Export

Only a `FOUND` candidate can be exported, and export requires a human
action:

```text
alphaloop export <candidate_id> --output strategy.asb
```

The `.asb` file is an immutable local archive. Its schema includes an
optional `registry_uri` for future registry-based distribution. The
first release does not require or operate a registry.

```text
strategy.asb
├── bundle.yaml
├── strategy.dsl.yaml
├── market-profile.yaml
├── parameters.yaml
├── risk-envelope.yaml
├── lineage.yaml
├── evidence/
└── conformance/
```

The archive contains:

- a schema version, canonical content hash, and content-addressed
  `bundle_id` derived from that hash;
- the constrained strategy DSL;
- frozen parameters and market profile;
- research-stage risk assumptions;
- complete run and evidence lineage;
- fixed conformance inputs and expected outputs;
- an optional `registry_uri`;
- no credentials;
- no arbitrary executable code.

Any change creates a new bundle and a new content hash.

### 8.3 Strategy output semantics

The strategy DSL outputs broker-neutral target weights or exposures:

```text
effective_at -> {asset_id: target_weight}
```

AlphaStrategy maps target weights to orders using account size, current
positions, liquidity, broker rules, and stricter account-level risk
limits. If it cannot achieve the target weights, it records execution
deviation rather than silently changing the strategy definition.

Paper and live environments consume the same immutable bundle.

### 8.4 Import safety

AlphaStrategy must reject a bundle when:

- the schema or DSL version is unsupported;
- the content hash is invalid;
- required lineage or evidence is missing;
- conformance fixtures produce different target weights;
- the market profile is unsupported.

Import does not authorize trading. Promotion from imported to paper,
shadow, or live is an independent AlphaStrategy workflow with explicit
human approval.

## 9. Failure semantics and safety

### 9.1 Preflight rejection

Invalid data, unsupported hypotheses, missing benchmarks, insufficient
resources, and inexpressible DSL requirements are rejected before a
formal run begins. A preflight error is not a research outcome.

### 9.2 Runtime failures

- Candidate-specific failures isolate and eliminate that candidate.
- A data-integrity or diagnostic-engine failure stops the whole run.
- Recoverable process failures restart from the latest complete
  checkpoint.
- An unrecoverable worker failure yields a failed job and an
  inconclusive outcome.
- Exhausted time or cost budgets yield `INCONCLUSIVE` when the required
  evidence set is incomplete.

### 9.3 Evidence authority

Only the deterministic hard-gate evaluator can produce `FOUND`.

The Web console, LLM judge, report generator, or agent narrative cannot
override a gate. Missing, corrupted, or partial evidence prevents
`FOUND`.

### 9.4 Trading hard wall

alphaloop does not:

- hold broker credentials;
- connect to a broker;
- submit paper or live orders;
- invoke AlphaStrategy execution APIs;
- automatically promote a candidate.

## 10. Product surfaces

### 10.1 Web

The Web console is the primary surface because it supports long-running
jobs, progress, review, and artifact navigation.

### 10.2 CLI

The CLI starts the local control plane, submits jobs, queries status,
replays results, and exports bundles. Long jobs return a `run_id`
instead of holding a synchronous command session open.

### 10.3 Agent Skill

A local Agent Skill teaches coding agents to:

- formulate and preflight a hypothesis;
- submit through the CLI or Job API;
- poll rather than block for hours;
- interpret the three research outcomes;
- avoid claiming alpha after a failed gate;
- request human approval for a new hypothesis or bundle export.

The Skill is workflow guidance, not a service or an evidence engine.

### 10.4 MCP

MCP is not required for the first core experience. A later thin adapter
may expose short asynchronous operations such as:

- `create_run`
- `get_run_status`
- `get_run_result`
- `cancel_run`

No MCP tool call remains open for an overnight run.

### 10.5 Desktop app

A desktop wrapper is deferred. The local daemon plus packaged Web
console provides the required experience without early cross-platform
desktop maintenance.

## 11. First-release scope

### Included

- one user on one local machine;
- one-command local startup;
- durable Job API and local worker supervision;
- checkpoint and restart recovery;
- packaged Web console;
- frozen research specifications;
- constrained strategy DSL;
- iterative research with epistemic stopping;
- US-equity daily and crypto daily profiles;
- three research outcomes;
- evidence and trial-ledger artifacts;
- manual immutable `.asb` export;
- optional `registry_uri` field in the bundle schema;
- CLI and local Agent Skill.

### Excluded

- official hosted cloud;
- remote worker implementation;
- team identity, permissions, and approvals;
- Bundle Registry;
- desktop packaging;
- live or paper trading in alphaloop;
- AlphaStrategy implementation work;
- AlphaStrategy-to-alphaloop telemetry;
- automatic paper/live promotion;
- arbitrary generated strategy code;
- an MCP adapter; this is a later integration and must never keep an
  overnight tool call open.

## 12. Verification strategy

### State and protocol

- Model tests cover every valid and invalid job-status/outcome
  combination.
- Negative tests prove no incomplete diagnostic set can produce
  `FOUND`.
- Property tests prove every candidate and methodological revision is
  represented in multiple-testing accounting.

### Reproducibility

- Fixed plan, data snapshot, engine version, and seed replay to identical
  deterministic candidate results and evidence.
- LLM-generated planning output is snapshotted before deterministic
  replay.

### Resilience

- Fault injection kills workers at each checkpoint boundary.
- Tests simulate interrupted writes, disk pressure, candidate crashes,
  daemon restarts, and exhausted budgets.
- Recovery never treats partial artifacts as complete.

### Market profiles

- Each profile has an independent conformance suite for calendars,
  costs, benchmarks, and data-quality rules.
- Cross-profile tests prove candidates are not mixed into one default
  ranking.

### Bundle contract

- Hash and tamper tests reject altered bundles.
- Unsupported schema and DSL versions fail closed.
- Producer and consumer share fixed conformance fixtures.
- AlphaStrategy import contract tests must produce exactly the expected
  target weights before accepting a bundle.

### End-to-end

- CI runs a shortened complete overnight workflow.
- Release candidates run a real overnight soak benchmark.
- Usability validation confirms a user can identify the conclusion,
  primary evidence, and stop reason in five minutes.

## 13. Implementation decomposition

This target is too large for one implementation plan or pull request.
Implementation must proceed through separate specifications and plans:

1. **Core contracts:** Research Spec, run state machine, artifact schema,
   Strategy Candidate Bundle schema.
2. **Durable local runtime:** Job API, daemon, supervisor, checkpoints,
   and recovery.
3. **Research protocol:** constrained DSL, iterative loop, epistemic
   stopping, and both market profiles.
4. **Morning Web experience:** preflight, progress, conclusion, evidence
   funnel, and recommendations.
5. **AlphaStrategy handoff:** `.asb` producer and independent consumer
   contract. AlphaStrategy repository work remains a separate plan.
6. **Agent entry:** local Skill and CLI workflow, followed only if needed
   by a thin asynchronous MCP adapter.

The next implementation-design cycle should begin with item 1. Later
items depend on its versioned contracts.

Refactor mapping and file boundaries:
[`docs/design/overnight-research-lab-refactor.md`](../design/overnight-research-lab-refactor.md).

Phase 1 implementation plan:
[`docs/superpowers/plans/2026-08-18-overnight-lab-phase1-contracts.md`](../superpowers/plans/2026-08-18-overnight-lab-phase1-contracts.md).
