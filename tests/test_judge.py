"""
Unit + integration tests for the alphaloop v0.6 LLM-as-judge evaluator.

Covers the 15 tests requested in the Coder task brief, plus a few
extras that the design doc § 4 names. Tests are split into two
modules: this file (no I/O, no real network) and integration tests
that exercise the full `alphaloop report` CLI.

The single most important test-design decision: **never make a real
HTTP call**. The `FakeLLMClient` (in tests/conftest.py) lets us inject
scripted responses and inspect what the diagnostic sent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import alphaloop
from alphaloop.cli import main as cli_main
from alphaloop.diagnostic import DimensionScore, LLMJudgeResult, llm_judge
from alphaloop.diagnostic.judge import run as run_judge_diag
from alphaloop.judge import (
    LLMJudgeClient,
    PROMPT_TEMPLATE,
    render_prompt,
)
from alphaloop.judge.client import LLMCallError, LLMConfigError
from alphaloop.judge.prompts import _yaml_load  # noqa: F401  (test it directly)

from conftest import GOOD_JUDGE_RESPONSE, FakeLLMClient

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(
    *,
    no_judge: bool = False,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    judge_base_url: str | None = None,
    judge_threshold: int = 7,
    seed: int = 0,
    output: str | None = None,
):
    """Build a minimal argparse.Namespace mimicking the `report` CLI."""
    import argparse

    return argparse.Namespace(
        no_judge=no_judge,
        judge_model=judge_model,
        judge_api_key=judge_api_key,
        judge_base_url=judge_base_url,
        judge_threshold=judge_threshold,
        seed=seed,
        output=output,
    )


def _good_response(score: int = 8) -> str:
    """JSON response with all three dimensions at the given score."""
    return json.dumps(
        {
            "readability": {"score": score, "reasoning": "r", "evidence": "e"},
            "decision_quality": {
                "score": score,
                "reasoning": "r",
                "evidence": "e",
            },
            "risk_disclosure": {
                "score": score,
                "reasoning": "r",
                "evidence": "e",
            },
        }
    )


# ===========================================================================
# 1. test_judge_env_vars_resolve
# ===========================================================================


def test_judge_env_vars_resolve(clean_env):
    """Env vars LLM_MODEL + LLM_API_KEY + LLM_BASE_URL resolve into config."""
    clean_env.setenv("LLM_MODEL", "gpt-test")
    clean_env.setenv("LLM_API_KEY", "sk-test")
    clean_env.setenv("LLM_BASE_URL", "https://example.test/v1")
    client = LLMJudgeClient.from_env_or_args()
    assert client.config.model == "gpt-test"
    assert client.config.api_key == "sk-test"
    assert client.config.base_url == "https://example.test/v1"


# ===========================================================================
# 2. test_judge_yaml_fallback
# ===========================================================================


def test_judge_yaml_fallback(clean_env, tmp_path):
    """LLM_JUDGE_CONFIG env var points to YAML with model/api_key/base_url."""
    yaml_path = tmp_path / "judge.yaml"
    yaml_path.write_text(
        "model: yaml-model\napi_key: yaml-key\nbase_url: https://yaml.test/v1\n",
        encoding="utf-8",
    )
    clean_env.setenv("LLM_JUDGE_CONFIG", str(yaml_path))
    client = LLMJudgeClient.from_env_or_args()
    assert client.config.model == "yaml-model"
    assert client.config.api_key == "yaml-key"
    assert client.config.base_url == "https://yaml.test/v1"


# ===========================================================================
# 3. test_judge_cli_flag_override
# ===========================================================================


def test_judge_cli_flag_override(clean_env):
    """CLI flags override env vars (resolution order: CLI > env > YAML)."""
    clean_env.setenv("LLM_MODEL", "env-model")
    clean_env.setenv("LLM_API_KEY", "env-key")
    client = LLMJudgeClient.from_env_or_args(
        model="cli-model", api_key="cli-key"
    )
    assert client.config.model == "cli-model"
    assert client.config.api_key == "cli-key"


# ===========================================================================
# 4. test_judge_yaml_backward_compat
# ===========================================================================


def test_judge_yaml_backward_compat(clean_env, tmp_path):
    """An old-style YAML with no api_key falls back to env vars for the key."""
    yaml_path = tmp_path / "judge_legacy.yaml"
    yaml_path.write_text("model: legacy-model\n", encoding="utf-8")
    clean_env.setenv("LLM_JUDGE_CONFIG", str(yaml_path))
    clean_env.setenv("LLM_API_KEY", "env-only-key")
    client = LLMJudgeClient.from_env_or_args()
    assert client.config.model == "legacy-model"
    assert client.config.api_key == "env-only-key"


# ===========================================================================
# 5. test_judge_missing_api_key_raises
# ===========================================================================


def test_judge_missing_api_key_raises(clean_env):
    """No model + no api_key raises LLMConfigError."""
    with pytest.raises(LLMConfigError):
        LLMJudgeClient.from_env_or_args()


def test_judge_missing_api_key_only_model_raises(clean_env):
    """Model set but api_key missing → still raises."""
    clean_env.setenv("LLM_MODEL", "only-model")
    with pytest.raises(LLMConfigError):
        LLMJudgeClient.from_env_or_args()


# ===========================================================================
# 6. test_judge_yaml_invalid_yaml
# ===========================================================================


def test_judge_yaml_invalid_yaml(clean_env, tmp_path):
    """A YAML with no 'key: value' pairs raises LLMConfigError on lookup."""
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text("# only comments\n\n", encoding="utf-8")
    clean_env.setenv("LLM_JUDGE_CONFIG", str(yaml_path))
    with pytest.raises(LLMConfigError):
        LLMJudgeClient.from_env_or_args()


# ===========================================================================
# 7. test_judge_yaml_ioerror
# ===========================================================================


def test_judge_yaml_ioerror(clean_env, tmp_path):
    """LLM_JUDGE_CONFIG pointing at a non-existent file raises config error."""
    missing = tmp_path / "nope.yaml"
    clean_env.setenv("LLM_JUDGE_CONFIG", str(missing))
    with pytest.raises(LLMConfigError):
        LLMJudgeClient.from_env_or_args()


# ===========================================================================
# 8. test_judge_yaml_empty_key
# ===========================================================================


def test_judge_yaml_empty_key(clean_env, tmp_path):
    """YAML with `model: ` (empty value) does not satisfy required key."""
    yaml_path = tmp_path / "empty.yaml"
    yaml_path.write_text("model: \napi_key: real-key\n", encoding="utf-8")
    clean_env.setenv("LLM_JUDGE_CONFIG", str(yaml_path))
    with pytest.raises(LLMConfigError):
        LLMJudgeClient.from_env_or_args()


# ===========================================================================
# 9. test_judge_prompt_renders_correctly
# ===========================================================================


def test_judge_prompt_renders_correctly():
    """render_prompt produces system + user with report text embedded."""
    report = "THIS IS THE BACKTEST REPORT"
    messages = render_prompt(report)
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    # The report must appear verbatim in the user message.
    assert "THIS IS THE BACKTEST REPORT" in messages[1]["content"]
    # The system prompt must describe the three dimensions.
    for dim in ("readability", "decision_quality", "risk_disclosure"):
        assert dim in messages[0]["content"]


# ===========================================================================
# 10. test_judge_response_parsed_correctly
# ===========================================================================


def test_judge_response_parsed_correctly(fake_llm_client):
    """A well-formed JSON response yields a populated LLMJudgeResult."""
    result = llm_judge("some report", client=fake_llm_client)
    assert result.error is None
    assert result.readability.score == 8
    assert result.decision_quality.score == 8
    assert result.risk_disclosure.score == 8
    assert result.readability.reasoning == "clear"
    assert result.model == "fake-llm-v1"
    assert result.prompt_tokens > 0
    assert result.completion_tokens > 0
    assert result.passes is True


# ===========================================================================
# 11. test_judge_dimensions_required
# ===========================================================================


def test_judge_dimensions_required():
    """Missing dimension in response → score=1 + reasoning=missing..."""
    fake = FakeLLMClient(
        responses=[
            '{"readability": {"score": 9, "reasoning": "ok", "evidence": "x"}}'
        ]
    )
    result = llm_judge("report", client=fake)
    assert result.readability.score == 9
    # Missing decision_quality and risk_disclosure default to 1.
    assert result.decision_quality.score == 1
    assert result.risk_disclosure.score == 1
    assert result.decision_quality.reasoning == "missing from response"
    assert result.passes is False


# ===========================================================================
# 12. test_judge_score_range
# ===========================================================================


def test_judge_score_range():
    """Scores out of [1,10] are clamped; result reflects clamped values."""
    fake = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "readability": {"score": 0, "reasoning": "r", "evidence": "e"},
                    "decision_quality": {
                        "score": 15,
                        "reasoning": "r",
                        "evidence": "e",
                    },
                    "risk_disclosure": {
                        "score": 7,
                        "reasoning": "r",
                        "evidence": "e",
                    },
                }
            )
        ]
    )
    result = llm_judge("report", client=fake, threshold=7)
    assert result.readability.score == 1  # clamped up from 0
    assert result.decision_quality.score == 10  # clamped down from 15
    assert result.risk_disclosure.score == 7
    # passes iff all >= threshold; readability clamped to 1 < 7 → fails.
    assert result.passes is False
    # overall_score is the min — clamped.
    assert result.overall_score == 1.0


def test_judge_threshold_is_per_dimension_not_average():
    """Threshold is per-dimension, not average (R3 design concern)."""
    fake = FakeLLMClient(responses=[_good_response(score=10)])
    # Force one to 7 by using a different response: re-call with custom
    # override response (separate fake).
    fake2 = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "readability": {"score": 10, "reasoning": "r", "evidence": "e"},
                    "decision_quality": {
                        "score": 10,
                        "reasoning": "r",
                        "evidence": "e",
                    },
                    "risk_disclosure": {
                        "score": 7,
                        "reasoning": "r",
                        "evidence": "e",
                    },
                }
            )
        ]
    )
    result = llm_judge("report", client=fake2, threshold=8)
    assert result.risk_disclosure.score == 7
    # Average would be (10+10+7)/3 = 9, but per-dim threshold=8 fails.
    assert result.passes is False
    assert result.overall_score == 7.0


def test_judge_passes_when_all_above_threshold():
    fake = FakeLLMClient(responses=[_good_response(score=9)])
    result = llm_judge("report", client=fake)
    assert result.passes is True


def test_judge_fails_when_one_below_threshold():
    fake = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "readability": {"score": 9, "reasoning": "r", "evidence": "e"},
                    "decision_quality": {
                        "score": 9,
                        "reasoning": "r",
                        "evidence": "e",
                    },
                    "risk_disclosure": {
                        "score": 5,
                        "reasoning": "r",
                        "evidence": "e",
                    },
                }
            )
        ]
    )
    result = llm_judge("report", client=fake)
    assert result.passes is False
    assert result.overall_score == 5.0


# ===========================================================================
# 13. test_judge_graceful_failure
# ===========================================================================


def test_judge_graceful_failure_invalid_json():
    """Non-JSON response yields error result, never raises."""
    fake = FakeLLMClient(responses=["this is not json at all"])
    result = llm_judge("report", client=fake)
    assert result.error is not None
    assert "parse" in result.error.lower()
    assert result.passes is False
    summary = result.summary()
    assert "SKIP" in summary


def test_judge_graceful_failure_client_raises():
    """When the client raises LLMCallError, result.error is set; no raise."""
    fake = FakeLLMClient(
        responses=[],
        raise_on_call=LLMCallError(500, "internal server error"),
    )
    result = llm_judge("report", client=fake)
    assert result.error is not None
    assert "500" in result.error or "internal" in result.error.lower()
    assert result.passes is False


def test_judge_graceful_failure_markdown_fenced_json():
    """JSON wrapped in ```json ... ``` fences is still parsed."""
    fenced = (
        "```json\n"
        + _good_response(score=9)
        + "\n```"
    )
    fake = FakeLLMClient(responses=[fenced])
    result = llm_judge("report", client=fake)
    assert result.error is None
    assert result.readability.score == 9
    assert result.passes is True


# ===========================================================================
# 14. test_report_no_judge_flag
# ===========================================================================


def test_report_no_judge_flag():
    """--no-judge flag means no Q7 section at all."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from alphaloop.cli import main; sys.exit(main(sys.argv[1:]))",
            "report",
            "--no-judge",
            "--seed",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "LLM_MODEL": "",
            "LLM_API_KEY": "",
            "LLM_BASE_URL": "",
            "PYTHONPATH": "src",
        },
        timeout=60,
    )
    assert proc.returncode == 0
    assert "## Q7" not in proc.stdout


