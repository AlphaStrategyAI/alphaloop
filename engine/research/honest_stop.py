"""V1-P0 transitional honest stop after failed method verification (not long-term default)."""

from __future__ import annotations

from dataclasses import dataclass

from engine.export import strategy_pack_eligibility
from engine.research.models import ChangeClass, Research, ResearchStatus
from engine.research.specify import ProposedChange, classify_change
from engine.verifiers import VerificationReport, method_set_excluding_pit


def default_implementation_next_change(accepted) -> ProposedChange:
    return ProposedChange(
        field="lookback_days",
        before=accepted.spec.lookback_days,
        after=accepted.spec.lookback_days + 5,
    )


def change_requires_user_confirm(change: ProposedChange) -> bool:
    """Economic / coverage / B3 logic edits must not take the honest COMPLETE stop path."""
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


def methods_verification_passed(research: Research) -> bool:
    attempt = _last_accepted_attempt(research)
    if attempt is None or attempt.verification is None:
        return False
    method_set = method_set_excluding_pit(
        research.brief.round1_methods.value or attempt.spec.method_set
    )
    return attempt.verification.passed_for(method_set)


def failed_verifier_ids(research: Research) -> tuple[str, ...]:
    attempt = _last_accepted_attempt(research)
    if attempt is None or attempt.verification is None:
        return ()
    return tuple(
        item.verifier_id for item in attempt.verification.results if not item.passed
    )


def honest_stop_applies(research: Research, deferred: ProposedChange | None) -> bool:
    if research.status is not ResearchStatus.COMPLETED:
        return False
    if methods_verification_passed(research):
        return False
    if deferred is None or change_requires_user_confirm(deferred):
        return False
    return True


def can_manual_continue_iterate(research: Research, deferred: ProposedChange | None) -> bool:
    return honest_stop_applies(research, deferred)


@dataclass(frozen=True, slots=True)
class CompletedPresentation:
    methods_verification_passed: bool
    strategy_pack_eligible: bool
    export_kind: str
    failed_verifier_ids: tuple[str, ...]
    failed_export_checks: tuple[str, ...]
    honest_stop: bool
    auto_iterate_declined: bool
    deferred_change_summary: str | None
    trial_counters: dict[str, int] | None
    headline: str
    summary: str
    hint_line: str


def _format_change(change: ProposedChange) -> str:
    return f"{change.field}: {change.before!r} → {change.after!r}"


def completed_presentation(research: Research) -> CompletedPresentation:
    eligibility = strategy_pack_eligibility(research)
    methods_ok = methods_verification_passed(research)
    failed_ids = failed_verifier_ids(research)
    attempt = _last_accepted_attempt(research)
    deferred = (
        default_implementation_next_change(attempt) if attempt is not None else None
    )
    stop = honest_stop_applies(research, deferred)
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
            "当前冻结验证已全部通过（含时点第四关）。"
            "可导出 strategy_pack；alphaloop 不提供执行入口。"
        )
        hint = ""
    elif methods_ok:
        export_kind = "research_record_only"
        gates = "、".join(failed_ids) if failed_ids else "、".join(eligibility.failed_checks)
        headline = "研究已完成，但未通过可实盘交接"
        summary = (
            f"验证方法集已通过，但仍只能导出 research_record。"
            f"未满足的门禁：{gates}。"
        )
        hint = ""
    else:
        export_kind = "research_record_only"
        gates = "、".join(failed_ids) if failed_ids else "、".join(eligibility.failed_checks)
        headline = "研究已结束，验证未通过"
        summary = (
            f"本轮未通过冻结验证，不能导出 strategy_pack，只能导出 research_record。"
            f"未通过的门禁包括：{gates}。"
        )
        trial_note = ""
        version_rounds = (
            len(research.versions[-1].rounds) if research.versions else 0
        )
        if counters or version_rounds:
            trial_note = (
                f"本版已完成 {version_rounds} 轮；"
                f"最近一轮评估 {counters['candidatesEvaluated'] if counters else 0} 次，"
                f"通过 {counters['candidatesPassed'] if counters else 0} 次。"
            )
        change_note = _format_change(deferred) if deferred and stop else ""
        hint = (
            "V1 规则：验证方法集未通过；若继续，下一步本是参数/模型实现层调整"
            f"（{change_note}）。系统未自动迭代，已停在当前结论。"
            f"{trial_note}"
        ).strip()
    return CompletedPresentation(
        methods_verification_passed=methods_ok,
        strategy_pack_eligible=eligibility.eligible,
        export_kind=export_kind,
        failed_verifier_ids=failed_ids,
        failed_export_checks=eligibility.failed_checks,
        honest_stop=stop,
        auto_iterate_declined=stop,
        deferred_change_summary=_format_change(deferred) if deferred and stop else None,
        trial_counters=counters,
        headline=headline,
        summary=summary,
        hint_line=hint,
    )


def assert_can_manual_continue(research: Research) -> ProposedChange:
    attempt = _last_accepted_attempt(research)
    if attempt is None:
        raise ValueError("continue_iterate requires a completed round")
    deferred = default_implementation_next_change(attempt)
    if not can_manual_continue_iterate(research, deferred):
        raise ValueError("research is not eligible for manual continue_iterate")
    return deferred


def verification_thresholds_unchanged(
    before: VerificationReport,
    after: VerificationReport,
) -> bool:
    revisions = {
        item.verifier_id: item.revision for item in before.results
    }
    after_revisions = {
        item.verifier_id: item.revision for item in after.results
    }
    return revisions == after_revisions
