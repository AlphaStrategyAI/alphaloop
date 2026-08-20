from __future__ import annotations

import subprocess
import sys
from importlib.resources import files
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from alphaloop.contracts.gates import HardGateName
from alphaloop.contracts.research_spec import ALLOWED_PROFILES
from alphaloop.protocol.dsl import DIRECTIONAL_SIGNAL_KINDS
from alphaloop.runtime.api import JobAPI
from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import DEFAULT_HOST, start_http_server
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from alphaloop.runtime.store import JobStore
from alphaloop.runtime.supervisor import Supervisor
from tests.runtime.test_supervisor import FakeWorker, _cached_spec


def test_packaged_assets_are_read_only_morning_copy():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert "/app.js" in html
    assert "FOUND" in html
    assert "NO_EVIDENCE" in html
    assert "INCONCLUSIVE" in html
    assert 'id="spec-yaml"' in html
    assert 'id="submit-job"' in html
    assert 'id="preview-protocol"' in html
    assert 'id="protocol-preview"' in html
    assert "disabled" in html
    assert "dataset.runId" in script
    assert "application/yaml" in script
    assert "setInterval" in script
    assert "/v1/jobs" in script
    assert "override" not in script.lower()
    assert "hard_gates=" not in script


def test_packaged_help_and_evidence_lines():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert 'id="help"' in html
    assert 'id="help-no-alpha"' in html
    assert "This console does not claim alpha or future profitability." in html
    assert 'id="help-status"' in html
    assert (
        "Job status (queued, running, completed, failed, cancelled) is not the research conclusion."
        in html
    )
    assert 'id="help-host"' in html
    assert HOST_CONSTRAINT in html
    assert 'id="help-found"' in html
    assert (
        "FOUND means every required hard gate is present and passed. It is not a promise of alpha."
        in html
    )
    assert "job.evidence_lines" in script
    assert "/v1/jobs/preview" in script
    assert "override" not in script.lower()


def test_packaged_example_layout_and_job_controls():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="load-example"' in html
    assert 'id="before-bed"' in html
    assert 'id="morning"' in html
    assert 'id="cancel-job"' in html
    assert 'id="resume-job"' in html
    assert "statement: 12-1 momentum works in US large caps net of costs" in script
    assert "signal_mechanism: momentum_12_1" in script
    assert "dataset_id: ds_example" in script
    assert 'postJobAction("cancel")' in script
    assert 'postJobAction("resume")' in script
    assert "dataset.runId" in script
    assert "override" not in script.lower()
    assert "56rem" in css or "min-width: 56rem" in css


def test_packaged_guided_form_preview_grid_and_job_cards():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="hypothesis-form"' in html
    assert 'id="field-statement"' in html
    assert 'id="field-economic-logic"' in html
    assert 'id="field-signal-mechanism"' in html
    assert 'id="field-market-scope"' in html
    assert 'id="field-market-profile"' in html
    assert 'id="field-benchmark"' in html
    assert 'id="field-hard-gates"' in html
    assert 'id="field-seed"' in html
    assert 'id="field-time-budget"' in html
    assert 'id="field-cost-budget"' in html
    assert 'id="field-dataset-id"' in html
    assert 'id="field-dataset-sha256"' in html
    assert html.find('id="field-cost-budget"') < html.find('id="field-dataset-id"')
    assert html.find('id="field-dataset-id"') < html.find('id="field-dataset-sha256"')
    assert 'id="field-dataset-file"' in html
    assert html.find('id="field-dataset-sha256"') < html.find('id="field-dataset-file"')
    for kind in DIRECTIONAL_SIGNAL_KINDS:
        assert f'value="{kind}"' in html
    assert 'value="parkinson_hist_vol"' not in html
    assert 'value="obv_slope"' not in html
    for profile in ALLOWED_PROFILES:
        assert f'value="{profile}"' in html
    for gate in HardGateName:
        assert f'value="{gate.value}"' in html
    assert "dataset.runId" in script
    assert "protocol-grid" in script
    assert "JSON.stringify(body.method_parameter_grid)" not in script
    assert "job.hypothesis" in script
    assert "n_trials" in script
    assert 'id="funnel-summary"' in html
    assert "failure_counts" in script
    assert "n_evaluated" in script
    assert "load-queued" in script
    assert "field-dataset-id" in script
    assert "field-dataset-sha256" in script
    load = script[script.find("function formToYaml") : script.find("function yamlToForm")]
    assert 'getElementById("field-dataset-id")' in load
    assert 'getElementById("field-dataset-sha256")' in load
    fill = script[script.find("function yamlToForm") : script.find("function formatGridRow")]
    assert 'getElementById("field-dataset-id")' in fill
    assert 'getElementById("field-dataset-sha256")' in fill
    assert "/v1/datasets" in script
    picker = script.find("function cacheDatasetFile")
    assert picker != -1
    picker_body = script[picker : picker + 1600]
    assert "/v1/datasets" in picker_body
    assert "submitJob" not in picker_body
    assert "field-dataset-id" in picker_body
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()
    assert "override" not in script.lower()
    assert "override" not in html.lower()
    assert "input:focus-visible" in css


