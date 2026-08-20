---
title: "Replay prints the five-minute verdict; PRD remaining work is honest"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §3.4 / §10.2 / §13"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cli-status-verdict.md
  - docs/requirements/2026-08-20-honest-docs-morning-help.md
  - docs/requirements/2026-08-20-empty-morning.md
---

# Replay prints the five-minute verdict; PRD remaining work is honest

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Default stdout of `alphaloop replay`, plus honest PRD §13 /
refactor remaining-work pointers. Not a new hard gate. Not inventing
`FOUND`. Not unfreezing `webui/`. Not soak execution. Not
\(N_{\mathrm{eff}}\). Not requiring the daemon for replay.

## 1. Why this cycle exists

PRD §3.4 / §12: a morning reader must identify conclusion, primary
evidence, and stop reason in five minutes. `status`, `cancel`, and
`resume` already print that cluster via `format_status_verdict`.
`alphaloop replay RUN_ID` still prints only `research_outcome: TOKEN`
after rewriting `report.md`. Regenerating the paper view hides the
verdict behind a labeled key.

Separately, PRD §13 still says remaining first-release work is
protocol gate returns, durable artifacts, morning submit/progress, and
§12 verification (Phases 8–11). Those phases shipped. Honest-docs
labeled the remaining-work design historical; empty-morning fixed
`ROADMAP.md`. The PRD — the loop's source of truth — still sells
unfinished Phases 8–11. Docs that claim shipped work is unfinished
destroy trust (five-minute review R6).

## 2. Best-practice basis

1. **Same cluster as `status RUN_ID`.** Reuse `format_status_verdict`.
   First line is the outcome token. Do not prepend `run_id:` (the
   caller already passed it).
2. **Verdict matches the rewritten report.** Replay derives the
   outcome from sealed `gates.json` (current behavior). It MUST NOT
   substitute a stale sqlite `research_outcome` when that disagrees
   with the artifacts it just used to write `report.md`.
3. **Offline.** Replay MUST keep working without the daemon. It MUST
   NOT re-run gates. It MUST NOT mint `FOUND`.
4. **Human default, `--json` for agents.** Same gh / kubectl pattern
   as status / cancel / resume.
5. **Honest remaining work.** Phases 1–11 are a historical map, not a
   current gap list. Current remaining work matches `ROADMAP.md`:
   soak execution on an awake host, do not shrink DSR `N` with
   \(N_{\mathrm{eff}}\), later MCP / cloud.

## 3. In-scope requirements

### R1. Default replay stdout is the five-minute verdict

After rewriting `report.md`, default `alphaloop replay RUN_ID` MUST
print `format_status_verdict` for a view whose:

- `research_outcome` is the token derived from sealed `gates.json`
  (same derivation as today's `write_report` path);
- `primary_evidence`, `stop_reason`, `queued_hypotheses`, and
  `qualifying_candidates` come from the run artifacts;
- `status` is the job-store status when
  `{data_dir}/.alphaloop/state.db` contains that `run_id`, else `""`.

It MUST NOT print `research_outcome: {token}` as the human default.
It MUST NOT contain `target found`. It MUST NOT dump `report.md`.
First line is the outcome token. Trailing newline. Locked no-alpha
sentence is `STATUS_NO_ALPHA` (verbatim):
`This status does not claim alpha or future profitability.`

Missing run directory stays exit 2.

### R2. `--json`

`alphaloop replay RUN_ID --json` MUST print
`json.dumps(view, sort_keys=True)` of that same view (not a second
derivation). Default stdout MUST fail `json.loads`.

### R3. PRD §13 and refactor pointer

In `docs/requirements/product-positioning-requirements.md` §13:

- MUST NOT say remaining first-release gaps are protocol gate
  returns, durable artifacts, morning submit/progress, and §12
  verification (Phases 8–11).
- MUST state that Phases 8–11 shipped.
- MUST point remaining first-release work at soak execution (not CI),
  not shrinking DSR `N` with \(N_{\mathrm{eff}}\), and later MCP /
  cloud. MCP must still never keep an overnight tool call open.
- The remaining-work plan link MUST be labeled historical.

In `docs/plans/overnight-research-lab-refactor.md`, the sentence that
says remaining first-release work is Phases 8–11 MUST instead say
those phases shipped and the remaining-work design is historical.

Do not rewrite the body of
`docs/plans/2026-08-19-overnight-lab-remaining-work.md`.

### R4. Docs surfaces

`docs/cli.md` replay section: default is the five-minute verdict;
`--json` for agents; still rewrites `report.md` without re-running
gates. README / `docs/index.md` replay one-liners may note the
verdict. Overnight-lab Skill MAY mention replay uses the same
verdict as `status`.

## 4. Out of scope

- Requiring the daemon. Changing `write_report`. Unfreezing `webui/`.
- Soak execution. \(N_{\mathrm{eff}}\). FakeWorker in morning e2e.
- Changing Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.

## 5. Acceptance

- Unit: replay default first line is `FOUND` (artifact fixture);
  cluster includes gloss, primary evidence, stop reason, job status
  line, `STATUS_NO_ALPHA`; `--json` is the view; missing dir exit 2.
- Static: PRD §13 does not list Phases 8–11 as remaining gaps;
  refactor pointer says shipped / historical.
- E2E: `alphaloop replay RUN_ID` first line equals the page outcome
  token; `report.md` still rewritten; page outcome unchanged.
- Locks: no `target found`; no gate override; no FakeWorker in
  morning e2e.
