# alphaloop Roadmap

> **From openstrategy v1.0 (honest tool) → alphaloop v2.0 (AI research system).**
> Inspired by Jeff Dean's 9-point interview (Alpha Engineer 2026-08-07) on
> AI's next paradigm: recursive & automated.

---

## Why alphaloop?

openstrategy v1.0 (now archived as `v1.0` tag) was an honest, verifiable
research tool — "not find alpha, don't waste time on bad strategies." It
answered 6 questions for any strategy in under 30 minutes.

But Jeff Dean's view is sharper: **凡可测量者，皆可攻克 (anything measurable
will be cracked)**. openstrategy's 6 diagnostic questions are measurable.
That makes them candidates for *automation*, not just *tooling*.

So alphaloop's mission is to take the next step: turn openstrategy's
diagnostic suite into the **evaluation layer of an autonomous research loop**.

---

## Phased rollout

### v0.5 (this release) — **rename + freeze**

- Rename package `openstrategy` → `alphaloop`
- Version 1.1.3 → **0.5.0** (semantic-reset to signal "new direction")
- Keep **all v1.0 features working**: 4 sources, 10 factors, 11 strategies,
  6 diagnostic, Alpaca paper-by-default broker adapter
- Keep `v1.0` git tag as a permanent historical marker
- 191/191 tests pass; CI integration unchanged
- **No new features.** Pure rename + repositioning.

### v0.6 — **LLM judge evaluator (Jeff Dean #9: accelerate the evaluator)**

Add a 7th diagnostic: an **LLM-as-judge** that scores backtest reports on:

- Readability (1-10)
- Investment-decision合理性 (1-10)
- Risk-disclosure completeness (1-10)

Backend: OpenRouter Fusion (per the Trask / Fusion trend; multi-model
ensemble for 7-point uplift at half cost).

The point: **accelerate the evaluation loop** so the research loop can
iterate faster. This is the literal Jeff Dean #9 thesis applied to quant.

### v0.7 — **alphaloop loop MVP (Jeff Dean #8: AI builds AI)**

Ship the first end-to-end autonomous research loop:

```
alphaloop loop "find a strategy that beats SPY with DSR > 1.0"
```

Auto-executes:

1. Load 5y data from 4 sources
2. Generate strategy × factor × parameter combinations (N≈500)
3. Run walk-forward CV on each
4. Score with 6 diagnostic + LLM judge (#7)
5. Output top-5 strategy report (markdown + JSON)
6. Commit report + backtest code to git

Targets: a single command that runs ~6h on multi-agent parallel,
returns a fully reproducible top-5 list.

### v1.0 (re-release) — **alphaloop as a research loop platform**

After v0.6 and v0.7 prove the concept, re-tag v1.0 under the new
`alphaloop` brand with:

- `alphaloop report` (rebranded from `openstrategy report`)
- `alphaloop loop` (new autonomous research command)
- `alphaloop serve` (MCP server — expose alphaloop to any LLM agent
  via Anthropic MCP protocol)
- Full integration with Anthropic Claude Code, OpenRouter, and at
  least one OSS model provider

### v2.0 — **AI research system (full)**

The full Jeff Dean #8 vision:

- Multi-agent evaluation search (multiple `alphaloop loop` runs,
  with a meta-evaluator picking the most promising paths — Jeff Dean #4)
- Self-feedback: failures auto-redesign the next experiment
- Anthropic MCP-native (Sonnet can call alphaloop directly)
- Hugging Face / Replicate / AWS Marketplace distribution

---

## Why the version reset to 0.5.0?

`v1.0` exists as a tag on the old `openstrategy` brand — that tag is
**historical** and **not** going away. New development under the
`alphaloop` brand starts at 0.5.0 so consumers can clearly distinguish:

- `openstrategy<1.0.0` — original tool (still installable via pip)
- `alphaloop>=0.5.0` — rebrand (same code, new name)
- `alphaloop>=0.6` — adds LLM judge
- `alphaloop>=0.7` — adds autonomous loop

`alphaloop==1.0.0` will be tagged when the loop MVP ships and we have
**reproducible evidence** that the loop finds alpha the honest way.

---

## Brand notes

- The `openstrategy` PyPI name remains owned (we don't transfer it)
- The `fpc0000/openstrategy` GitHub repo will be **renamed** to
  `AlphaStrategyAI/alphaloop` in a separate step (requires user OK)
- The 191 existing tests are unchanged; alphaloop is a drop-in rename

---

## References

- Jeff Dean interview (Alpha Engineer 2026-08-07) — 9 core points
- Lilian Weng "Harness Engineering" (2026-07)
- Addy Osmani "Loop Engineering" (2026-06)
- LLM Wiki CLI (Karpathy-style persistent memory)