def test_packaged_signal_select_groups_economic_families():
    from alphaloop.protocol.recommend import REVERSION_KINDS, TREND_KINDS

    html = files("alphaloop.webui.static").joinpath("index.html").read_text(
        encoding="utf-8"
    )
    start = html.find('id="field-signal-mechanism"')
    select = html[start : html.find("</select>", start)]
    assert '<optgroup label="Trend">' in select
    assert '<optgroup label="Mean reversion">' in select
    assert '<optgroup label="Relative value">' in select
    trend = select.split('<optgroup label="Trend">')[1].split("</optgroup>")[0]
    revert = select.split('<optgroup label="Mean reversion">')[1].split("</optgroup>")[0]
    relative = select.split('<optgroup label="Relative value">')[1]
    for kind in TREND_KINDS:
        assert f'value="{kind}"' in trend
    for kind in REVERSION_KINDS:
        assert f'value="{kind}"' in revert
    assert 'value="pairs_spread"' in relative
    assert "momentum_12_1 — 12-1 momentum" in select
    assert "rsi — RSI" in select
    assert "pairs_spread — pairs spread" in select
    assert 'value="parkinson_hist_vol"' not in select
    assert 'value="obv_slope"' not in select


def test_packaged_hard_gates_keep_token_and_human_gloss():
    html = files("alphaloop.webui.static").joinpath("index.html").read_text(
        encoding="utf-8"
    )
    start = html.find('id="field-hard-gates"')
    fieldset = html[start : html.find("</fieldset>", start)]
    for gate in HardGateName:
        assert f'value="{gate.value}"' in fieldset
    assert "dsr — Deflated Sharpe Ratio" in fieldset
    assert "walk_forward — walk-forward OOS" in fieldset
    assert "vs_random — versus random" in fieldset
    assert "vs_buy_hold — versus buy-and-hold" in fieldset
    assert "vs_benchmark — versus benchmark" in fieldset
    assert "data_consistency — data consistency" in fieldset
    assert fieldset.count('type="checkbox"') == len(HardGateName)


def test_packaged_console_dataset_csv_accept():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert 'id="field-dataset-file"' in html
    assert ".csv" in html
    assert "CSV" in html or "csv" in html
    picker = script.find("function cacheDatasetFile")
    assert picker != -1
    assert "submitJob" not in script[picker : picker + 1600]
    assert HOST_CONSTRAINT in html


def test_packaged_before_bed_groups_and_yaml_fold():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert html.find('id="group-hypothesis"') < html.find('id="group-market"')
    assert html.find('id="group-market"') < html.find('id="group-run"')
    assert html.find('id="group-run"') < html.find('id="group-dataset"')
    assert html.find('id="group-dataset"') < html.find('id="field-hard-gates"')
    assert html.find('id="spec-yaml-fold"') < html.find('id="spec-yaml"')
    assert html.find('id="spec-yaml"') < html.find('id="load-example"')
    assert ">Research spec (YAML)<" in html
    assert '<details id="spec-yaml-fold">' in html
    assert ".form-group" in css
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html
    assert "override" not in html.lower()


