"""Ensure desktop view payloads never expose Python repr strings (e.g. CoverageFloor(...))."""

import re
from dataclasses import replace
from pathlib import Path

import pytest

from engine.main import ResearchCommandService
from engine.research.display_names import contains_internal_leak
from engine.research.clock import TimeBudget
from engine.research.loop import ResearchLoop
from engine.research.models import ResearchEvent, ResearchStatus, new_research
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from tests.test_export_pack import completed_research
from tests.test_loop_runtime import (
    NOW,
    EconomicBuilder,
    FailedMethodsParamBuilder,
    PassReviewer,
    running_research,
)
from tests.test_state_machine import locked_brief, with_status

REPR_LIKE = re.compile(r"\w+\(\w+=")


_TECHNICAL_STRING_KEYS = frozenset(
    {
        "researchId",
        "roundId",
        "methodId",
        "selectedRoundId",
        "selectedMethodId",
        "id",
        "revision",
        "conclusionRoundId",
        "recordId",
    }
)


def _all_strings(value: object, parent_key: str | None = None):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _TECHNICAL_STRING_KEYS:
                continue
            yield from _all_strings(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item, parent_key)
    elif isinstance(value, str):
        yield value


def assert_no_repr_like(view: dict) -> None:
    for text in _all_strings(view):
        match = REPR_LIKE.search(text)
        assert match is None, f"repr-like fragment in view text: {text[:160]!r}"


def assert_no_internal_id_leaks(view: dict) -> None:
    for text in _all_strings(view):
        if "revision" in text and len(text) > 40 and text.count(" ") < 2:
            continue
        assert not contains_internal_leak(text), f"internal id leak in view: {text[:160]!r}"


@pytest.fixture
def service(tmp_path: Path) -> ResearchCommandService:
    store = SQLiteStore(tmp_path / "repr.db")
    return ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))


VIEW_CASES = (
    "research_list",
    "draft",
    "confirm_run",
    "running",
    "paused",
    "awaiting_confirm",
    "completed",
    "ended_exhausted",
)


@pytest.mark.parametrize("case", VIEW_CASES)
def test_view_paths_avoid_python_repr(
    service: ResearchCommandService, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if case == "research_list":
        view = service.view_for("#/research")
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    if case == "draft":
        service.store.create(replace(new_research("r-draft", NOW), dialogue=()))
        view = service.view_for("#/research/r-draft")
        assert view["kind"] == "draft"
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    if case == "confirm_run":
        service.store.create(
            replace(with_status(ResearchStatus.DRAFT), research_id="r-confirm", brief=locked_brief())
        )
        view = service.view_for("#/research/r-confirm")
        assert view["kind"] == "confirm_run"
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    if case == "running":
        service.store.create(running_research())
        view = service.view_for("#/research/r-loop")
        assert view["kind"] == "running"
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    if case == "paused":
        service.store.create(transition(running_research(), ResearchEvent.PAUSE, NOW))
        view = service.view_for("#/research/r-loop")
        assert view["kind"] == "running"
        assert view["status"] == "paused"
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    if case == "awaiting_confirm":
        service.store.create(running_research())
        waiting = ResearchLoop(
            service.store,
            EconomicBuilder(),
            PassReviewer(),
            TimeBudget(lambda: 10.0),
            lambda: NOW,
        ).run_once("r-loop")
        assert waiting.status is ResearchStatus.AWAITING_CONFIRM
        view = service.view_for("#/research/r-loop")
        assert view["kind"] == "awaiting_confirm"
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    if case == "completed":
        service.store.create(replace(completed_research(), research_id="r-done"))
        view = service.view_for("#/research/r-done")
        assert view["kind"] == "completed"
        assert view["status"] == "completed"
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    if case == "ended_exhausted":
        monkeypatch.setenv("ALPHALOOP_MAX_TRIALS", "1")
        service.store.create(running_research())
        ended = ResearchLoop(
            service.store,
            FailedMethodsParamBuilder(),
            PassReviewer(),
            TimeBudget(lambda: 10.0),
            lambda: NOW,
        ).run_once("r-loop")
        assert ended.status is ResearchStatus.COMPLETED
        view = service.view_for("#/research/r-loop")
        assert view["kind"] == "completed"
        assert_no_repr_like(view)
        assert_no_internal_id_leaks(view)
        return

    raise AssertionError(f"unknown case {case}")
