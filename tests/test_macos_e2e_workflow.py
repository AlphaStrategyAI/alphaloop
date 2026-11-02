"""macos-e2e matches the windows-e2e gate: PR runs it, push does not, release opts in."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAC_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release-macos.yml"
WIN_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release-windows.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release.yml"
MAC_E2E = ROOT / "apps" / "desktop" / "e2e" / "macos_gui_e2e.py"
LIB_RS = ROOT / "apps" / "desktop" / "src-tauri" / "src" / "lib.rs"
CARGO = ROOT / "apps" / "desktop" / "src-tauri" / "Cargo.toml"

SPEC = importlib.util.spec_from_file_location("macos_gui_e2e", MAC_E2E)
assert SPEC and SPEC.loader
macos_e2e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(macos_e2e)


def test_macos_runner_is_macos_15_not_the_retired_image() -> None:
    workflow = MAC_WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: macos-14" not in workflow
    assert "macos-14" in workflow
    assert workflow.count("runs-on: macos-15") == 2


def test_macos_e2e_job_matches_windows_wiring() -> None:
    workflow = MAC_WORKFLOW.read_text(encoding="utf-8")
    assert "run_e2e:" in workflow
    assert "default: false" in workflow
    job = workflow.split("macos-e2e:", 1)[1].split("steps:", 1)[0]
    assert "needs: build-macos-bundle" in job
    assert "if: github.event_name == 'pull_request' || inputs.run_e2e" in job
    assert "runs-on: macos-15" in job
    assert "timeout-minutes: 60" in job
    windows = WIN_WORKFLOW.read_text(encoding="utf-8")
    windows_job = windows.split("windows-e2e:", 1)[1].split("steps:", 1)[0]
    assert "if: github.event_name == 'pull_request' || inputs.run_e2e" in windows_job
    body = workflow.split("macos-e2e:", 1)[1]
    assert "timeout-minutes: 30" in body
    for env in (
        "ALPHALOOP_OFFLINE_MARKET_DATA",
        "ALPHALOOP_MAX_TRIALS",
        "ALPHALOOP_E2E_HOLD_RUNNING_SEC",
        "ALPHALOOP_REVIEWER",
        "ALPHALOOP_WEBDRIVER",
    ):
        assert env in body
    assert "macos_arm64.app.tar.gz" in body
    assert "macos-e2e-screenshots" in body
    assert "macos-e2e-logs" in body
    assert "macos_gui_e2e.py" in body
    assert "macos_installed_smoke.sh" in body


def test_release_workflow_opts_both_platforms_into_e2e() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    macos = text.split("macos:", 1)[1].split("windows:", 1)[0]
    windows = text.split("windows:", 1)[1].split("publish:", 1)[0]
    assert "desktop-release-macos.yml" in macos
    assert "run_e2e: true" in macos
    assert "run_e2e: true" in windows


def test_gui_script_registers_the_windows_trunk_steps() -> None:
    text = MAC_E2E.read_text(encoding="utf-8")
    for slug in (
        "install",
        "launch",
        "language",
        "secrets-keyring",
        "secrets-create",
        "secrets-unlock",
        "confirms",
        "blocked-run",
        "momentum-blocked",
        "family-buttons",
        "en-reference",
        "en-time-examples",
        "en-methods-coverage",
        "no-source-n3",
        "llm-settings",
        "dialogue-rollout",
        "conclusion",
        "delete-running",
        "persist",
        "uninstall",
    ):
        assert f'"{slug}"' in text
    for name in (
        "step_en_time_examples",
        "step_en_methods_coverage",
        "step_no_source_n3",
        "step_llm_settings",
        "step_dialogue_rollout",
    ):
        assert f"def {name}" in text
    assert "taskkill" not in text
    assert "MSEDGEDRIVER" not in text
    assert "ALPHALOOP_WEBDRIVER" in text


def test_webdriver_plugin_is_macos_only_and_opt_in() -> None:
    source = LIB_RS.read_text(encoding="utf-8")
    assert 'cfg(target_os = "macos")' in source
    assert 'std::env::var("ALPHALOOP_WEBDRIVER")' in source
    assert 'tauri_plugin_wdio_webdriver::init()' in source
    cargo = CARGO.read_text(encoding="utf-8")
    macos = cargo.split('[target.\'cfg(target_os = "macos")\'.dependencies]', 1)[1]
    macos = macos.split('[target.\'cfg(target_os = "windows")\'.dependencies]', 1)[0]
    assert 'tauri-plugin-wdio-webdriver = "1.5.1"' in macos


def test_process_match_uses_the_executable_basename() -> None:
    text = """
      10 /Applications/alphaloop.app/Contents/MacOS/alphaloop
      11 /Applications/alphaloop.app/Contents/Resources/engine/alphaloop-engine/alphaloop-engine
      12 /usr/bin/python3 apps/desktop/e2e/macos_gui_e2e.py
    """
    assert macos_e2e.pids_from_ps(text, "alphaloop", 12) == [10]
    assert macos_e2e.pids_from_ps(text, "alphaloop-engine", 12) == [11]
    assert macos_e2e.pids_from_ps(text, "python3", 12) == []