def test_packaged_queued_followup_auto_preview():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    load_at = script.find("function loadQueuedHypothesis")
    example_at = script.find("const EXAMPLE_SPEC")
    assert load_at != -1
    assert example_at != -1
    body = script[load_at:example_at]
    assert "previewProtocol()" in body
    assert "submitJob()" not in body
    assert "dataset" in body
    assert "time_budget_s" in body
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_funnel_bars():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="funnel-bars"' in html
    assert "funnel-stack" in script
    assert "funnel-seg" in script
    assert "dataset.pct" in script
    assert "incomplete:" in script
    assert "funnel-fail-fill" in script
    assert ".funnel-stack" in css
    assert '.funnel-seg[data-key="passed"]' in css
    assert '.funnel-seg[data-key="failed"]' in css
    assert '.funnel-seg[data-key="incomplete"]' in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_search_progress():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="search-progress"' in html
    assert "search: " in script
    assert "search-progress-fill" in script
    assert "planned_n_trials" in script
    assert ".search-progress" in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_morning_lead_and_job_funnel():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert "fillFunnelStack" in script
    assert "job-funnel" in script
    assert "aria-current" in script
    assert "detail.hidden" in script
    assert ".job-funnel .funnel-stack" in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_qualifying_candidates():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    assert 'id="qualifying"' in html
    assert html.find('id="qualifying"') < html.find('id="evidence"')
    assert "qualifying_candidates" in script
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_console_asb_export():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="export-status"' in html
    assert "export-asb" in script
    assert "/export" in script
    assert "exported_path" in script
    assert "export_handoff" in script
    assert "#export-status" in css
    assert "pre-wrap" in css
    assert html.find('id="handoff"') < html.find('id="export-status"')
    assert html.find('id="export-status"') < html.find('id="job-status"')
    assert "currentRunId !== runId" in script
    assert "#handoff .export-asb" in css
    assert '#verdict[data-outcome="FOUND"] #handoff .export-asb' in css
    assert "var(--accent)" in css
    assert "http" not in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_console_morning_report():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="report"' in html
    assert html.find('id="stop-reason"') < html.find('id="report"')
    assert html.find('id="recovery-attempts"') < html.find('id="cancel-job"')
    assert html.find('id="cancel-job"') < html.find('id="resume-job"')
    assert html.find('id="resume-job"') < html.find('id="report"')
    assert html.find('id="report"') < html.find('id="qualifying"')
    assert "report_markdown" in script
    assert "fillReport" in script
    assert "grid-template-columns" in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_console_lifecycle_chrome():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="cancel-job"' in html
    assert 'id="resume-job"' in html
    assert "#cancel-job" in css
    assert "#resume-job" in css
    cancel_rule = css.find("#cancel-job {")
    resume_rule = css.rfind("#resume-job {")
    assert cancel_rule != -1
    assert resume_rule != -1
    cancel_block = css[cancel_rule : css.find("}", cancel_rule)]
    resume_block = css[resume_rule : css.find("}", resume_rule)]
    assert "var(--focus)" in cancel_block
    assert "var(--accent)" not in cancel_block
    assert "var(--warn)" in resume_block
    assert "var(--accent)" not in resume_block
    chrome = css[css.find("#cancel-job") : css.find("}", css.find("#cancel-job"))]
    assert "var(--ink)" in chrome
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html


def test_packaged_console_preview_chrome():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="preview-protocol"' in html
    preview_rule = css.find("#preview-protocol {")
    assert preview_rule != -1
    preview_block = css[preview_rule : css.find("}", preview_rule)]
    assert "var(--ink)" in preview_block
    assert "var(--focus)" in preview_block
    assert "var(--accent)" not in preview_block
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html


