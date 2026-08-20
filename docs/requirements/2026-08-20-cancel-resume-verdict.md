---
title: "CLI cancel and resume print the five-minute verdict"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "docs/requirements/2026-08-20-cli-status-verdict.md §4 (cancel/resume JSON-only)"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-cli-status-verdict.md
---

# CLI cancel and resume print the five-minute verdict

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Default stdout of `alphaloop cancel` and `alphaloop resume`.
Not a new hard gate. Not inventing `FOUND`. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\). Not changing `status`.

## 1. Why this cycle exists

PRD §3.4 / §4.3: identify conclusion, primary evidence, and stop
reason in five minutes. `alphaloop status` already prints that
cluster. `cancel` and `resume` still dump the full `morning_view`
JSON, including `report_markdown`.

A researcher who stops a run or wakes the host then types `cancel` /
`resume` still cannot read the outcome without parsing JSON. Nielsen:
visibility of system status. Job status is not the research
conclusion — but the default command must not hide the conclusion
inside a payload dump.

## 2. Best-practice basis

1. **Same cluster as `status RUN_ID`.** Reuse `format_status_verdict`.
   First line is the outcome token. Do not prepend `run_id:` (the
   caller already passed it).
2. **`--json` for agents and e2e.** Byte-stable
   `json.dumps(morning_view, sort_keys=True)`.
3. **Do not re-derive `FOUND`.** Cancel of a sealed FOUND job keeps
   FOUND (existing store rule). Cancel before seal is INCONCLUSIVE.

## 3. In-scope requirements

### R1. `--json` on cancel and resume

`alphaloop cancel RUN_ID [--json]` and
`alphaloop resume RUN_ID [--json]`.

### R2. Default verdict

Without `--json`, stdout is `format_status_verdict(morning_view)`
exactly as `alphaloop status RUN_ID`. It MUST NOT be a JSON object.
It MUST contain the locked no-alpha sentence. It MUST NOT contain
`target found`.

`--json` prints the full `morning_view` payload.

### R3. Docs

`docs/cli.md` cancel / resume sections match R1–R2. Help /
`HOST_CONSTRAINT` / example YAML unchanged.

## 4. Out of scope

- Making `RUN_ID` optional on cancel/resume.
- Soak. \(N_{\mathrm{eff}}\). MCP / cloud. Unfreezing `webui/`.

## 5. Acceptance

- Unit: cancel a queued job → first line `INCONCLUSIVE`,
  `Job status: cancelled`; `--json` has those fields.
- Unit: resume a failed job → first line `NONE`; `--json` status
  `queued`.
- E2E: `cancel --json` / `resume --json` keep payload asserts;
  default cancel first line equals page `#outcome` after cancel-before-seal.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.

## 6. Loop exit

Remaining: soak **execution** on an awake host; do not shrink DSR
`N` with \(N_{\mathrm{eff}}\). Later: MCP / cloud.
