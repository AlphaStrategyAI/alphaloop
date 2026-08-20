from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd
import pytest
import yaml

from alphaloop.contracts.artifacts import RunLayout, hash_bytes
from alphaloop.runtime.preflight import HOST_CONSTRAINT
from alphaloop.runtime.worker import find_running_worker_pid

pytestmark = pytest.mark.e2e

_OUTCOMES = ("FOUND", "NO_EVIDENCE", "INCONCLUSIVE")


def _write_dataset(data_dir: Path, columns=("AAPL", "MSFT", "SPY"), dataset_id="ds_e2e"):
    idx = pd.bdate_range("2018-01-01", periods=260)
    frame = pd.DataFrame(
        {name: 100.0 + pd.Series(range(260), index=idx, dtype=float) for name in columns}
    )
    path = Path(data_dir) / "datasets" / dataset_id / "prices.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    return {
        "dataset_id": dataset_id,
        "sha256": hash_bytes(path.read_bytes()),
    }


def _spec_yaml(dataset, **overrides) -> str:
    payload = {
        "statement": "12-1 momentum works in US large caps net of costs",
        "economic_logic": "past winners continue",
        "signal_mechanism": "momentum_12_1",
        "market_scope": "AAPL, MSFT",
        "market_profile": "us-equity-daily",
        "benchmark": "SPY",
        "hard_gates": ["dsr"],
        "seed": 7,
        "time_budget_s": 30,
        "cost_budget_usd": 1.0,
        "dataset": dataset,
    }
    payload.update(overrides)
    return yaml.safe_dump(payload)