def test_packaged_console_freeze_chrome():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="submit-job"' in html
    freeze_rule = css.find("#submit-job {")
    assert freeze_rule != -1
    freeze_block = css[freeze_rule : css.find("}", freeze_rule)]
    assert "var(--ink)" in freeze_block
    assert "var(--accent)" in freeze_block
    assert "var(--focus)" not in freeze_block
    assert "var(--warn)" not in freeze_block
    assert "#16352c" not in freeze_block
    assert "#2f6b55" not in freeze_block
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html


def test_packaged_console_preview_card():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="protocol-preview"' in html
    assert "preview-n-trials" in script
    assert "seed:" in script
    assert "time_budget_s:" in script
    assert "cost_budget_usd:" in script
    card = css.find("#protocol-preview:not(:empty)")
    assert card != -1
    card_block = css[card : css.find("}", card)]
    assert "var(--ink)" in card_block
    assert "var(--focus)" in card_block
    assert "var(--accent)" not in card_block
    n_rule = css.find("#preview-n-trials")
    assert n_rule != -1
    n_block = css[n_rule : css.find("}", n_rule)]
    assert "var(--focus)" in n_block
    assert "var(--accent)" not in n_block
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_console_load_chrome():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="load-example"' in html
    load_rule = css.find("#load-example {")
    assert load_rule != -1
    load_block = css[load_rule : css.find("}", load_rule)]
    assert "var(--ink)" in load_block
    assert "var(--fg)" in load_block
    assert "var(--line)" in load_block
    assert "var(--accent)" not in load_block
    assert "var(--warn)" not in load_block
    assert "var(--focus)" not in load_block
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html


def test_packaged_console_replay_report():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="replay-job"' in html
    assert html.find('id="resume-job"') < html.find('id="replay-job"')
    assert html.find('id="replay-job"') < html.find('id="report"')
    assert 'postJobAction("replay")' in script
    replay_rule = css.find("#replay-job {")
    assert replay_rule != -1 or "#replay-job" in css
    block_start = css.find("#replay-job")
    assert block_start != -1
    block = css[block_start : css.find("}", block_start)]
    assert "var(--accent)" not in block
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_packaged_example_dataset_matches_load_example_hash():
    from alphaloop.contracts.artifacts import hash_bytes

    root = files("alphaloop.webui.static")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    blob = files("alphaloop.runtime.example_dataset").joinpath("prices.parquet").read_bytes()
    digest = hash_bytes(blob)
    assert "dataset_id: ds_example" in script
    assert f"sha256: {digest}" in script
    assert HOST_CONSTRAINT in root.joinpath("index.html").read_text(encoding="utf-8")
    assert "override" not in script.lower()


def test_packaged_empty_morning_cue():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    locked = (
        "No overnight job yet. Load example, then Preview protocol, then "
        "Freeze and submit. This console does not claim alpha or future "
        "profitability."
    )
    assert 'id="empty-morning"' in html
    assert html.find('id="job-list"') < html.find('id="empty-morning"')
    assert html.find('id="empty-morning"') < html.find('id="detail"')
    assert locked in html
    empty_block = html[html.find('id="empty-morning"') : html.find('id="detail"')]
    assert "<button" not in empty_block.lower()
    assert HOST_CONSTRAINT not in empty_block
    load = script[
        script.find("async function loadJobs") : script.find("let previewedYaml")
    ]
    assert 'getElementById("empty-morning")' in load
    assert ".hidden" in load
    assert "jobs.length" in load
    assert "#empty-morning" in css
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_prd_section_13_does_not_list_phases_8_11_as_remaining():
    from pathlib import Path

    text = Path("docs/requirements/product-positioning-requirements.md").read_text(
        encoding="utf-8"
    )
    section = text.split("## 13. Implementation decomposition")[1]
    assert "Remaining first-release gaps are protocol gate returns" not in section
    assert "Phases 8–11 shipped" in section
    assert "soak" in section.lower()
    assert "N_{\\mathrm{eff}}" in section
    assert "n_trials" in section
    assert "MCP" in section
    assert "historical" in section.lower()


def test_refactor_remaining_work_pointer_is_historical():
    from pathlib import Path

    text = Path("docs/plans/overnight-research-lab-refactor.md").read_text(
        encoding="utf-8"
    )
    assert "Remaining first-release work is specified in" not in text
    assert "Phases 8–11 shipped" in text