# ===========================================================================
# 15. test_judge_skips_when_no_llm_config
# ===========================================================================


def test_judge_skips_when_no_llm_config(clean_env):
    """No LLM_MODEL/LLM_API_KEY/LLM_JUDGE_CONFIG → llm_judge returns SKIP."""
    result = llm_judge("any report")
    assert result.error is not None
    assert "config" in result.error.lower() or "LLM_MODEL" in result.error
    assert result.passes is False
    assert result.model == ""


# ===========================================================================
# Extras (not in the Coder brief, but called out by design doc § 4)
# ===========================================================================


def test_judge_latency_and_tokens_propagate():
    """FakeLLMClient with delay_ms=250 → result.latency_ms reflects it."""
    fake = FakeLLMClient(responses=[_good_response()], delay_ms=250)
    result = llm_judge("report", client=fake)
    assert result.latency_ms == 250
    assert result.prompt_tokens > 0
    assert result.completion_tokens > 0


def test_judge_propagates_model_name_from_client():
    """result.model reflects what the client returned, not what was requested."""
    fake = FakeLLMClient(
        responses=[_good_response()], model_name="actual-model-from-api"
    )
    result = llm_judge("report", client=fake, model="requested-model")
    assert result.model == "actual-model-from-api"


def test_judge_passes_full_report_through_to_prompt():
    """Known report string appears verbatim in FakeLLMClient.calls[0]."""
    fake = FakeLLMClient(responses=[_good_response()])
    sentinel = "MARKER-REPORT-CONTENT-XYZ-789"
    llm_judge(sentinel, client=fake)
    assert len(fake.calls) == 1
    user_msg = fake.calls[0]["messages"][-1]
    assert sentinel in user_msg["content"]


