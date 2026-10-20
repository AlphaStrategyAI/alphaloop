"""Secrets must not survive error text, logs, sqlite, export zips, or filenames."""

from __future__ import annotations

import json
import logging
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx

from engine.research.gather import GatherBatch
from engine.research.loop import DefaultRoundBuilder
from engine.research.models import ResearchStatus, new_research
from engine.research.secret_memory import (
    DESKTOP_REQUIRED_CODE,
    DESKTOP_REQUIRED_MESSAGE,
    configure_process_owner,
    install_secrets,
    secret_gate,
)
from engine.research.secret_redaction import (
    clear_registered_secrets,
    install_redacting_log_filter,
    redact_filename,
    redact_text,
    register_secret,
    set_text_redactor,
)
from engine.research.store import SQLiteStore
from engine.research.user_errors import classify_run_error
from engine.review.subagent import SubagentReviewer
from tests.test_loop_runtime import FakeBuilder, PassReviewer, running_research

SECRET = "alphaloop-test-secret-9f3a"
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def setup_function() -> None:
    clear_registered_secrets()
    set_text_redactor(None)
    configure_process_owner("cli")


def test_redacts_exact_secret_url_userinfo_query_and_token_path() -> None:
    register_secret(SECRET)
    raw = (
        f"error sending request for url https://user:{SECRET}@example.invalid"
        f"/v1/{SECRET}?api_key={SECRET}&other=1"
    )
    cleaned = redact_text(raw)
    assert SECRET not in cleaned
    assert "api_key" not in cleaned
    assert "user:" not in cleaned
    assert "example.invalid" in cleaned
    assert redact_filename(f"export-{SECRET}.zip") == "export-«redacted».zip"
    assert redact_filename("report.zip") == "report.zip"


def test_extra_redactor_runs_after_the_builtin_pass() -> None:
    register_secret(SECRET)
    set_text_redactor(lambda text: text.replace("example.invalid", "host"))
    cleaned = redact_text(f"https://example.invalid/?k={SECRET}")
    assert SECRET not in cleaned
    assert "host" in cleaned
    assert "k=" not in cleaned


def test_failed_network_review_sqlite_log_and_zip_omit_the_secret(tmp_path: Path) -> None:
    register_secret(SECRET)
    install_redacting_log_filter()
    log_path = tmp_path / "engine.log"
    logger = logging.getLogger("alphaloop.secret-test")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path)
    logger.addHandler(handler)
    try:
        request = httpx.Request(
            "GET",
            f"https://user:{SECRET}@example.invalid/data/{SECRET}?token={SECRET}",
        )
        network_error = httpx.ConnectError(
            f"connection failed for https://user:{SECRET}@example.invalid/data/{SECRET}?token={SECRET}",
            request=request,
        )
        assert SECRET in str(network_error)
        code, message = classify_run_error(network_error)
        assert code == "RUN_LOOP_FAILED"
        assert SECRET not in message
        logger.info("run failed: %s", str(network_error))

        class _Boom:
            def complete(self, system: str, user: str) -> str:
                raise httpx.ConnectError(f"review {SECRET} rejected", request=request)

        from tests.test_deterministic_reviewer import _draft

        report = SubagentReviewer(_Boom()).run(_draft(True))
        finding = report.findings[0].message
        assert SECRET not in finding

        class _FailPort:
            def fetch(self, query: str) -> tuple:
                raise RuntimeError(f"upstream https://example.invalid/p/{SECRET}?x=1")

        batch = __import__(
            "engine.research.gather", fromlist=["gather_materials"]
        ).gather_materials("thesis", (_FailPort(),))
        assert batch.failures
        assert all(SECRET not in item for item in batch.failures)
        evidence = tmp_path / "snapshots"
        evidence.mkdir()
        builder = DefaultRoundBuilder(
            material_ports=(),
            data_port=object(),  # type: ignore[arg-type]
            start=NOW.date(),
            end=NOW.date(),
            snapshot_root=evidence,
        )
        builder._write_evidence(GatherBatch((), batch.failures))
        failure_file = evidence.parent / "materials" / "gather-failures.json"
        assert SECRET not in failure_file.read_text(encoding="utf-8")

        research = replace(
            new_research("r-secret", NOW),
            status=ResearchStatus.PAUSED,
            last_run_error=message,
            last_run_error_code=code,
        )
        store = SQLiteStore(tmp_path / "research.db")
        store.create(research)
        from engine.export import build_research_record_pack

        pack = build_research_record_pack(research, tmp_path / "record.zip")
        blob = pack.read_bytes()
        assert SECRET.encode() not in blob
        with zipfile.ZipFile(pack) as archive:
            archived = archive.read("history/research.json")
            assert SECRET.encode() not in archived
            payload = json.loads(archived)
            assert payload["last_run_error"] == message
            for info in archive.infolist():
                assert SECRET not in info.filename
        db_bytes = (tmp_path / "research.db").read_bytes()
        assert SECRET.encode() not in db_bytes
        handler.flush()
        assert SECRET not in log_path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*"):
            assert SECRET not in path.name
    finally:
        logger.removeHandler(handler)
        handler.close()


def test_failure_preview_command_omits_the_secret(tmp_path: Path) -> None:
    from engine.main import ResearchCommandService
    from engine.research.runtime import EnginePaths

    configure_process_owner("desktop")
    install_secrets({"vendor-demo": SECRET})
    service = ResearchCommandService(
        SQLiteStore(tmp_path / "preview.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )
    payload = service.handle({"type": "secret_failure_preview", "secret_id": "vendor-demo"})
    assert SECRET not in payload["message"]
    assert "example.invalid" in payload["message"]
    assert "api_key" not in payload["message"]
    assert SECRET.encode() not in (tmp_path / "preview.db").read_bytes()


def test_cli_without_secret_pauses_and_desktop_push_allows_run() -> None:
    configure_process_owner("cli")
    assert secret_gate(("vendor-demo",)) == "pause"
    configure_process_owner("desktop")
    assert secret_gate(("vendor-demo",)) == "wait"
    install_secrets({"vendor-demo": SECRET})
    assert secret_gate(("vendor-demo",)) == "ok"
    assert SECRET not in DESKTOP_REQUIRED_MESSAGE
    assert DESKTOP_REQUIRED_CODE == "SECRETS_REQUIRE_DESKTOP"


def test_missing_required_secret_field_on_old_research_stays_empty() -> None:
    from engine.research.models import Research
    from engine.research.store import CONVERTER, _deep_unstructure

    research = new_research("r-old", NOW)
    payload = _deep_unstructure(research)
    payload.pop("required_secret_ids")
    loaded = CONVERTER.structure(payload, Research)
    assert loaded.required_secret_ids == ()


def test_run_once_pauses_when_cli_research_requires_a_secret(tmp_path: Path) -> None:
    from engine.research.clock import TimeBudget
    from engine.research.loop import ResearchLoop
    from tests.test_loop_runtime import FakeMonotonic

    configure_process_owner("cli")
    research = replace(running_research(), required_secret_ids=("vendor-demo",))
    store = SQLiteStore(tmp_path / "loop.db")
    store.create(research)
    loop = ResearchLoop(
        store,
        FakeBuilder(),
        PassReviewer(),
        TimeBudget(FakeMonotonic()),
        lambda: NOW,
    )
    updated = loop.run_once(research.research_id)
    assert updated.status is ResearchStatus.PAUSED
    assert updated.last_run_error == DESKTOP_REQUIRED_MESSAGE
    assert updated.last_run_error_code == DESKTOP_REQUIRED_CODE
    assert SECRET.encode() not in (tmp_path / "loop.db").read_bytes()