def test_roadmap_remaining_does_not_list_shipped_preview_as_unfinished():
    from pathlib import Path

    text = Path("ROADMAP.md").read_text(encoding="utf-8")
    remaining = text.split("## Remaining work")[1].split("## Version note")[0]
    assert "Protocol preview before freeze" not in remaining
    assert "Qualifying-candidate tables" not in remaining
    assert "funnel visualization" not in remaining
    assert "N_{\\mathrm{eff}}" in remaining
    assert "n_trials" in remaining
    assert "soak" in remaining.lower()
    assert "MCP" in remaining
    assert "cloud" in remaining.lower()


def test_packaged_console_overnight_liveness():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="worker-heartbeat"' in html
    assert html.find('id="job-status"') < html.find('id="worker-heartbeat"')
    assert "Worker heartbeat:" in script
    assert "verdict.dataset.status" in script
    assert "overnight-pulse" in css
    assert 'data-status="running"' in css
    assert "prefers-reduced-motion" in css
    assert "animation: none" in css
    assert "http" not in css
    assert "override" not in script.lower()


def test_packaged_console_failed_recovery_surface():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="job-error"' in html
    assert html.find('id="worker-heartbeat"') < html.find('id="job-error"')
    assert html.find('id="job-error"') < html.find('id="recovery-attempts"')
    assert "Worker error:" in script
    assert "Recovery attempts:" in script
    assert "job-recovery" in script
    assert "recovery: " in script
    assert 'data-status="failed"' in css
    assert "overnight-pulse" in css
    failed = css[css.find('data-status="failed"') :]
    assert "overnight-pulse" not in failed.split("@")[0]
    assert "http" not in css
    assert "override" not in script.lower()


def test_packaged_console_keyboard_preview_then_freeze():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="keyboard-hint"' in html
    assert html.find('id="submit-job"') < html.find('id="keyboard-hint"')
    assert "Ctrl/Cmd+Enter: Preview, then Freeze." in html
    assert 'addEventListener("keydown"' in script
    assert "ctrlKey" in script
    assert "metaKey" in script
    assert "previewProtocol()" in script
    assert "submitJob()" in script
    assert "#keyboard-hint" in css
    assert "http" not in css
    assert "override" not in script.lower()


def test_packaged_console_job_list_keys():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="job-keys-hint"' in html
    assert "j/k or arrows move between jobs." in html
    assert "ArrowDown" in script
    assert "ArrowUp" in script
    assert "showJob(" in script
    assert "TEXTAREA" in script
    assert "INPUT" in script
    assert "SELECT" in script
    assert "#job-keys-hint" in css
    assert "http" not in css
    assert "override" not in script.lower()


def test_packaged_console_morning_verdict_stage():
    root = files("alphaloop.webui.static")
    html = root.joinpath("index.html").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    css = root.joinpath("styles.css").read_text(encoding="utf-8")
    assert 'id="verdict"' in html
    assert 'id="outcome-gloss"' in html
    assert html.find('id="outcome"') < html.find('id="outcome-gloss"')
    assert html.find('id="outcome-gloss"') < html.find('id="primary-evidence"')
    assert html.find('id="primary-evidence"') < html.find('id="stop-reason"')
    assert html.find('id="stop-reason"') < html.find('id="job-status"')
    assert html.find('id="stop-reason"') < html.find('id="next-step"')
    assert html.find('id="next-step"') < html.find('id="job-status"')
    assert html.find('id="next-step"') < html.find('id="handoff"')
    assert html.find('id="handoff"') < html.find('id="job-status"')
    assert "fillHandoff" in script
    assert "Qualifying:" in script
    assert "fillNextStep" in script
    assert "Next run:" in script
    assert "fillPrimaryEvidence" in script
    assert "Primary evidence:" in script
    assert 'id="help-no-evidence"' in html
    assert 'id="help-inconclusive"' in html
    assert (
        "NO_EVIDENCE means a required hard gate failed. It is not a promise that alpha does not exist."
        in html
    )
    assert (
        "INCONCLUSIVE means the evidence set is incomplete. Missing diagnostics cannot produce FOUND."
        in html
    )
    assert "fillOutcomeGloss" in script
    assert "help-found" in script
    assert "repeating-linear-gradient" in css
    assert "font-variant-numeric" in css
    assert "clamp(" in css
    assert "#next-step .load-queued" in css
    no_evidence_load = (
        '#verdict[data-outcome="NO_EVIDENCE"] #next-step .load-queued'
    )
    assert no_evidence_load in css
    block_start = css.find(no_evidence_load)
    block = css[block_start : css.find("}", block_start)]
    assert "var(--warn)" in block
    assert "var(--accent)" not in block
    assert "http" not in css.lower()
    assert HOST_CONSTRAINT in html
    assert "override" not in script.lower()


