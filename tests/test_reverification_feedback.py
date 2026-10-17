from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from engine.main import ResearchCommandService
from engine.research.desktop_view import last_reverification_summary
from engine.research.models import Reverification, new_research
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.verifiers import VerificationReport, VerifierResult
from tests.test_export_pack import completed_research

NOW = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)


def test_reverify_pass_does_not_change_overall_verdict_copy(tmp_path: Path) -> None:
    research = replace(completed_research(), research_id="r-rev")
    round_id = research.versions[-1].rounds[-1].round_id
    failed = VerifierResult("overfit.walk", "walk-v1", True, {}, "ok")
    passed_scorecard = VerifierResult("scorecard.market", "scorecard-v1", False, {}, "fail")
    report = VerificationReport((passed_scorecard, failed, failed, failed, failed))
    round_ = research.versions[-1].rounds[-1]
    attempt = replace(round_.accepted_attempt, verification=report)
    round_ = replace(round_, accepted_attempt=attempt)
    version = replace(research.versions[-1], rounds=(round_,))
    research = replace(research, versions=(version,))
    research = replace(
        research,
        reverifications=(
            Reverification(
                round_id=round_id,
                method_id="overfit.walk",
                report=report,
                passed=True,
                created_at=NOW,
            ),
        ),
    )
    summary = last_reverification_summary(research)
    assert summary is not None
    assert summary["overallConclusionUnchanged"] is True
    assert "整轮结论未变" in summary["userMessage"]
    assert "仍未通过" in summary["userMessage"]
