"""Crossref papers are kept only when they match the strategy's key terms."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.gather import Material, gather_materials
from engine.research.material_relevance import relevance_score, strategy_key_terms
from engine.research.models import (
    Attempt,
    ChangeClass,
    ImplementationDelta,
    LogicStatement,
    ResearchStatus,
    RoundV2,
    ReviewReport,
    TrialCounters,
    Version,
)
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.verifiers import VerificationReport, VerifierResult
from tests.test_loop_runtime import NOW, running_research, simulation, strategy
from tests.test_state_machine import locked_brief


FETCHED = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)
QUERY = "美股股票 SPY 的均值回归。有效研究时间 12 小时。"


def _paper(material_id: str, title: str, abstract: str) -> Material:
    return Material(
        material_id=material_id,
        source="papers",
        title=title,
        url=f"https://doi.org/{material_id}",
        text=abstract,
        fetched_at=FETCHED,
        published_at=None,
    )


class _Papers:
    def __init__(self, materials: tuple[Material, ...]) -> None:
        self._materials = materials

    def fetch(self, query: str) -> tuple[Material, ...]:
        assert "均值回归" in query or "mean reversion" in query.lower()
        return self._materials


def test_scoring_rule_is_title_then_abstract_and_not_a_padded_cutoff() -> None:
    terms = strategy_key_terms(QUERY)
    assert "mean reversion" in terms
    assert "均值回归" in terms
    relevant_title = _paper("doi:1", "Short-term reversal and mean reversion", "unrelated biology")
    relevant_abstract = _paper("doi:2", "Liquidity and volume", "Evidence of mean-reversion in equities.")
    irrelevant = _paper("doi:3", "Polymer folding kinetics", "A study of protein folding rates.")
    assert relevance_score(relevant_title, terms) == 2
    assert relevance_score(relevant_abstract, terms) == 1
    assert relevance_score(irrelevant, terms) == 0


def test_gather_keeps_relevant_papers_and_drops_unrelated_ones() -> None:
    kept_title = _paper("doi:keep", "Equity mean reversion", "abstract")
    kept_abstract = _paper("doi:abs", "Trading costs", "This paper studies mean reversion.")
    dropped = _paper("doi:drop", "Coral reef calcification", "Ocean chemistry and pH.")
    batch = gather_materials(QUERY, (_Papers((kept_title, kept_abstract, dropped)),))
    ids = {item.material_id for item in batch.materials}
    assert ids == {"doi:keep", "doi:abs"}


def test_no_relevant_papers_is_an_empty_result_not_padding() -> None:
    unrelated = tuple(
        _paper(f"doi:{index}", f"Unrelated topic {index}", "No strategy language here.")
        for index in range(5)
    )
    batch = gather_materials(QUERY, (_Papers(unrelated),))
    assert batch.materials == ()
    assert batch.no_relevant_materials is True


def test_completed_view_says_no_relevant_materials_when_none_were_saved(tmp_path: Path) -> None:
    research = replace(running_research(), brief=locked_brief())
    gate = VerifierResult("scorecard.market", "scorecard-v1", False, {}, "no")
    attempt = Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=strategy(1),
        simulation=simulation(),
        verification=VerificationReport((gate,)),
        review=ReviewReport(True, ()),
        evidence_paths=(),
    )
    round_ = RoundV2(
        "r-loop-v1-r1",
        1,
        attempt,
        NOW,
        LogicStatement("mean reversion", False, baseline_version=1),
        ImplementationDelta(),
        TrialCounters(1, 0, 1),
    )
    version = Version("r-loop-v1", 1, research.brief, (round_,), NOW, "confirm_run")
    research = replace(
        research,
        status=ResearchStatus.COMPLETED,
        versions=(version,),
        current_version_number=1,
        pending_confirm=None,
    )
    store = SQLiteStore(tmp_path / "mat.db")
    store.create(research)
    view = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path)).view_for(
        "#/research/r-loop"
    )
    assert view["sources"] == "未找到相关资料"
