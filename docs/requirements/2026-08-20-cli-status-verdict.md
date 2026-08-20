---
title: "CLI status leads with the five-minute morning verdict"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §3.4 / §4.3 / §10.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-morning-verdict.md
  - docs/requirements/2026-08-20-primary-evidence.md
  - docs/requirements/2026-08-20-next-run-cue.md
  - docs/requirements/2026-08-20-found-handoff.md
---

# CLI status leads with the five-minute morning verdict

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `alphaloop status` human output and `--json` machine
payload. Not a new hard gate. Not inventing `FOUND`. Not unfreezing
`webui/`. Not soak execution. Not \(N_{\mathrm{eff}}\). Not changing
`cancel` / `resume` JSON.

## 1. Why this cycle exists

The product promise is: understand a trustworthy conclusion in five
minutes. PRD §3.4 / §12 name three tokens a morning reader must
identify: conclusion, primary evidence, and stop reason. PRD §10.2
makes the CLI a first-class surface for the AI-native / terminal
user. The packaged Web `#verdict` already clusters those tokens with
a locked Help gloss.

`alphaloop status RUN_ID` still dumps the entire `morning_view` JSON,
including `report_markdown`. A human cannot scan that in five minutes.
An agent that `json.loads` stdout is served, but the default command
is not the morning review. Nielsen: recognition rather than recall.
Tufte: do not bury the claim in an appendix.

## 2. Best-practice basis

1. **Human default, explicit `--json` (gh / kubectl pattern).** Default
   stdout is the five-minute cluster. Agents that parse status use
   `--json`. Do not mix a prose stanza with JSON on one stream.
2. **Same locked copy as Help.** Gloss sentences are the packaged
   `#help-found` / `#help-no-evidence` / `#help-inconclusive` /
   `#help-status` paragraphs. Do not invent a second narrative.
3. **Do not re-derive `FOUND`.** The formatter reads sealed
   `morning_view` fields. It never claims alpha. It never emits
   `target found`.
4. **Keep machine JSON byte-stable.** `--json` remains
   `json.dumps(morning_view, sort_keys=True)` so existing agent and
   e2e parsers keep working when they opt in.

## 3. In-scope requirements

### R1. Default verdict

`alphaloop status RUN_ID` (no `--json`) MUST print this cluster, in
order, one field per line, ending with a newline:

1. `research_outcome` token only (`FOUND` / `NO_EVIDENCE` /
   `INCONCLUSIVE` / `NONE`)
2. Locked gloss for that token (table below)
3. `Primary evidence: {primary_evidence}` or
   `Primary evidence: (running or not yet terminal)` when the field
   is null / missing / empty
4. `Stop reason: {stop_reason}` or
   `Stop reason: (running or not yet terminal)` when the field is
   null / missing / empty
5. `Next run: {queued_hypotheses[0].statement}` only when that list
   is non-empty and the first item has a statement
6. `Qualifying: {trial_id} · {kind} · {parameters}` only when
   `research_outcome` is `FOUND` and `qualifying_candidates` is
   non-empty. `trial_id` falls back to `gates.json`. `kind` may be
   empty. `parameters` is sorted `k=v` pairs, or `{}` when empty
7. `Job status: {status}`
8. Locked sentence, verbatim:
   `This status does not claim alpha or future profitability.`

| outcome | locked gloss |
| --- | --- |
| `FOUND` | `FOUND means every required hard gate is present and passed. It is not a promise of alpha.` |
| `NO_EVIDENCE` | `NO_EVIDENCE means a required hard gate failed. It is not a promise that alpha does not exist.` |
| `INCONCLUSIVE` | `INCONCLUSIVE means the evidence set is incomplete. Missing diagnostics cannot produce FOUND.` |
| `NONE` | `Job status (queued, running, completed, failed, cancelled) is not the research conclusion.` |

Default stdout MUST NOT be a JSON object. It MUST NOT include
`report_markdown`. It MUST NOT contain `target found`.

### R2. `--json`

`alphaloop status RUN_ID --json` MUST print the full `morning_view`
payload as `json.dumps(..., sort_keys=True)` followed by a newline.
This is the machine path for the overnight-lab Skill and for e2e
`json.loads`.

`cancel` and `resume` stay JSON-only (no human cluster).

### R3. Single formatter

`format_status_verdict(view: dict) -> str` lives next to `morning_view`
and is the only source of the human cluster. The CLI prints that
string. Unit tests cover FOUND, NO_EVIDENCE, INCONCLUSIVE, NONE, a
queued next-run line, and a FOUND qualifying line.

### R4. Docs and Skill

`docs/cli.md`, README / docs index status examples, and the packaged
overnight-lab Skill MUST say:

- humans read `alphaloop status RUN_ID` (five-minute cluster);
- agents parse `alphaloop status RUN_ID --json`.

Help / `HOST_CONSTRAINT` / example YAML unchanged.

## 4. Out of scope

- Soak execution. \(N_{\mathrm{eff}}\). MCP / cloud workers.
- Unfreezing `webui/`. Changing Web `#verdict`.
- Human-formatting `cancel` / `resume`.
- Auto-export of `.asb`.

## 5. Acceptance

- Unit: `format_status_verdict` line order and locked copy.
- Unit: CLI default status is not `json.loads`-able; `--json` is.
- E2E: `test_terminal_outcome_matches_cli_status` uses `--json`;
  default status first line equals the page `#outcome` token and
  includes `Primary evidence:` plus the no-alpha sentence.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.

## 6. Loop exit

Remaining first-release items: soak **execution** on an awake host
(not CI); correlation-adjusted \(N_{\mathrm{eff}}\) must not shrink
DSR `N`. Later: MCP / cloud workers. Autonomous iteration stays
inside the human-freeze lock.
