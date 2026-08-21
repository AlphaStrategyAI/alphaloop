---
title: "CLI status names repaired signal kinds on revision lines"
status: "requirements"
authors:
  - alphaloop
date: "2026-08-20"
supersedes: "none — additive to 2026-08-20-revision-kind-gloss.md / 2026-08-20-cli-status-verdict.md"
related:
  - docs/requirements/product-positioning-requirements.md
  - docs/requirements/2026-08-20-revision-kind-gloss.md
  - docs/requirements/2026-08-20-cli-status-verdict.md
  - docs/requirements/2026-08-20-qualifying-glosses.md
---

# CLI status names repaired signal kinds on revision lines

**Date:** 2026-08-20
**Status:** Approved for this implementation cycle
**Scope:** `format_status_verdict` optional `Revision:` lines via
`format_revision_line`; `replay_view` includes the same `revisions`
rows as `morning_view`. Not inventing `FOUND`. Not rewriting
`trial-ledger.jsonl`. Not shrinking DSR `N`. Not unfreezing `webui/`.
Not soak. Not \(N_{\mathrm{eff}}\). Not restyling chrome. Not changing
the locked outcome gloss.

## 1. Why this cycle exists

PRD §4.3 / §10.2: the CLI is a first-class five-minute surface.
Packaged `#revisions` and `report.md` now print
`c_2 · method · momentum_12_1 — 12-1 momentum · window=21`.
`alphaloop status` / `replay` still omit those lines, so a terminal
reader cannot tell which frozen signal the method repair applied to.

Nielsen: recognition rather than recall. CONSORT: name the analysed
method on every reporting surface, not only the Web report.
`2026-08-20-revision-kind-gloss.md` left CLI status out of that cycle
on purpose.

YAML / EXAMPLE_SPEC / Help / `HOST_CONSTRAINT` unchanged.

## 2. Best-practice basis

1. **Same line as the report.** Reuse `format_revision_line` (kind
   gloss, revision token, params). No second formatter.
2. **Keep the cluster compact.** Prefix `Revision:`. Empty list omits
   the line, matching `Next run:` / `Qualifying:`.
3. **Same payload as morning.** `replay_view["revisions"]` MUST be
   `build_method_revisions(layout)` so replay/status share rows.
4. **Do not claim alpha.** Locked outcome gloss and no-alpha sentence
   unchanged.

## 3. In-scope requirements

### R1. Verdict lines

`format_status_verdict` MUST, after `Stop reason:` and before
`Next run:`, emit one `Revision: {format_revision_line(row)}` line
per dict in `view["revisions"]`. Non-dict rows skipped. Empty or
missing `revisions` omits every `Revision:` line.

### R2. Replay payload

`replay_view` MUST include `revisions` from `build_method_revisions`.
`--json` already dumps the view; do not invent `FOUND`.

### R3. Docs

`docs/cli.md` MUST say the five-minute cluster may include revision
lines that name the repaired signal with the same gloss as the form.
Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC stay locked.

## 4. Out of scope

- Funnel bars on CLI. Changing `Next run:` copy. Soak.
  \(N_{\mathrm{eff}}\). Unfreezing `webui/`. Rewriting the ledger.

## 5. Acceptance

- Unit: a method row with `kind_label` prints
  `Revision: c_2 · method · momentum_12_1 — 12-1 momentum · window=21`.
- Unit: missing/empty `revisions` omits `Revision:`.
- Unit: `replay_view` includes `revisions` as a list.
- `python3 -m pytest -m "not e2e and not llm" --ignore=tests/integration`
  and `python3 -m pytest tests/e2e -m e2e`.
