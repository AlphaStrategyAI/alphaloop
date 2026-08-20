---
title: "Morning verdict stages primary evidence with the stop reason"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §3.4 / §4.3 / §12"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-verdict.md
  - docs/requirements/2026-08-19-five-minute-morning-review.md
---

# Morning verdict stages primary evidence with the stop reason

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Packaged morning console verdict stage, `morning_view`
payload, and `report.md` view of the same primary-evidence sentence.
Not a new hard gate. Not inventing `FOUND`. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\).

## 1. Why this cycle exists

The product promise is: understand a trustworthy conclusion in five
minutes. PRD §3.4 / §12 name three tokens a morning reader must
identify **from the home page**:

1. the conclusion (`FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`);
2. the **primary evidence**;
3. the **stop reason**.

The verdict stage already leads with the outcome token and a locked
Help gloss. Stop reason still sits below search progress. Primary
evidence is only the later `#evidence` list and funnel. A five-minute
reader has to hunt for which gate actually decided the night.

That is not one-glance overnight-lab UX. Nielsen: recognition rather
than recall; visibility of system status. Tufte: the display must
show the data that supports the claim, and must not imply a claim
the evidence does not support. CONSORT / pre-registration: report
the pre-specified primary result next to the conclusion, not only
in an appendix.

## 2. Best-practice basis

1. **Three tokens in one cluster (PRD §3.4 / §4.3 / §12):** conclusion,
   primary evidence, and stop reason share `#verdict`. `#outcome` stays
   the token so existing tests keep reading one word.
2. **Primary means one fact, not the whole funnel.** For
   `NO_EVIDENCE`, that fact is the first `funnel.dominant_failures`
   name (highest failure count). The funnel section still lists every
   failed gate. Do not invent a gate name when the list is empty.
3. **Do not re-derive `FOUND`.** `format_primary_evidence` follows the
   sealed `research_outcome`. Incomplete or missing `gates.json` never
   produces the all-passed sentence. `INCONCLUSIVE` never claims that
   required gates passed, even if a leftover file looks green.
4. **Same sentence in `report.md`.** The archived artifact a human
   files away must carry `primary_evidence:` so a paste into notes
   still has the three tokens. No LLM prose. No alpha claim.

## 3. In-scope requirements

### R1. Payload field

`morning_view` MUST include `primary_evidence` (`str | None`) computed
by `alphaloop.runtime.artifacts_io.format_primary_evidence`.

| `research_outcome` | `primary_evidence` |
| --- | --- |
| `FOUND` | `all required hard gates passed` |
| `NO_EVIDENCE` with a non-empty `funnel.dominant_failures` | `{dominant_failures[0]} failed` |
| `NO_EVIDENCE` with an empty dominant list | `a required hard gate failed` |
| `INCONCLUSIVE` with missing required names in sealed evidence | `missing {name, ...}` (required order) |
| `INCONCLUSIVE` with no readable `gates.json` | `no sealed gates.json` |
| `INCONCLUSIVE` otherwise | `incomplete evidence set` |
| `NONE` | `None` |

The function MUST NOT inspect the outcome of other jobs. It MUST NOT
claim alpha. It MUST NOT emit `FOUND` as text.

### R2. Verdict cluster

Packaged detail MUST keep `#outcome` then `#outcome-gloss` inside
`#verdict`, then:

1. `#primary-evidence`
2. `#stop-reason` (moved into `#verdict`; no second copy)

`#job-status` stays **after** `#verdict`. `#outcome` text remains
exactly the research-outcome token.

After `showJob`, `#primary-evidence` `textContent` is:

- `Primary evidence: {primary_evidence}` when the field is a non-empty
  string;
- `Primary evidence: (running or not yet terminal)` when it is `null`
  / missing (same parenthetical as today's empty stop reason).

`#stop-reason` copy is unchanged: `Stop reason: {stop_reason}` or
`Stop reason: (running or not yet terminal)`.

### R3. `report.md`

`write_report` MUST emit `primary_evidence: {value}` immediately after
`stop_reason` when `format_primary_evidence` returns a string. Omit
the line when the value is `None`. Existing header, no-alpha sentence,
gates, funnel, and qualifying sections stay.

### R4. Locks

`HOST_CONSTRAINT` unchanged. Existing Help sentences unchanged.
Example YAML unchanged. No webfont URL. No Node. No gate override.
No `FakeWorker` in morning e2e.

## 4. Out of scope

- Soak. \(N_{\mathrm{eff}}\). MCP / cloud workers. Unfreezing `webui/`.
- Replacing the evidence list or funnel. Those remain the full record.
- Auto-submitting a queued follow-up.

## 5. Acceptance

- Unit: `format_primary_evidence` / `morning_view` cover FOUND,
  NO_EVIDENCE (dsr first), INCONCLUSIVE with no gates file, NONE.
- Unit: `write_report` includes `primary_evidence:` on a failed DSR.
- Packaged assets: `#primary-evidence` inside `#verdict` before
  `#stop-reason`; `#stop-reason` before `#job-status`.
- E2E: `#outcome` is still exactly the token; `#primary-evidence`
  starts with `Primary evidence:`; INCONCLUSIVE-without-gates mentions
  `no sealed gates.json`.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.

## 6. Loop exit

Remaining first-release items are soak / 95% overnight (not CI) and
correlation-adjusted \(N_{\mathrm{eff}}\) (must not shrink DSR `N`).
Later: MCP / cloud workers. Autonomous iteration stays inside the
human-freeze lock.