def test_static_package_loads_without_fastapi():
    """Morning assets must load even when FastAPI is not installed."""
    code = r"""
import sys
from importlib.abc import MetaPathFinder
from importlib.resources import files


class BlockFastAPI(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "fastapi" or fullname.startswith("fastapi."):
            raise ModuleNotFoundError("No module named 'fastapi'")
        return None


sys.meta_path.insert(0, BlockFastAPI())
for name in list(sys.modules):
    if name == "fastapi" or name.startswith("fastapi.") or name.startswith("alphaloop.webui"):
        del sys.modules[name]

html = files("alphaloop.webui.static").joinpath("index.html").read_text(encoding="utf-8")
assert "FOUND" in html
assert "NO_EVIDENCE" in html
assert "INCONCLUSIVE" in html
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _server(tmp_path):
    store = JobStore(tmp_path / "state.db", tmp_path)
    worker = FakeWorker()
    sup = Supervisor(store, tmp_path, worker, heartbeat_timeout_s=60.0)
    api = JobAPI(store, sup, tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def test_root_serves_packaged_html(tmp_path):
    server, base = _server(tmp_path)
    try:
        with urlopen(base + "/") as response:
            assert response.headers.get_content_type() == "text/html"
            body = response.read().decode("utf-8")
        assert "FOUND" in body
        assert "NO_EVIDENCE" in body
        assert "INCONCLUSIVE" in body
        assert "/app.js" in body
        assert "spec-yaml" in body
        assert 'id="help"' in body
        assert HOST_CONSTRAINT in body
    finally:
        server.shutdown()


def test_static_javascript_and_css(tmp_path):
    server, base = _server(tmp_path)
    try:
        with urlopen(base + "/app.js") as response:
            assert "javascript" in response.headers.get_content_type()
            script = response.read().decode("utf-8")
        assert "/v1/jobs" in script
        assert "override" not in script.lower()
        with urlopen(base + "/styles.css") as response:
            assert response.headers.get_content_type() == "text/css"
            css = response.read().decode("utf-8")
        assert '[data-outcome="FOUND"]' in css
        assert '[data-outcome="NO_EVIDENCE"]' in css
        assert '[data-outcome="INCONCLUSIVE"]' in css
    finally:
        server.shutdown()


def test_list_jobs_http(tmp_path):
    server, base = _server(tmp_path)
    client = JobClient(base)
    try:
        created = client.create_run(_cached_spec())
        listed = client.list_jobs()
        assert listed["jobs"][0]["run_id"] == created["run_id"]
        assert "research_outcome" in listed["jobs"][0]
        assert listed["jobs"][0]["evidence_lines"] == []
    finally:
        server.shutdown()


@pytest.mark.parametrize("method", ["PUT", "PATCH", "POST"])
def test_gate_override_is_not_found(tmp_path, method):
    server, base = _server(tmp_path)
    try:
        request = Request(
            base + "/v1/jobs/j_x/gates",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(request)
        assert exc.value.code == 404
    finally:
        server.shutdown()


def test_static_path_traversal_rejected(tmp_path):
    server, base = _server(tmp_path)
    try:
        with pytest.raises(HTTPError) as exc:
            urlopen(base + "/../runtime/api.py")
        assert exc.value.code == 404
    finally:
        server.shutdown()
