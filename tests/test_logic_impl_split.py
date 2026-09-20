"""Tests for B2/B3: Trial counters and logic/implementation split."""
from datetime import UTC, datetime

from engine.research.models import (
    Attempt,
    ChangeClass,
    ImplementationDelta,
    LogicStatement,
    ReviewReport,
    RoundV2,
    TrialCounters,
)


def test_trial_counters_fields() -> None:
    counters = TrialCounters(
        candidates_evaluated=15,
        candidates_passed=3,
        conclusion_attempt_number=2,
    )
    assert counters.candidates_evaluated == 15
    assert counters.candidates_passed == 3
    assert counters.conclusion_attempt_number == 2


def test_logic_statement_baseline_version() -> None:
    logic = LogicStatement(
        statement="低波动量价回归策略，在波动率低于阈值时做多回归信号",
        changed_from_prior=False,
        change_description=None,
        baseline_version=1,
    )
    assert logic.baseline_version == 1
    assert logic.changed_from_prior is False


def test_logic_statement_change_requires_description() -> None:
    logic = LogicStatement(
        statement="增加拥挤度过滤条件",
        changed_from_prior=True,
        change_description="增加了拥挤度过滤，当持仓集中度超过阈值时不入场",
        baseline_version=1,
    )
    assert logic.changed_from_prior is True
    assert logic.change_description is not None


def test_implementation_delta_fields() -> None:
    delta = ImplementationDelta(
        research_method_changes=("换用滚动窗口回归",),
        model_changes=("从线性回归改为岭回归",),
        param_changes=(("lookback", "20", "30"), ("entry_z", "1.0", "1.5")),
    )
    assert len(delta.param_changes) == 2
    assert delta.param_changes[0] == ("lookback", "20", "30")


def test_round_v2_requires_all_b2_b3_fields() -> None:
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    attempt = Attempt(
        attempt_id="a-1",
        number=1,
        change_class=ChangeClass.PARAM,
        spec=None,
        simulation=None,
        verification=None,
        review=ReviewReport(passed=True, findings=()),
    )
    round_ = RoundV2(
        round_id="v1-r1",
        number=1,
        accepted_attempt=attempt,
        completed_at=now,
        logic_statement=LogicStatement(
            statement="测试逻辑",
            changed_from_prior=False,
            baseline_version=1,
        ),
        implementation_delta=ImplementationDelta(),
        trial_counters=TrialCounters(
            candidates_evaluated=10,
            candidates_passed=2,
            conclusion_attempt_number=1,
        ),
    )
    assert round_.trial_counters.candidates_evaluated == 10
    assert round_.logic_statement.statement == "测试逻辑"


def test_implementation_delta_defaults() -> None:
    """Test that ImplementationDelta has sensible defaults."""
    delta = ImplementationDelta()
    assert delta.research_method_changes == ()
    assert delta.model_changes == ()
    assert delta.param_changes == ()


def test_logic_statement_defaults() -> None:
    """Test that LogicStatement has sensible defaults for optional fields."""
    logic = LogicStatement(
        statement="基本逻辑",
        changed_from_prior=False,
    )
    assert logic.change_description is None
    assert logic.baseline_version == 1


def test_round_history_includes_trial_counts() -> None:
    from engine.export import _round_history_with_trials
    
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    round_ = RoundV2(
        round_id="v1-r1",
        number=1,
        accepted_attempt=Attempt(
            attempt_id="a-1",
            number=1,
            change_class=ChangeClass.PARAM,
            spec=None,
            simulation=None,
            verification=None,
            review=ReviewReport(passed=True, findings=()),
        ),
        completed_at=now,
        logic_statement=LogicStatement("test", False, baseline_version=1),
        implementation_delta=ImplementationDelta(),
        trial_counters=TrialCounters(15, 3, 2),
    )
    history = _round_history_with_trials([round_])
    assert history[0]["trial_counters"]["candidates_evaluated"] == 15
    assert history[0]["trial_counters"]["candidates_passed"] == 3
    assert history[0]["trial_counters"]["conclusion_attempt_number"] == 2


def test_round_history_includes_logic_statement() -> None:
    from engine.export import _round_history_with_trials
    
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    round_ = RoundV2(
        round_id="v1-r1",
        number=1,
        accepted_attempt=Attempt(
            attempt_id="a-1",
            number=1,
            change_class=ChangeClass.PARAM,
            spec=None,
            simulation=None,
            verification=None,
            review=ReviewReport(passed=True, findings=()),
        ),
        completed_at=now,
        logic_statement=LogicStatement(
            statement="低波动量价回归策略",
            changed_from_prior=True,
            change_description="增加了趋势过滤",
            baseline_version=1,
        ),
        implementation_delta=ImplementationDelta(
            research_method_changes=("换用滚动窗口",),
            param_changes=(("lookback", "20", "30"),),
        ),
        trial_counters=TrialCounters(10, 2, 1),
    )
    history = _round_history_with_trials([round_])
    assert history[0]["logic_statement"]["statement"] == "低波动量价回归策略"
    assert history[0]["logic_statement"]["changed_from_prior"] is True
    assert history[0]["logic_statement"]["change_description"] == "增加了趋势过滤"
    assert history[0]["implementation_delta"]["research_method_changes"] == ["换用滚动窗口"]
    assert history[0]["implementation_delta"]["param_changes"] == [["lookback", "20", "30"]]
