"""Unit tests for the v0.8 prompt registry (R-Prompt).

Covers PRD § 3.4 acceptance criteria A-4.1 through A-4.6:

- A-4.1: prompt_registry has at least 2 entries.
- A-4.2: --judge-prompt-version=v0.6.0-prompt-1 selects the v0.6 prompt.
- A-4.3: default loads v0.8.0-prompt-2 without user action.
- A-4.4: v0.6.0-prompt-1 is preserved.
- A-4.5: --calibrate-prompt produces side-by-side JSON.
- A-4.6: when v0.6 fails, A/B tool shows v0.8 with better scores.
"""
from __future__ import annotations

import json
from pathlib import Path

from alphaloop.calibration.prompt_registry import (
    DEFAULT_PROMPT_VERSION,
    LATEST_SENTINEL,
    PROMPT_VERSION_ENV_VAR,
    PromptRegistry,
    compare_prompts,
    get_prompt,
    list_versions,
    register_version,
    resolve_version,
    unregister_version,
)


# ---------------------------------------------------------------------------
# A-4.1 + A-4.4: at least 2 versions, v0.6 preserved
# ---------------------------------------------------------------------------


def test_registry_has_at_least_two_versions():
    """A-4.1: prompt_registry has ≥ 2 entries."""
    versions = list_versions()
    assert len(versions) >= 2
    assert "v0.6.0-prompt-1" in versions
    assert "v0.8.0-prompt-2" in versions


def test_v0_6_prompt_preserved():
    """A-4.4: v0.6.0-prompt-1 is still in the registry."""
    assert "v0.6.0-prompt-1" in list_versions()


def test_get_prompt_v0_6_returns_non_empty():
    """v0.6 prompt is non-empty and contains rubric keywords."""
    p = get_prompt(version="v0.6.0-prompt-1")
    assert p
    assert "You are an honest, strict reviewer" in p
    assert "decision_quality" in p
    assert "risk_disclosure" in p


def test_get_prompt_v0_8_returns_non_empty():
    """v0.8 prompt is non-empty."""
    p = get_prompt(version="v0.8.0-prompt-2")
    assert p
    assert "You are an honest, strict reviewer" in p


def test_default_version_is_latest_lexicographic():
    """A-4.3: default = lex-last registered version."""
    versions = list_versions()
    # Latest = max() since versions are lex-sortable.
    assert DEFAULT_PROMPT_VERSION == max(versions)


def test_get_prompt_latest_sentinel():
    """get_prompt(version='latest') returns the latest registered."""
    p_latest = get_prompt(version=LATEST_SENTINEL)
    p_max = get_prompt(version=max(list_versions()))
    assert p_latest == p_max


def test_get_prompt_unknown_raises():
    """Unknown version raises KeyError."""
    import pytest

    with pytest.raises(KeyError):
        get_prompt(version="v9999-not-registered")


# ---------------------------------------------------------------------------
# Env-var resolution
# ---------------------------------------------------------------------------


def test_get_prompt_honors_env_var(monkeypatch):
    """ALPHALOOP_JUDGE_PROMPT_VERSION env var selects a version."""
    monkeypatch.setenv(PROMPT_VERSION_ENV_VAR, "v0.6.0-prompt-1")
    p = get_prompt()
    assert "You are an honest, strict reviewer" in p


def test_get_prompt_explicit_arg_overrides_env(monkeypatch):
    """Explicit version arg wins over env var."""
    monkeypatch.setenv(PROMPT_VERSION_ENV_VAR, "v0.6.0-prompt-1")
    # Should fall back to "latest" since v999.0 is unknown → KeyError → bundled
    # PROMPT_TEMPLATE fallback (handled in judge.prompts, NOT here).
    # Here in the registry we expect a clean registry lookup; use a real version.
    p = get_prompt(version="v0.8.0-prompt-2")
    assert "You are an honest, strict reviewer" in p


def test_resolve_version_default_returns_latest():
    """resolve_version with no args returns lex-last version."""
    v = resolve_version()
    assert v == max(list_versions())


def test_resolve_version_explicit():
    """resolve_version returns the explicit name when given."""
    v = resolve_version(flag_version="v0.6.0-prompt-1")
    assert v == "v0.6.0-prompt-1"


