from __future__ import annotations

from importlib.resources import files

from alphaloop.runtime.preflight import HOST_CONSTRAINT


def _skill_text() -> str:
    return files("alphaloop.skills.overnight-lab").joinpath("SKILL.md").read_text(
        encoding="utf-8"
    )


def test_skill_is_packaged_markdown():
    text = _skill_text()
    assert text.startswith("---")
    assert "name: overnight-lab" in text
    assert "FOUND" in text
    assert "NO_EVIDENCE" in text
    assert "INCONCLUSIVE" in text


def test_skill_teaches_submit_and_poll_not_block():
    text = _skill_text()
    lowered = text.lower()
    assert "alphaloop start" in lowered
    assert "alphaloop submit" in lowered
    assert "alphaloop status" in lowered
    assert "alphaloop status RUN_ID --json" in text
    assert "poll" in lowered
    assert "do not block" in lowered or "do not keep" in lowered
    assert "Submit" in text or "YAML" in text


def test_skill_forbids_alpha_claims_and_gate_overrides():
    text = _skill_text().lower()
    assert "do not claim alpha" in text or "must not claim alpha" in text
    assert "cannot override" in text or "must not override" in text
    assert "hard gate" in text
    assert "human" in text and "export" in text


def test_skill_discloses_host_constraint_and_rejects_overnight_mcp():
    text = _skill_text()
    assert "remain awake" in text.lower() or HOST_CONSTRAINT.split(".")[0] in text
    lowered = text.lower()
    assert "mcp" in lowered
    assert "overnight" in lowered
    assert "must not" in lowered or "do not" in lowered
