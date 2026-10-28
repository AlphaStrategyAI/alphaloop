"""The Windows GUI script registers the thickened-bar gaps from acceptance PR #161.

The acceptance doc itself stays on that docs PR. This test only locks the
script and workflow entries that CI will execute.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E2E_PATH = ROOT / "apps" / "desktop" / "e2e" / "windows_gui_e2e.py"
UI_PATH = ROOT / "apps" / "desktop" / "src" / "i18n" / "uiMessages.ts"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "desktop-release-windows.yml"

SPEC = importlib.util.spec_from_file_location("windows_gui_e2e", E2E_PATH)
assert SPEC and SPEC.loader
e2e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e2e)


def test_new_steps_are_registered_for_ci() -> None:
    text = E2E_PATH.read_text(encoding="utf-8")
    for slug in ("en-time-examples", "en-methods-coverage", "no-source-n3", "llm-settings"):
        assert f'"{slug}"' in text
        assert f"step_{slug.replace('-', '_')}" in text


def test_slot_and_n3_copy_matches_the_ui() -> None:
    ui = UI_PATH.read_text(encoding="utf-8")
    assert e2e.N3_EN in ui
    assert e2e.N3_ZH in ui
    assert e2e.EN_METHODS in ui
    assert e2e.EN_COVERAGE in ui
    assert "12 hours, or 30 minutes" in ui
    assert e2e.HOURS_PROMPT in ui
    assert e2e.METHODS_PROMPT in ui
    assert e2e.COVERAGE_PROMPT in ui
    assert "I couldn't understand" in e2e.APOLOGY_MARKERS[0]
    assert "LLM settings are not ready" not in ui


def test_llm_settings_wait_reads_the_non_secret_fields(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "uiLanguage": "en",
                "llmBaseUrl": e2e.LLM_REMOTE_URL,
                "llmModel": e2e.LLM_MODEL,
                "llmPrivacyAcknowledged": True,
            }
        ),
        encoding="utf-8",
    )
    loaded = e2e._wait_llm_settings(tmp_path)
    assert loaded["llmBaseUrl"] == e2e.LLM_REMOTE_URL
    assert e2e.LLM_API_KEY not in json.dumps(loaded)
    assert "llm-api-key" not in json.dumps(loaded)


def test_apology_marker_fails_the_slot_step() -> None:
    try:
        e2e.assert_no_apology("I couldn't understand that. How much effective research time")
    except AssertionError as error:
        assert "apology" in str(error)
    else:
        raise AssertionError("expected an apology to fail")


def test_windows_e2e_step_timeout_covers_the_added_flow() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    gui = workflow.split("Windows GUI end-to-end", 1)[1].split("shell:", 1)[0]
    assert "timeout-minutes: 30" in gui
    job = workflow.split("windows-e2e:", 1)[1].split("steps:", 1)[0]
    assert "timeout-minutes: 60" in job