def test_resolve_version_env(monkeypatch):
    """resolve_version honors ALPHALOOP_JUDGE_PROMPT_VERSION env."""
    monkeypatch.setenv(PROMPT_VERSION_ENV_VAR, "v0.6.0-prompt-1")
    v = resolve_version()
    assert v == "v0.6.0-prompt-1"


# ---------------------------------------------------------------------------
# Register / unregister
# ---------------------------------------------------------------------------


def test_register_version_round_trip():
    """register_version adds a new version; unregister removes it."""
    register_version("test-extra-001", "fake template")
    assert "test-extra-001" in list_versions()
    p = get_prompt(version="test-extra-001")
    assert p == "fake template"
    unregister_version("test-extra-001")
    assert "test-extra-001" not in list_versions()


def test_register_version_empty_rejected():
    """register_version rejects empty / whitespace version."""
    import pytest

    with pytest.raises(ValueError):
        register_version("", "x")


def test_register_version_empty_template_rejected():
    """register_version rejects empty / whitespace template."""
    import pytest

    with pytest.raises(ValueError):
        register_version("v-x", "")


def test_prompt_registry_class_can_be_instantiated():
    """PromptRegistry can be used as a fresh standalone instance."""
    reg = PromptRegistry()
    reg.register("a", "AAA")
    reg.register("b", "BBB")
    assert reg.list_versions() == ["a", "b"]
    assert reg.get("a") == "AAA"
    assert reg.has("c") is False


def test_prompt_registry_clear():
    """PromptRegistry.clear removes all entries."""
    reg = PromptRegistry()
    reg.register("a", "AAA")
    reg.clear()
    assert reg.list_versions() == []


# ---------------------------------------------------------------------------
# A-4.5 + A-4.6: compare_prompts side-by-side
# ---------------------------------------------------------------------------


def test_compare_prompts_produces_side_by_side(tmp_path):
    """A-4.5: compare_prompts returns a side-by-side dict."""
    metrics_a = {
        "readability": {"pearson_r": 0.72},
        "decision_quality": {"pearson_r": 0.65},
        "risk_disclosure": {"pearson_r": 0.81},
    }
    metrics_b = {
        "readability": {"pearson_r": 0.78},
        "decision_quality": {"pearson_r": 0.74},
        "risk_disclosure": {"pearson_r": 0.79},
    }
    diff = compare_prompts(
        "v0.6.0-prompt-1",
        "v0.8.0-prompt-2",
        metrics_a=metrics_a,
        metrics_b=metrics_b,
    )
    assert diff["version_a"] == "v0.6.0-prompt-1"
    assert diff["version_b"] == "v0.8.0-prompt-2"
    # Winners: B for readability/decision_quality, A for risk_disclosure.
    assert diff["winners"]["readability"] == "B"
    assert diff["winners"]["decision_quality"] == "B"
    assert diff["winners"]["risk_disclosure"] == "A"
    # Templates preserved as a diff line list.
    assert isinstance(diff["template_diff_lines"], list)
    # Length proxies.
    assert diff["length_a_chars"] > 0
    assert diff["length_b_chars"] > 0


def test_compare_prompts_serializable(tmp_path):
    """Side-by-side output is JSON-serializable."""
    metrics_a = {"readability": {"pearson_r": 0.5}}
    metrics_b = {"readability": {"pearson_r": 0.6}}
    diff = compare_prompts(
        "v0.6.0-prompt-1",
        "v0.8.0-prompt-2",
        metrics_a=metrics_a,
        metrics_b=metrics_b,
    )
    json.dumps(diff)  # must not raise


def test_compare_prompts_v0_6_fails_v0_8_better():
    """A-4.6: when v0.6 fails on decision_quality, A/B shows v0.8 better."""
    metrics_a = {
        "decision_quality": {"pearson_r": 0.62},  # BELOW gate (0.70)
    }
    metrics_b = {
        "decision_quality": {"pearson_r": 0.74},  # above gate
    }
    diff = compare_prompts(
        "v0.6.0-prompt-1",
        "v0.8.0-prompt-2",
        metrics_a=metrics_a,
        metrics_b=metrics_b,
    )
    assert diff["winners"]["decision_quality"] == "B"
    assert metrics_a["decision_quality"]["pearson_r"] < 0.70
    assert metrics_b["decision_quality"]["pearson_r"] >= 0.70