def test_judge_summary_format_includes_three_dimensions():
    """summary() must mention all three dimensions and verdict."""
    fake = FakeLLMClient(responses=[_good_response(score=9)])
    result = llm_judge("report", client=fake)
    summary = result.summary()
    for needle in ("verdict:", "Readability:", "Decision quality:", "Risk disclosure:"):
        assert needle in summary


def test_judge_default_threshold_is_7():
    """Default threshold is 7 per design doc § 1.2."""
    fake = FakeLLMClient(responses=[_good_response(score=7)])
    result = llm_judge("report", client=fake)
    assert result.threshold == 7
    assert result.passes is True

    fake2 = FakeLLMClient(responses=[_good_response(score=6)])
    result2 = llm_judge("report", client=fake2)
    assert result2.threshold == 7
    assert result2.passes is False


def test_judge_custom_threshold_propagates():
    """threshold=9 with all 8s fails."""
    fake = FakeLLMClient(responses=[_good_response(score=8)])
    result = llm_judge("report", client=fake, threshold=9)
    assert result.threshold == 9
    assert result.passes is False


def test_judge_summary_skipped_on_error():
    """When error is set, summary() reports SKIP."""
    fake = FakeLLMClient(responses=["not json"])
    result = llm_judge("report", client=fake)
    assert result.error is not None
    assert "SKIP" in result.summary()


