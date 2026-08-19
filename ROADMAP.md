# alphaloop Roadmap

alphaloop is a **local-first overnight research lab** for AI-native
independent quantitative researchers. A user submits a constrained
investment hypothesis before bed. A local worker researches on the
user's machine. In the morning the console presents one of three
conclusions: `FOUND`, `NO_EVIDENCE`, or `INCONCLUSIVE`.

The product promise is:

> Submit in one minute before bed; run reliably overnight; understand a
> trustworthy conclusion in five minutes the next morning.

alphaloop does **not** promise alpha or future profitability. Its value
is making agent-assisted strategy research reproducible, auditable, and
resistant to automated p-hacking.

---

## First release (current)

What ships now:

- Frozen `ResearchSpec` (hypothesis, hard gates, seed, budgets, optional
  content-addressed dataset).
- Local Job API + supervisor + `ProcessWorker`. `alphaloop start` is the
  control plane, worker, and packaged static morning page.
- Constrained strategy DSL. Markets `us-equity-daily` and `crypto-daily`
  are independent.
- Hard gates with fail-closed evidence. `FOUND` only from complete
  `GateEvidence`. `llm_judge` is not a gate.
- Trial ledger, checkpoints, `manifest.yaml`, `candidates.parquet`,
  `report.md`.
- Morning review: job **status** and research **outcome** stay separate;
  the page and report disclose the frozen hypothesis, `spec_id`, `seed`,
  and unique-ledger `n_trials`.
- YAML submit from the packaged Web console or CLI. Closing the browser
  or CLI does not stop a job; host sleep or power-off does.
- Optional export of an immutable Strategy Candidate Bundle (`.asb`)
  when `FOUND`. AlphaStrategy owns paper/live trading.

What this release is **not**:

- An AI trading bot, broker, or live execution path (`alphaloop.live`
  stays frozen).
- A command that "finds a strategy that beats SPY."
- MCP as the overnight runtime. A later thin MCP may expose short
  asynchronous job-control operations only.
- The frozen Vite + React Quant Lab SPA under `webui/`. First-release UI
  is `src/alphaloop/webui/static/` served by the daemon.

---

## Remaining work (not a promise of alpha)

Honest follow-ons, in product order:

1. **Overnight soak (release process, not CI).** PRD §3.4 asks that a
   fixed overnight benchmark complete without operator intervention on
   every supported platform. That is a release gate, not a pytest job.
2. **Protocol preview before freeze.** PRD §4.1 step 4: review the
   research protocol in the console before the job is frozen.
3. **Richer five-minute evidence.** Qualifying-candidate tables and
   funnel visualization beyond today's gate list, still without claiming
   alpha.
4. **Optional later surfaces.** Short MCP job-control; cloud workers for
   hosts that cannot stay awake. Neither replaces the local Job API.

Out of scope until a later positioning change: team permissions, broker
integration, unfreezing `alphaloop.live`, treating `llm_judge` as a hard
gate.

---

## Version note

Package version `0.5.0` is the overnight-lab line, not a rename-only
freeze of the old `openstrategy` tool. Historical `openstrategy` v1.0
remains a git tag. Do not read the version number as "the loop finds
alpha."

---

## References

- `docs/requirements/product-positioning-requirements.md`
- `docs/requirements/2026-08-19-five-minute-morning-review.md`
- Bailey & López de Prado (2014), Deflated Sharpe Ratio / selection-bias
  disclosure
- Nielsen, visibility of system status (job status ≠ research outcome)
