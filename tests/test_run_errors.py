from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.models import ResearchStatus, new_research
from engine.i18n.errors import set_technical_detail_redactor
from engine.research.run_errors import apply_run_failure, max_consecutive_run_errors
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.models import ResearchEvent
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import running_research

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_apply_run_failure_pauses_after_n_identical_errors() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ALPHALOOP_MAX_CONSECUTIVE_RUN_ERRORS", "3")
    research = running_research()
    msg = "UNIQUE constraint failed"
    current = research
    for _ in range(2):
        current = apply_run_failure(current, msg, NOW)
        assert current.status is ResearchStatus.RUNNING
    paused = apply_run_failure(current, msg, NOW)
    assert paused.status is ResearchStatus.PAUSED
    assert paused.consecutive_identical_run_errors == 3
    assert paused.last_run_error == msg
    monkeypatch.undo()


def test_transient_error_resets_count_on_different_message() -> None:
    research = running_research()
    once = apply_run_failure(research, "error-a", NOW)
    assert once.consecutive_identical_run_errors == 1
    twice = apply_run_failure(once, "error-b", NOW)
    assert twice.consecutive_identical_run_errors == 1


def test_last_error_surfaces_in_running_view(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "err.db")
    research = running_research()
    research = transition(
        apply_run_failure(research, "boom", NOW),
        ResearchEvent.PAUSE,
        NOW,
    )
    store.create(research)
    service = ResearchCommandService(
        store,
        EnginePaths.for_colocated_root(tmp_path),
    )
    view = service.view_for("#/research/r-loop")
    assert view["status"] == "paused"
    assert view["lastError"]["message"] == "boom"


def test_last_error_includes_code_when_classified(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "code.db")
    research = running_research()
    research = apply_run_failure(
        research,
        "数据源未返回行情，请检查标的和网络。",
        NOW,
        code="DATA_EMPTY_PRICES",
    )
    research = transition(research, ResearchEvent.PAUSE, NOW)
    store.create(research)
    service = ResearchCommandService(
        store,
        EnginePaths.for_colocated_root(tmp_path),
    )
    view = service.view_for("#/research/r-loop")
    assert view["lastError"]["code"] == "DATA_EMPTY_PRICES"


def test_last_error_passes_params_and_redacts_detail(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "detail.db")
    research = running_research()
    research = apply_run_failure(
        research,
        "数据源未返回行情，请检查标的和网络。",
        NOW,
        code="DATA_EMPTY_PRICES",
        params={"symbols": 3},
        detail="secret-token failed",
    )
    research = transition(research, ResearchEvent.PAUSE, NOW)
    store.create(research)
    service = ResearchCommandService(
        store,
        EnginePaths.for_colocated_root(tmp_path),
    )

    def hide(text: str) -> str:
        return text.replace("secret-token", "[redacted]")

    previous = set_technical_detail_redactor(hide)
    try:
        view = service.view_for("#/research/r-loop")
    finally:
        set_technical_detail_redactor(previous)
    assert view["lastError"]["params"] == {"symbols": 3}
    assert view["lastError"]["detail"] == "[redacted] failed"
    assert "secret-token" not in view["lastError"]["detail"]
