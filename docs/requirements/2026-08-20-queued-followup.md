---
title: "Evidence-backed follow-up hypotheses queued for a human run"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §4.3 / §6.1"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-funnel.md
  - docs/requirements/2026-08-20-frozen-grid-honest-kinds.md
---

# Evidence-backed follow-up hypotheses queued for a human run

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Deterministic, constrained follow-up hypotheses after
`NO_EVIDENCE`, plus a morning "Load into editor" action. Not an in-run
LLM. Not expanding a failed method grid. Not inventing `FOUND`.

## 1. Why this cycle exists

PRD §4.3 requires the morning page to present **evidence-backed
suggestions for a future hypothesis**. PRD §6.1: a new
`signal_mechanism` is a new economic hypothesis; the agent may
recommend it; a human must freeze it in a **future** run.

The production worker does not pass `revision_proposer`. Overnight
jobs therefore write `queued_hypotheses: []`. The funnel now shows
why the frozen grid died, but the user still has to invent the next
YAML from memory. That is not one-minute iterate, and it is not
autonomous search-with-human-approval.

## 2. Best-practice basis

1. **Pre-registration / CONSORT:** the next experiment is named from
   the failed evidence, not from peeking until profitable.
2. **PRD epistemic stop:** do not expand the failed parameter search;
   change of kind is queued, not executed.
3. **Nielsen recognition rather than recall:** a button loads the
   suggestion into the guided form; freeze still requires Preview.
4. **Do not claim alpha.** Follow-up copy MUST say it is not a claim
   of alpha.

## 3. In-scope requirements

### R1. Counterpart kind

`alphaloop.protocol.recommend.counterpart_kind(kind) -> str | None`

- Trend family `momentum_12_1`, `roc`, `macd`, `atr_breakout` → `rsi`
- Reversion family `rsi`, `bollinger_zscore`, `ohlr_4_pct` →
  `momentum_12_1`
- `pairs_spread` → `rsi`
- Feature / volume / unknown → `None`

The counterpart MUST be in `DIRECTIONAL_SIGNAL_KINDS` and MUST NOT
equal `kind`.

### R2. Queue only after `NO_EVIDENCE`

When `run_protocol` returns `NO_EVIDENCE` with complete evidence, if
`recommendations.json` `queued_hypotheses` is empty, write exactly one
follow-up mapping:

- `queued_reason`: `economic_change_queued`
- `signal_mechanism`: counterpart kind
- `market_scope`, `market_profile`, `benchmark`, `hard_gates` copied
  from the frozen spec
- `statement` cites the frozen kind, dominant failed gate names, the
  next kind, and the words `not a claim of alpha`
- `economic_logic`: follow-up mechanism text, not a profitability claim

Do **not** queue on `FOUND` or `INCONCLUSIVE`. Do **not** overwrite a
non-empty queue (injected proposer / existing file). Do **not**
evaluate the follow-up in the same run.

### R3. Morning Load into editor

Each queued item in `#queued` MUST have a `button.load-queued` that
fills `#hypothesis-form` / `#spec-yaml` from that mapping, clears the
preview snapshot, and leaves `#submit-job` disabled. It MUST NOT POST
`/v1/jobs`. It MUST NOT invent `FOUND`. `HOST_CONSTRAINT` unchanged.

## 4. Out of scope

- LLM proposer. Executing the follow-up in the same job. `S=16`. Soak.
- FakeWorker in morning e2e. Unfreezing `webui/`. Parkinson/OBV as
  follow-ups.

## 5. Acceptance

- Unit: counterpart table; complete-fail momentum queues `rsi`; FOUND
  does not queue; existing `keep me` queue is preserved; frozen-grid
  proposer is not called.
- Unit: HTML/JS contain `load-queued`.
- E2E: writing a queued row then clicking Load fills `rsi` and does
  not create a second job.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