def test_run_protocol_entrypoint_delegates():
    """`run(report)` from diagnostic.judge delegates to llm_judge()."""
    fake = FakeLLMClient(responses=[_good_response(score=9)])
    result = run_judge_diag("report text", client=fake)
    assert isinstance(result, LLMJudgeResult)
    assert result.passes is True


def test_yaml_load_handles_minimal_template():
    """The bundled template parses cleanly via _yaml_load."""
    parsed = _yaml_load(PROMPT_TEMPLATE)
    assert "system" in parsed
    assert "user" in parsed
    assert "{report_markdown}" in parsed["user"]


def test_yaml_load_rejects_empty():
    with pytest.raises(ValueError):
        _yaml_load("")


def test_yaml_load_rejects_missing_block_marker():
    with pytest.raises(ValueError):
        _yaml_load("system: not-a-literal-block\n")


def test_yaml_load_rejects_missing_key():
    """A YAML with only `system:` and no `user:` is rejected by render."""
    bad = "system: |\n  body text\n"
    with pytest.raises(ValueError):
        render_prompt("report", inline_template=bad)
    with pytest.raises(ValueError):
        render_prompt("report", inline_template="system: |\n  body\n")


def test_judge_module_is_exported_from_package():
    """alphaloop.llm_judge + LLMJudgeResult + DimensionScore exist."""
    assert hasattr(alphaloop, "llm_judge")
    assert hasattr(alphaloop, "LLMJudgeResult")
    assert hasattr(alphaloop, "DimensionScore")


