from datetime import UTC, datetime
from pathlib import Path

from engine.research.models import ChangeClass, Attempt, MethodRef, ReviewReport, new_research
from engine.research.store import SQLiteStore
from tests.test_loop_runtime import NOW, strategy

RESEARCH_ID = "r-recycle"


def test_delete_clears_child_rows_and_recreate_can_record_attempts(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "del.db")
    store.create(new_research(RESEARCH_ID, NOW))
    attempt = Attempt(
        attempt_id="v1-r1-a1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=strategy(1),
        simulation=None,
        verification=None,
        review=ReviewReport(True, ()),
    )
    store.record_review_attempt(RESEARCH_ID, 1, 1, attempt, NOW)
    store.record_method_usage(
        RESEARCH_ID,
        1,
        (MethodRef("overfit.walk", "walk-v1"),),
    )
    store.record_error(RESEARCH_ID, "x", NOW, force=True)

    store.delete(RESEARCH_ID)
    assert store.connection.execute(
        "SELECT COUNT(*) FROM review_attempts WHERE research_id=?",
        (RESEARCH_ID,),
    ).fetchone()[0] == 0

    store.create(new_research(RESEARCH_ID, NOW))
    store.record_review_attempt(RESEARCH_ID, 1, 1, attempt, NOW)
    assert store.get_attempt("v1-r1-a1", research_id=RESEARCH_ID) is not None