def _cli(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alphaloop.cli.main", *args, "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def _open_morning(page, base_url: str) -> None:
    page.goto(base_url + "/", wait_until="domcontentloaded")
    page.wait_for_selector("#preview-protocol")
    page.wait_for_selector("#submit-job")


def _preview_yaml(page, yaml_text: str) -> None:
    page.fill("#spec-yaml", yaml_text)
    page.click("#preview-protocol")
    page.wait_for_function(
        """() => {
            const preview = (document.getElementById('protocol-preview').textContent || '');
            const errors = (document.getElementById('preflight-errors').textContent || '');
            return preview.indexOf('planned_n_trials') !== -1 || errors.length > 0;
        }""",
        timeout=10000,
    )


def _preview_then_submit(page, yaml_text: str) -> None:
    _preview_yaml(page, yaml_text)
    page.wait_for_function(
        "() => document.getElementById('submit-job') && !document.getElementById('submit-job').disabled",
        timeout=10000,
    )
    page.click("#submit-job")


def _first_run_id(page) -> str:
    page.wait_for_selector("#job-list button[data-run-id]", timeout=15000)
    run_id = page.locator("#job-list button").first.get_attribute("data-run-id")
    assert run_id
    return run_id


def _open_job_detail(page) -> None:
    page.locator("#job-list button").first.click()
    page.wait_for_function(
        """() => {
            const detail = document.getElementById('detail');
            const outcome = document.getElementById('outcome');
            return detail && !detail.hidden && (outcome.textContent || '').trim().length > 0;
        }""",
        timeout=10000,
    )


def _wait_list_outcome(page, timeout_ms: int = 60000) -> str:
    page.wait_for_function(
        """() => [...document.querySelectorAll('#job-list button')].some((button) =>
            /FOUND|NO_EVIDENCE|INCONCLUSIVE/.test(button.getAttribute('data-outcome') || ''))""",
        timeout=timeout_ms,
    )
    outcome = page.locator("#job-list button").first.get_attribute("data-outcome")
    assert outcome
    return outcome


def test_home_shows_promise_and_submit_form(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    body = page.content()
    assert "Submit in one minute" in body
    assert "FOUND" in body
    assert "NO_EVIDENCE" in body
    assert "INCONCLUSIVE" in body
    assert page.locator("#spec-yaml").count() == 1
    assert page.locator("#submit-job").count() == 1
    assert page.locator("#preview-protocol").count() == 1
    assert page.locator("#submit-job").is_disabled()
    assert page.locator("#load-example").count() == 1
    assert page.locator("#before-bed").count() == 1
    assert page.locator("#morning").count() == 1
    assert page.locator("#hypothesis-form").count() == 1
    assert page.locator("#field-signal-mechanism").count() == 1


def test_load_example_fills_spec_without_creating_a_job(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.click("#load-example")
    text = page.locator("#spec-yaml").input_value()
    assert "statement: 12-1 momentum works in US large caps net of costs" in text
    assert "signal_mechanism: momentum_12_1" in text
    assert page.locator("#submit-job").is_disabled()
    assert page.locator("#job-list button").count() == 0
    assert "target found" not in page.content()


def test_load_example_fills_guided_form(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.click("#load-example")
    assert page.locator("#field-signal-mechanism").input_value() == "momentum_12_1"
    assert page.locator("#field-market-profile").input_value() == "us-equity-daily"
    assert page.locator("#field-statement").input_value().startswith("12-1 momentum")
    assert page.locator("#submit-job").is_disabled()


def test_help_visible_without_opening_a_job(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    assert page.locator("#help-no-alpha").inner_text() == (
        "This console does not claim alpha or future profitability."
    )
    assert HOST_CONSTRAINT in page.locator("#help-host").inner_text()
    assert page.locator("#help-status").inner_text() == (
        "Job status (queued, running, completed, failed, cancelled) is not the research conclusion."
    )
    assert page.locator("#help-found").inner_text() == (
        "FOUND means every required hard gate is present and passed. It is not a promise of alpha."
    )
    assert "target found" not in page.content()


def test_invalid_yaml_shows_preflight_errors_without_job(real_daemon, browser_page):
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_yaml(page, _spec_yaml({"dataset_id": "x", "sha256": "0" * 64}, hard_gates=[]))
    page.wait_for_function(
        "() => (document.getElementById('preflight-errors').textContent || '').length > 0",
        timeout=10000,
    )
    assert page.locator("#job-list button").count() == 0


def test_parkinson_preview_shows_feature_error_without_job(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_yaml(page, _spec_yaml(dataset, signal_mechanism="parkinson_hist_vol"))
    page.wait_for_function(
        "() => (document.getElementById('preflight-errors').textContent || '').length > 0",
        timeout=10000,
    )
    text = page.locator("#preflight-errors").inner_text().lower()
    assert "feature" in text
    assert page.locator("#job-list button").count() == 0


def test_preview_does_not_create_a_job(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_yaml(page, _spec_yaml(dataset))
    assert "planned_n_trials" in page.locator("#protocol-preview").inner_text()
    assert page.locator("#protocol-grid li").count() >= 1
    assert page.locator("#job-list button").count() == 0
    assert not page.locator("#submit-job").is_disabled()


def test_editing_yaml_after_preview_disables_submit(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_yaml(page, _spec_yaml(dataset))
    assert not page.locator("#submit-job").is_disabled()
    page.fill("#spec-yaml", _spec_yaml(dataset, seed=8))
    assert page.locator("#submit-job").is_disabled()
    assert page.locator("#job-list button").count() == 0


def test_valid_submit_shows_host_constraint_and_job_row(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset))
    page.wait_for_function(
        f"() => (document.getElementById('host-constraint').textContent || '') === {json.dumps(HOST_CONSTRAINT)}",
        timeout=10000,
    )
    run_id = _first_run_id(page)
    assert run_id.startswith("j_")


def test_job_card_shows_hypothesis_and_n_trials(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset))
    page.wait_for_selector("#job-list button[data-run-id]", timeout=15000)
    card = page.locator("#job-list button").first
    assert "12-1 momentum works in US large caps net of costs" in card.inner_text()
    assert "n_trials" in card.inner_text()
    assert card.get_attribute("data-run-id").startswith("j_")


def test_load_queued_fills_editor_without_submitting(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset))
    run_id = _first_run_id(page)
    rec_path = Path(real_daemon["data_dir"]) / run_id / "recommendations.json"
    rec_path.write_text(
        json.dumps(
            {
                "queued_hypotheses": [
                    {
                        "queued_reason": "economic_change_queued",
                        "statement": "No evidence for momentum_12_1; try rsi. This is not a claim of alpha.",
                        "economic_logic": "Follow-up mechanism after momentum_12_1 found no evidence.",
                        "signal_mechanism": "rsi",
                        "market_scope": "AAPL, MSFT",
                        "market_profile": "us-equity-daily",
                        "benchmark": "SPY",
                        "hard_gates": ["dsr"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#job-list button[data-run-id]", timeout=15000)
    _open_job_detail(page)
    page.wait_for_selector("#queued button.load-queued", timeout=10000)
    page.locator("#queued button.load-queued").click()
    assert page.locator("#field-signal-mechanism").input_value() == "rsi"
    assert "signal_mechanism: rsi" in page.locator("#spec-yaml").input_value()
    assert page.locator("#submit-job").is_disabled()
    assert page.locator("#job-list button").count() == 1
    assert "target found" not in page.content()


def test_job_detail_while_running_or_later_legal_outcome(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset))
    page.wait_for_selector("#job-list button", timeout=15000)
    _open_job_detail(page)
    outcome = page.locator("#outcome").inner_text().strip()
    assert outcome in ("NONE",) + _OUTCOMES
    assert page.locator("#job-status").inner_text().startswith("Job status:")
    assert "12-1 momentum works in US large caps net of costs" in page.locator(
        "#hypothesis-statement"
    ).inner_text()
    meta = page.locator("#spec-meta").inner_text()
    assert "spec_id:" in meta
    assert "seed:" in meta
    assert "n_trials:" in meta
    assert "Stop reason:" in page.locator("#stop-reason").inner_text()
    assert "evaluated:" in page.locator("#funnel-summary").inner_text()
    assert "target found" not in page.content()


def test_terminal_outcome_matches_cli_status(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset, time_budget_s=30))
    outcome = _wait_list_outcome(page)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    status = _cli(real_daemon["data_dir"], "status", run_id)
    assert status.returncode == 0
    payload = json.loads(status.stdout)
    assert payload["research_outcome"] == outcome
    assert payload["research_outcome"] in _OUTCOMES
    _open_job_detail(page)
    assert page.locator("#outcome").inner_text().strip() == payload["research_outcome"]
    assert "target found" not in page.content()


def test_missing_columns_are_inconclusive_without_gates(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], columns=("MSFT", "SPY"), dataset_id="ds_nocol")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset))
    outcome = _wait_list_outcome(page)
    assert outcome == "INCONCLUSIVE"
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    assert not (layout.evidence / "gates.json").exists()
    _open_job_detail(page)
    assert page.locator("#outcome").inner_text().strip() == "INCONCLUSIVE"
    evidence = page.locator("#evidence").inner_text()
    assert "none" in evidence or evidence.strip() == "none"


def test_cancel_before_seal_is_inconclusive(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset, time_budget_s=3600))
    run_id = _first_run_id(page)
    cancelled = _cli(real_daemon["data_dir"], "cancel", run_id)
    assert cancelled.returncode == 0
    payload = json.loads(cancelled.stdout)
    assert payload["status"] == "cancelled"
    assert payload["research_outcome"] == "INCONCLUSIVE"
    page.wait_for_function(
        """() => [...document.querySelectorAll('#job-list button')].some((button) =>
            button.getAttribute('data-outcome') === 'INCONCLUSIVE')""",
        timeout=15000,
    )
    _open_job_detail(page)
    assert page.locator("#outcome").inner_text().strip() == "INCONCLUSIVE"


def test_cancel_from_console_before_seal_is_inconclusive(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset, time_budget_s=3600))
    page.wait_for_selector("#job-list button", timeout=15000)
    _open_job_detail(page)
    page.wait_for_selector("#cancel-job:not([hidden])", timeout=10000)
    page.click("#cancel-job")
    page.wait_for_function(
        """() => [...document.querySelectorAll('#job-list button')].some((button) =>
            button.getAttribute('data-outcome') === 'INCONCLUSIVE')""",
        timeout=15000,
    )
    assert page.locator("#job-list button").first.get_attribute("data-outcome") == (
        "INCONCLUSIVE"
    )
    assert page.locator("#outcome").inner_text().strip() == "INCONCLUSIVE"
    assert "target found" not in page.content()


def test_cancel_keeps_found_when_already_sealed(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset, time_budget_s=30))
    outcome = _wait_list_outcome(page)
    run_id = _first_run_id(page)
    if outcome != "FOUND":
        pytest.skip("shortened worker run did not seal FOUND")
    cancelled = _cli(real_daemon["data_dir"], "cancel", run_id)
    assert cancelled.returncode == 0
    page.wait_for_timeout(2500)
    _open_job_detail(page)
    assert page.locator("#outcome").inner_text().strip() == "FOUND"


def test_kill_worker_then_resume_shows_queued_or_running(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset, time_budget_s=3600))
    run_id = _first_run_id(page)
    deadline = time.time() + 20
    pid = None
    while time.time() < deadline:
        pid = find_running_worker_pid(run_id)
        if pid is not None:
            break
        time.sleep(0.1)
    if pid is None:
        pytest.skip("worker pid never appeared")
    os.kill(pid, signal.SIGKILL)
    resumed = _cli(real_daemon["data_dir"], "resume", run_id)
    assert resumed.returncode == 0
    payload = json.loads(resumed.stdout)
    assert payload["status"] in {"queued", "running"}
    page.wait_for_function(
        """(runId) => [...document.querySelectorAll('#job-list button')].some((button) =>
            button.getAttribute('data-run-id') === runId)""",
        arg=run_id,
        timeout=15000,
    )


def test_replay_rewrites_report_without_changing_page_outcome(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset, time_budget_s=30))
    outcome = _wait_list_outcome(page)
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    before = layout.report.read_text(encoding="utf-8") if layout.report.is_file() else ""
    replayed = _cli(real_daemon["data_dir"], "replay", run_id)
    assert replayed.returncode == 0
    assert layout.report.is_file()
    report = layout.report.read_text(encoding="utf-8")
    assert report != "" or before == ""
    assert "This report does not claim alpha or future profitability." in report
    assert "12-1 momentum works in US large caps net of costs" in report
    page.wait_for_timeout(2500)
    assert _wait_list_outcome(page, timeout_ms=5000) == outcome


def test_export_found_only(real_daemon, browser_page, tmp_path):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(page, _spec_yaml(dataset, time_budget_s=30))
    outcome = _wait_list_outcome(page)
    run_id = _first_run_id(page)
    dest = tmp_path / "out.asb"
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    candidate = "c_missing"
    if layout.trial_ledger.is_file():
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines():
            if line.strip():
                candidate = json.loads(line)["trial_id"]
                break
    exported = _cli(
        real_daemon["data_dir"],
        "export",
        candidate,
        "--run-id",
        run_id,
        "--output",
        str(dest),
    )
    if outcome == "FOUND":
        assert exported.returncode == 0
        assert dest.is_file()
    else:
        assert exported.returncode == 2
        assert not dest.exists()


def test_no_gate_override_in_page_or_http(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"])
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    html = page.content()
    script = urlopen(real_daemon["base_url"] + "/app.js").read().decode("utf-8")
    assert "override" not in html.lower()
    assert "override" not in script.lower()
    _preview_then_submit(page, _spec_yaml(dataset))
    run_id = _first_run_id(page)
    for method in ("PUT", "PATCH", "POST"):
        req = Request(
            f"{real_daemon['base_url']}/v1/jobs/{run_id}/gates",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req)
        assert exc.value.code == 404


def test_macd_walk_forward_job_records_regime_stable(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_macd_wf")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(
        page,
        _spec_yaml(
            dataset,
            statement="MACD crossover works in US large caps net of costs",
            signal_mechanism="macd",
            hard_gates=["walk_forward"],
            time_budget_s=60,
        ),
    )
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    gates_path = layout.evidence / "gates.json"
    assert gates_path.is_file()
    payload = json.loads(gates_path.read_text(encoding="utf-8"))
    rows = {row["name"]: row for row in payload["results"]}
    assert "walk_forward" in rows
    assert "regime_stable" in rows["walk_forward"]["detail"]
    assert isinstance(rows["walk_forward"]["detail"]["regime_stable"], bool)
    assert "oos_sharpe_median" in rows["walk_forward"]["detail"]
    assert "n_positive_folds" in rows["walk_forward"]["detail"]
    assert "majority_stable" in rows["walk_forward"]["detail"]
    assert "cpcv_passes" in rows["walk_forward"]["detail"]
    assert isinstance(rows["walk_forward"]["detail"]["cpcv_passes"], bool)
    assert "holdout_passes" in rows["walk_forward"]["detail"]
    assert isinstance(rows["walk_forward"]["detail"]["holdout_passes"], bool)
    assert "target found" not in page.content()
    _open_job_detail(page)
    page.wait_for_selector("#evidence li")
    evidence_text = page.locator("#evidence").inner_text()
    assert "walk_forward:" in evidence_text
    assert "regime_stable=" in evidence_text


def test_bollinger_job_records_method_trials(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_bb_e2e")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(
        page,
        _spec_yaml(
            dataset,
            statement="Bollinger mean reversion works in US large caps net of costs",
            signal_mechanism="bollinger_zscore",
            time_budget_s=60,
        ),
    )
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "bollinger_zscore" for row in rows)
    assert "target found" not in page.content()


def test_ohlr_job_records_method_trials(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_ohlr_e2e")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(
        page,
        _spec_yaml(
            dataset,
            statement="Williams percent R oversold longs work in US large caps net of costs",
            signal_mechanism="ohlr_4_pct",
            time_budget_s=60,
        ),
    )
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "ohlr_4_pct" for row in rows)
    assert "target found" not in page.content()


def test_pairs_job_records_method_trials(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_pairs_e2e")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(
        page,
        _spec_yaml(
            dataset,
            statement="Pairs spread mean reversion works in US large caps net of costs",
            signal_mechanism="pairs_spread",
            time_budget_s=60,
        ),
    )
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "pairs_spread" for row in rows)
    assert "target found" not in page.content()


def test_atr_job_records_method_trials(real_daemon, browser_page):
    dataset = _write_dataset(real_daemon["data_dir"], dataset_id="ds_atr_e2e")
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    _preview_then_submit(
        page,
        _spec_yaml(
            dataset,
            statement="ATR buffered Donchian breakouts work in US large caps net of costs",
            signal_mechanism="atr_breakout",
            time_budget_s=60,
        ),
    )
    outcome = _wait_list_outcome(page, timeout_ms=90000)
    assert outcome in _OUTCOMES
    run_id = _first_run_id(page)
    layout = RunLayout(real_daemon["data_dir"] / run_id)
    rows = [
        json.loads(line)
        for line in layout.trial_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert all(row.get("kind") == "atr_breakout" for row in rows)
    assert "target found" not in page.content()
