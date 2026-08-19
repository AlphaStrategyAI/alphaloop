# Overnight Lab Phase 6 — Agent Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local Agent Skill that teaches coding agents the overnight-lab workflow: preflight, submit, poll, interpret `FOUND` / `NO_EVIDENCE` / `INCONCLUSIVE`, and never claim alpha or export without a human.

**Architecture:** A packaged Markdown skill under `src/alphaloop/skills/overnight-lab/`. It is workflow guidance, not an evidence engine and not an MCP server. Agents use the existing CLI / Job API. No tool call stays open overnight.

**Tech Stack:** Markdown skill file, `importlib.resources`, pytest. No new runtime dependency.

## Global Constraints

- Skill is guidance only. It cannot mint `FOUND` or override gates.
- Poll `alphaloop status` / `GET /v1/jobs/{id}`; do not block a tool call for hours.
- MCP is out of scope. Do not tell agents to keep an MCP session open overnight.
- Export requires `FOUND` and explicit human approval.
- Economic-logic changes need a new spec and human approval; do not silently mutate a running job.
- Source of truth: requirements §10.3 / §10.4 and design Phase 6.

## File Structure

- Create: `src/alphaloop/skills/__init__.py`
- Create: `src/alphaloop/skills/overnight-lab/__init__.py`
- Create: `src/alphaloop/skills/overnight-lab/SKILL.md`
- Test: `tests/skills/test_overnight_lab_skill.py`
- Modify: `pyproject.toml` force-include SKILL.md
- Modify: design §5 Phase 6 and requirements §13

---

### Task 1: Packaged overnight-lab skill

**Files:**
- Create the skill package and `SKILL.md`
- Test: `tests/skills/test_overnight_lab_skill.py`

**Interfaces:**
- Skill YAML front matter: `name: overnight-lab`, description covering preflight/submit/poll/outcomes
- Body MUST include locked tokens `FOUND`, `NO_EVIDENCE`, `INCONCLUSIVE`
- Body MUST tell the agent to: write a ResearchSpec YAML; run `alphaloop start` if needed; `alphaloop submit --spec`; poll `alphaloop status`; disclose HOST_CONSTRAINT (host must remain awake)
- Body MUST forbid: claiming alpha after a failed gate; overriding hard gates; `export` without human confirmation; keeping an MCP/tool call open overnight; executing arbitrary generated Python
- Body MUST say method repairs may continue only when evidence is incomplete; economic changes are queued for a human
- Load via `importlib.resources.files("alphaloop.skills.overnight-lab").joinpath("SKILL.md")`

- [ ] Tests first (file missing → fail), then write SKILL.md, then commit `feat(skills): add local overnight-lab agent skill`

---

### Task 2: Docs and regression

- Design Phase 6 links this plan
- Requirements §13: items 1–5 done; item 6 is this plan
- `python3 -m pytest tests/ -m "not integration" -q`

- [ ] Commit `docs: point Phase 6 Agent Skill at the implementation plan`

---

## Self-review

1. Spec coverage: skill workflow, three outcomes, no overnight MCP, human export, no gate override.
2. Out of scope: MCP adapter implementation, AlphaStrategy consumer, hosted cloud.
