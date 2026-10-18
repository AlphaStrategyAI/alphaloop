"""Implementation trial budget for failed verification auto-iteration (V1 P0)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from engine.export import strategy_pack_eligibility
from engine.research.pool_data_shrink import pool_shrink_disclosure
from engine.research.data_window import disclosure_rounds_on_window
from engine.research.display_names import format_param_change, gate_check_label
from engine.research.window_copy import all_researches_on_window_label
from engine.research.models import ChangeClass, Research, ResearchStatus
from engine.research.specify import ProposedChange, classify_change
from engine.verifiers import VerificationReport, method_set_excluding_pit

DEFAULT_IMPLEMENTATION_TRIAL_BUDGET = 5
DEFAULT_TRIAL_BUDGET_INCREMENT = 5
DEFAULT_HIGH_SUSPICION_ROUNDS = 20


def max_implementation_trials() -> int:
    raw = os.environ.get("ALPHALOOP_MAX_TRIALS")
    if raw is None or raw == "":
        return DEFAULT_IMPLEMENTATION_TRIAL_BUDGET
    return max(1, int(raw))


def high_suspicion_round_threshold() -> int:
    raw = os.environ.get("ALPHALOOP_HIGH_SUSPICION_ROUNDS")
    if raw is None or raw == "":
        return DEFAULT_HIGH_SUSPICION_ROUNDS
    return max(1, int(raw))


def trial_budget_increment() -> int:
    raw = os.environ.get("ALPHALOOP_TRIAL_BUDGET_INCREMENT")
    if raw is None or raw == "":
        return DEFAULT_TRIAL_BUDGET_INCREMENT
    return max(1, int(raw))


def default_implementation_next_change(accepted) -> ProposedChange:
    return ProposedChange(
        field="lookback_days",
        before=accepted.spec.lookback_days,
        after=accepted.spec.lookback_days + 5,
    )


def change_requires_user_confirm(change: ProposedChange) -> bool:
    """Economic / coverage / B3 logic edits must never auto-continue on budget."""
    klass = classify_change(change)
    if klass in {ChangeClass.ECONOMIC, ChangeClass.COVERAGE}:
        return True
    if klass is ChangeClass.MODEL and change.field in {"signal_definition", "feature_set"}:
        return True
    return False


def _last_accepted_attempt(research: Research):
    if not research.versions or not research.versions[-1].rounds:
        return None
    return research.versions[-1].rounds[-1].accepted_attempt


def implementation_trials_used(research: Research) -> int:
    if research.current_version_number is None or not research.versions:
        return 0
    version = research.versions[research.current_version_number - 1]
    return len(version.rounds)


def implementation_trials_remaining(research: Research) -> int:
    used = implementation_trials_used(research)
    return max(0, research.implementation_trial_budget - used)


def methods_verification_passed(research: Research) -> bool:
    attempt = _last_accepted_attempt(research)
    if attempt is None or attempt.verification is None:
        return False
    method_set = method_set_excluding_pit(
        research.brief.round1_methods.value or attempt.spec.method_set
    )
    return attempt.verification.passed_for(method_set)


def failed_verifier_ids(research: Research) -> tuple[str, ...]:
    from engine.research.methods import format_verifier_ids

    attempt = _last_accepted_attempt(research)
    if attempt is None or attempt.verification is None:
        return ()
    raw = tuple(item.verifier_id for item in attempt.verification.results if not item.passed)
    return format_verifier_ids(raw)


def deferred_implementation_change(research: Research) -> ProposedChange | None:
    attempt = _last_accepted_attempt(research)
    if attempt is None:
        return None
    return default_implementation_next_change(attempt)


def can_auto_continue_impl_iteration(
    research: Research,
    change: ProposedChange,
) -> bool:
    if change_requires_user_confirm(change):
        return False
    return implementation_trials_used(research) < research.implementation_trial_budget


def budget_exhausted_stop(research: Research) -> bool:
    if research.status is not ResearchStatus.COMPLETED:
        return False
    if methods_verification_passed(research):
        return False
    deferred = deferred_implementation_change(research)
    if deferred is None or change_requires_user_confirm(deferred):
        return False
    return implementation_trials_used(research) >= research.implementation_trial_budget


def auto_iterating_under_budget(research: Research) -> bool:
    if research.status is not ResearchStatus.RUNNING:
        return False
    if methods_verification_passed(research):
        return False
    deferred = deferred_implementation_change(research)
    if deferred is None or change_requires_user_confirm(deferred):
        return False
    used = implementation_trials_used(research)
    return used > 0 and used < research.implementation_trial_budget


def can_manual_continue_iterate(research: Research) -> bool:
    if research.status is not ResearchStatus.COMPLETED:
        return False
    if methods_verification_passed(research):
        return False
    deferred = deferred_implementation_change(research)
    if deferred is None or change_requires_user_confirm(deferred):
        return False
    return True


@dataclass(frozen=True, slots=True)
class TrialBudgetView:
    used: int
    budget: int
    remaining: int


def trial_budget_view(research: Research) -> TrialBudgetView:
    used = implementation_trials_used(research)
    budget = research.implementation_trial_budget
    return TrialBudgetView(used=used, budget=budget, remaining=max(0, budget - used))


@dataclass(frozen=True, slots=True)
class CompletedPresentation:
    methods_verification_passed: bool
    strategy_pack_eligible: bool
    export_kind: str
    failed_verifier_ids: tuple[str, ...]
    failed_export_checks: tuple[str, ...]
    budget_exhausted: bool
    trial_budget: TrialBudgetView
    deferred_change_summary: str | None
    trial_counters: dict[str, int] | None
    headline: str
    summary: str
    hint_line: str


def _format_change(change: ProposedChange) -> str:
    return format_param_change(
        change.field,
        str(change.before),
        str(change.after),
    )


def running_budget_hint(research: Research, store: object | None = None) -> str:
    if research.status is not ResearchStatus.RUNNING:
        return ""
    if methods_verification_passed(research):
        return ""
    if implementation_trials_used(research) == 0:
        return ""
    view = trial_budget_view(research)
    gates = "、".join(failed_verifier_ids(research)) or "冻结验证"
    m = disclosure_rounds_on_window(research, store)  # type: ignore[arg-type]
    base = (
        f"第 {view.used}/{view.budget} 轮验证未通过（未通过：{gates}）。"
        "系统仅在实现层调整参数，不改经济逻辑，阈值不变，自动迭代中。"
    )
    if m > view.used:
        return f"{base} {all_researches_on_window_label(m)}。"
    return base


def _gates_label(research: Research, failed_ids: tuple[str, ...], eligibility) -> str:
    gate_labels = tuple(gate_check_label(item) for item in eligibility.failed_checks)
    return "、".join(failed_ids) if failed_ids else "、".join(gate_labels)


def _completed_hint_line(
    research: Research,
    *,
    methods_ok: bool,
    eligibility,
    failed_ids: tuple[str, ...],
    exhausted: bool,
    budget: TrialBudgetView,
) -> str:
    if methods_ok and eligibility.eligible:
        return ""
    gates = _gates_label(research, failed_ids, eligibility)
    if exhausted:
        return (
            f"实现层迭代预算已用尽（{budget.used}/{budget.budget} 轮）。"
            "验证仍未通过；只能导出研究记录包。"
        )
    if not methods_ok:
        if budget.used > 0:
            return (
                f"第 {budget.used}/{budget.budget} 轮验证未通过（未通过：{gates}）。"
                "可导出研究记录包。"
            )
        return f"验证未通过（未通过：{gates}）。只能导出研究记录包。"
    return f"冻结验证已通过，策略包门禁未满足：{gates}。"


def _pool_shrink_prefix(research: Research) -> str:
    universe = research.brief.universe.value
    remaining = len(universe.symbols) if universe and universe.symbols else 0
    dropped = research.pool_data_dropped_count
    if dropped <= 0:
        return ""
    return pool_shrink_disclosure(dropped, remaining) + " "


def completed_presentation(
    research: Research,
    store: object | None = None,
) -> CompletedPresentation:
    eligibility = strategy_pack_eligibility(research)
    shrink_prefix = _pool_shrink_prefix(research)
    methods_ok = methods_verification_passed(research)
    failed_ids = failed_verifier_ids(research)
    deferred = deferred_implementation_change(research)
    exhausted = budget_exhausted_stop(research)
    budget = trial_budget_view(research)
    counters = None
    if research.versions and research.versions[-1].rounds:
        tc = research.versions[-1].rounds[-1].trial_counters
        counters = {
            "candidatesEvaluated": tc.candidates_evaluated,
            "candidatesPassed": tc.candidates_passed,
            "conclusionAttemptNumber": tc.conclusion_attempt_number,
        }
    if eligibility.eligible:
        export_kind = "strategy_pack"
        headline = "研究已完成，可导出策略包"
        summary = (
            shrink_prefix
            + "当前冻结验证已全部通过（含时点第四关）。"
            "可导出策略包；alphaloop 不提供执行入口。"
        )
        hint = _completed_hint_line(
            research,
            methods_ok=methods_ok,
            eligibility=eligibility,
            failed_ids=failed_ids,
            exhausted=exhausted,
            budget=budget,
        )
    elif methods_ok:
        export_kind = "research_record_only"
        gates = _gates_label(research, failed_ids, eligibility)
        headline = "研究已完成，但未通过可实盘交接"
        summary = (
            shrink_prefix
            + f"验证方法集已通过，但仍只能导出研究记录包。"
            f"未满足的门禁：{gates}。"
        )
        hint = _completed_hint_line(
            research,
            methods_ok=methods_ok,
            eligibility=eligibility,
            failed_ids=failed_ids,
            exhausted=exhausted,
            budget=budget,
        )
    else:
        export_kind = "research_record_only"
        gates = _gates_label(research, failed_ids, eligibility)
        headline = "研究已结束，验证未通过"
        summary = (
            shrink_prefix
            + f"不能导出策略包，只能导出研究记录包。"
            f"未通过的门禁包括：{gates}。"
        )
        m = disclosure_rounds_on_window(research, store)  # type: ignore[arg-type]
        if exhausted:
            summary = (
                shrink_prefix
                + f"{all_researches_on_window_label(m)}；轮数越多，偶然通过的可能性越高。"
                f"未通过门禁：{gates}。"
                "只能导出研究记录包。"
                "可点「继续迭代」追加预算后再跑（阈值不变）。"
            )
        hint = _completed_hint_line(
            research,
            methods_ok=methods_ok,
            eligibility=eligibility,
            failed_ids=failed_ids,
            exhausted=exhausted,
            budget=budget,
        )
    return CompletedPresentation(
        methods_verification_passed=methods_ok,
        strategy_pack_eligible=eligibility.eligible,
        export_kind=export_kind,
        failed_verifier_ids=failed_ids,
        failed_export_checks=eligibility.failed_checks,
        budget_exhausted=exhausted,
        trial_budget=budget,
        deferred_change_summary=_format_change(deferred) if deferred and exhausted else None,
        trial_counters=counters,
        headline=headline,
        summary=summary,
        hint_line=hint,
    )


def validate_continue_iterate_confirm(
    research: Research,
    *,
    user_confirmed: bool,
    high_suspicion_acknowledged: bool,
    store: object | None = None,
) -> None:
    if not user_confirmed:
        raise ValueError("continue_iterate requires user_confirmed=true")
    m = disclosure_rounds_on_window(research, store)  # type: ignore[arg-type]
    threshold = high_suspicion_round_threshold()
    if m >= threshold and not high_suspicion_acknowledged:
        raise ValueError(
            f"continue_iterate requires high_suspicion_acknowledged=true "
            f"when cumulative rounds on window ({m}) >= {threshold}"
        )


def assert_can_manual_continue(research: Research) -> ProposedChange:
    deferred = deferred_implementation_change(research)
    if deferred is None:
        raise ValueError("continue_iterate requires a completed round")
    if not can_manual_continue_iterate(research):
        raise ValueError("research is not eligible for manual continue_iterate")
    return deferred


def verification_thresholds_unchanged(
    before: VerificationReport,
    after: VerificationReport,
) -> bool:
    revisions = {item.verifier_id: item.revision for item in before.results}
    after_revisions = {item.verifier_id: item.revision for item in after.results}
    return revisions == after_revisions
