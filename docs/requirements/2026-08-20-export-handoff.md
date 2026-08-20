---
title: "CLI export prints a FOUND handoff, not only a path"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to product-positioning-requirements.md §8.2 / §10.2"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-found-handoff.md
  - docs/requirements/2026-08-20-cli-status-verdict.md
---

# CLI export prints a FOUND handoff, not only a path

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** Default stdout of `alphaloop export`. Not a new hard gate.
Not inventing `FOUND`. Not auto-export. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\). Not changing `assert_exportable`.

## 1. Why this cycle exists

PRD §8.2: export of a `FOUND` candidate is a **human** handoff to
AlphaStrategy. PRD §10.2: CLI is a first-class surface. `status`,
`cancel`, `resume`, and `replay` already print a five-minute cluster.
`alphaloop export` still prints only the output path.

A researcher who just exported cannot see the outcome token or the
candidate id without opening the zip. Nielsen: recognition rather
than recall. Tufte: do not hide the claim in a pathname.

The writer stays `export_found_asb` / `assert_exportable`. Success
is already `FOUND` only. This cycle is the receipt, not a new gate.

## 2. Best-practice basis

1. **Same first line as status:** the outcome token `FOUND`.
2. **Human default, `--json` for agents.** Default stdout must fail
   `json.loads`. `--json` is
   `{"candidate_id","exported_path","research_outcome"}` with
   `sort_keys=True`.
3. **Do not claim alpha.** Locked sentence, verbatim:
   `This export does not claim alpha or future profitability.`
4. **Do not invent FOUND.** Only print the cluster after
   `export_found_asb` returns. Failures stay stderr + exit 2.

## 3. In-scope requirements

### R1. Default receipt

After a successful write, default `alphaloop export` MUST print,
in order, trailing newline:

1. `FOUND`
2. `Qualifying: {candidate_id}`
3. `Exported: {output path}`
4. `This export does not claim alpha or future profitability.`

MUST NOT print only the bare path. MUST NOT contain `target found`.
MUST NOT dump the zip bytes.

### R2. `--json`

`alphaloop export ... --json` MUST print
`json.dumps({"candidate_id": ..., "exported_path": ..., "research_outcome": "FOUND"}, sort_keys=True)`.

### R3. Docs

`docs/cli.md` export section describes the receipt and `--json`.
Overnight-lab Skill MAY mention the default receipt.
`assert_exportable` unchanged. `gates.json` fallback still not
exportable.

## 4. Out of scope

- Auto-export on `FOUND`. Changing `.asb` contents. Soak.
  \(N_{\mathrm{eff}}\). FakeWorker in morning e2e.

## 5. Acceptance

- Unit: successful export first line `FOUND`; cluster includes
  qualifying id, `Exported:`, no-alpha sentence; `--json` payload;
  default fails `json.loads`; non-FOUND still exit 2.
- E2E: when the page outcome is `FOUND`, CLI export stdout starts
  with `FOUND` and includes the no-alpha sentence.
- Locks: no `target found`; no Python in `.asb`; no invented `FOUND`.