def test_judge_diagnostic_module_exports():
    """alphaloop.diagnostic re-exports llm_judge + LLMJudgeResult + DimensionScore."""
    from alphaloop import diagnostic

    assert hasattr(diagnostic, "llm_judge")
    assert hasattr(diagnostic, "LLMJudgeResult")
    assert hasattr(diagnostic, "DimensionScore")
    assert "llm_judge" in diagnostic.__all__
    assert "LLMJudgeResult" in diagnostic.__all__
    assert "DimensionScore" in diagnostic.__all__


def test_cli_main_includes_judge_flags():
    """`alphaloop report --help` mentions the new judge flags."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from alphaloop.cli import main; sys.exit(main(sys.argv[1:]))",
            "report",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": "src"},
        timeout=30,
    )
    assert proc.returncode == 0
    for needle in ("--no-judge", "--judge-model", "--judge-api-key", "--judge-base-url"):
        assert needle in proc.stdout, f"missing help text for {needle}"


def test_report_q7_section_appears_when_skipped():
    """When LLM is not configured, the report still includes a Q7 section
    (with SKIP message), so the user can see Q7 was attempted.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from alphaloop.cli import main; sys.exit(main(sys.argv[1:]))",
            "report",
            "--seed",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "LLM_MODEL": "",
            "LLM_API_KEY": "",
            "LLM_BASE_URL": "",
            "PYTHONPATH": "src",
        },
        timeout=60,
    )
    assert proc.returncode == 0
    # Q7 section IS present (SKIPPED).
    assert "## Q7: LLM Judge" in proc.stdout
    assert "SKIPPED" in proc.stdout or "skipped" in proc.stdout.lower()
    # Quantitative sections unaffected.
    for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6"):
        assert q in proc.stdout


def test_dimension_score_clamping_at_construction():
    """DimensionScore clamps out-of-range scores silently."""
    a = DimensionScore(score=0)
    assert a.score == 1
    b = DimensionScore(score=15)
    assert b.score == 10
    # __post_init__ accepts non-int and falls back to default 1.
    c = DimensionScore(score="not-a-number")  # type: ignore[arg-type]
    assert c.score == 1


def test_llm_judge_result_passes_property():
    """passes is True iff all 3 dims >= threshold AND error is None."""
    r = LLMJudgeResult(
        readability=DimensionScore(score=8),
        decision_quality=DimensionScore(score=8),
        risk_disclosure=DimensionScore(score=8),
        threshold=7,
    )
    assert r.passes is True
    r.error = "boom"
    assert r.passes is False


def test_llm_judge_result_overall_score_is_min():
    r = LLMJudgeResult(
        readability=DimensionScore(score=10),
        decision_quality=DimensionScore(score=5),
        risk_disclosure=DimensionScore(score=9),
    )
    assert r.overall_score == 5.0


def test_judge_compatible_with_diagnostic_run_protocol():
    """The run() protocol wrapper preserves kwargs like threshold + model."""
    fake = FakeLLMClient(responses=[_good_response(score=10)])
    result = run_judge_diag(
        "report", client=fake, threshold=10
    )
    assert result.threshold == 10
    assert result.passes is True