from datetime import UTC, datetime

from engine.research.models import Reverification, ResearchStatus
from engine.research.state_machine import transition, ResearchEvent
from tests.test_state_machine import locked_brief, with_status
from dataclasses import replace

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def test_open_version_clears_reverifications() -> None:
    research = replace(
        with_status(ResearchStatus.PAUSED),
        brief=locked_brief(),
        reverifications=(
            Reverification(
                round_id="r1",
                method_id="stability.oos",
                report=None,
                passed=True,
                created_at=NOW,
            ),
        ),
    )
    opened = transition(research, ResearchEvent.MODIFY_CONFIRM, NOW)
    assert opened.reverifications == ()
