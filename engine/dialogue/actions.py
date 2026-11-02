"""Runtime questions and the same commands the desktop buttons already send.

Read-only questions never change the brief. A logic change becomes a confirm
card. The active brief stays as it is until that card is approved.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any

from engine.dialogue.turns import append_dialogue
from engine.export import strategy_pack_eligibility
from engine.research.methods import suggest_method_refs
from engine.research.models import (
    ChangeClass,
    ConfirmKind,
    ConfirmRequest,
    DialogueRole,
    EvidenceKind,
    EvidenceRef,
    Research,
    ResearchEvent,
    ResearchStatus,
    Slot,
)
from engine.research.state_machine import executable_commands, transition

MISSING = "尚无已提交轮次/无此指标"
Perform = Callable[[Research, dict[str, Any]], Research]


def _norm(text: str) -> str:
    lowered = text.strip().lower()
    lowered = lowered.replace("？", "").replace("?", "").replace("！", "").replace("!", "")
    lowered = lowered.replace("，", " ").replace(",", " ").replace("：", ":").replace(":", ":")
    return " ".join(lowered.split())


def _commands(research: Research) -> str:
    names = ", ".join(executable_commands(research.status))
    return f"允许的命令：{names}"


def _latest_round(research: Research):
    if not research.versions:
        return None, None
    version = research.versions[-1]
    if not version.rounds:
        return version, None
    return version, version.rounds[-1]


def _cite_round(research: Research) -> str:
    version, round_ = _latest_round(research)
    if version is None or round_ is None:
        return MISSING
    attempt = round_.accepted_attempt
    attempt_id = getattr(attempt, "attempt_id", "")
    return (
        f"版本 {version.version_id} 轮次 {round_.round_id} "
        f"尝试 {attempt_id}。"
    )


def _answer_status(research: Research) -> str:
    _version, round_ = _latest_round(research)
    if round_ is None:
        return f"状态 {research.status.value}。{MISSING} {_commands(research)}"
    action = research.current_action.value
    return (
        f"状态 {research.status.value}。{_cite_round(research)}"
        f"最近动作 {action}。"
        f"{_commands(research)}"
    )


def _answer_gate(research: Research) -> str:
    _version, round_ = _latest_round(research)
    if round_ is None or round_.accepted_attempt.verification is None:
        return f"{MISSING} {_commands(research)}"
    failed = [
        f"{item.verifier_id}@{item.revision}"
        for item in round_.accepted_attempt.verification.results
        if not item.passed
    ]
    if not failed:
        return f"最近一轮没有未过的关。{_cite_round(research)}{_commands(research)}"
    return f"未过：{'、'.join(failed)}。{_cite_round(research)}{_commands(research)}"


def _committed_rounds(research: Research) -> list:
    return [round_ for version in research.versions for round_ in version.rounds]


def _answer_tried(research: Research) -> str:
    rounds = _committed_rounds(research)
    if not rounds:
        return f"{MISSING} {_commands(research)}"
    cited = "、".join(round_.round_id for round_ in rounds)
    return (
        f"已提交 {len(rounds)} 轮。"
        f"轮次 {cited}。"
        f"{_commands(research)}"
    )


def _answer_previous(research: Research) -> str:
    if len(research.versions) < 2:
        return f"{MISSING} {_commands(research)}"
    current = research.versions[-1]
    previous = research.versions[-2]
    changes = current.confirmed_changes or ()
    if not changes:
        rendered = "没有已记录的字段差异"
    else:
        rendered = "、".join(f"{name}={value}" for name, value in changes)
    return (
        f"版本 {current.version_id} 相对 {previous.version_id}：{rendered}。"
        f"{_commands(research)}"
    )


def _answer_export(research: Research) -> str:
    eligibility = strategy_pack_eligibility(research)
    if eligibility.eligible:
        kinds = "strategy_pack、research_record"
        failed = "无"
    else:
        kinds = "research_record"
        failed = "、".join(eligibility.failed_checks) or "无"
    reasons = " ".join(eligibility.reasons)
    extra = f" {reasons}" if reasons else ""
    return (
        f"当前可导出：{kinds}。失败检查：{failed}。{extra}"
        f"{_commands(research)}"
    )


def _answer_methods(research: Research, store, query: str) -> str:
    if store is None:
        return f"{MISSING} {_commands(research)}"
    needle = "" if query in {"建议方法", "方法库", "suggest a method", "suggest methods", "what methods"} else query
    executable, suggestions = suggest_method_refs(store, needle)
    if not executable and not suggestions:
        executable, suggestions = suggest_method_refs(store, "")
    exec_text = "、".join(f"{item.method_id}@{item.revision_hash}" for item in executable) or MISSING
    suggestion_text = "、".join(suggestions) or "无"
    return (
        f"可执行 MethodRef：{exec_text}。建议（不能执行或计作通过）：{suggestion_text}。"
        f"{_commands(research)}"
    )


def _reverify_choices(research: Research) -> list[tuple[str, str, str]]:
    choices: list[tuple[str, str, str]] = []
    for version in research.versions:
        for round_ in version.rounds:
            verification = round_.accepted_attempt.verification
            if verification is None:
                continue
            for item in verification.results:
                choices.append((round_.round_id, item.verifier_id, str(item.revision)))
            for ref in tuple(getattr(round_.accepted_attempt.spec, "method_set", ()) or ()):
                if ref.method_id != "pit.consistency":
                    choices.append((round_.round_id, ref.method_id, ref.revision_hash))
    unique: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in choices:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _logic_request(research: Research, after: str, now: datetime) -> ConfirmRequest:
    version, round_ = _latest_round(research)
    before = ""
    if version is not None:
        before = str(version.brief_snapshot.thesis.value or "")
    if not before:
        before = str(research.brief.thesis.value or "")
    proposed_after = after or "待确认的新逻辑"
    evidence: tuple[EvidenceRef, ...] = ()
    if round_ is not None:
        attempt = round_.accepted_attempt
        recorded = getattr(attempt, "review", None)
        recorded_at = round_.completed_at
        evidence = (
            EvidenceRef(
                record_id=attempt.attempt_id,
                recorded_at=recorded_at,
                kind=EvidenceKind.ATTEMPT,
                summary=None if recorded is None else "最近一轮已提交尝试",
            ),
        )
    version_number = research.current_version_number or 0
    return ConfirmRequest(
        request_id=f"logic-{research.research_id}-v{version_number}",
        kind=ConfirmKind.ECONOMIC,
        proposed_change=f"改前：{before or MISSING} 改后：{proposed_after}",
        reason="用户要求改逻辑。活动 brief 在确认前保持不变。",
        effect="确认暂停并开新版后才执行。可拒绝并保持原逻辑，或暂停后自己改。",
        why_change=evidence,
        change_class=ChangeClass.ECONOMIC,
        patch=(("thesis", proposed_after),) if after else (),
        created_at=now,
    )


def _is_status_question(normalized: str) -> bool:
    if normalized in {"现在在做什么", "我们在做什么", "what are we doing", "what's going on", "what is going on"}:
        return True
    return "在做什么" in normalized or "what are we doing" in normalized or "what we are doing" in normalized


def _is_gate_question(normalized: str) -> bool:
    if normalized in {"哪一关没过", "哪一关没有过", "which gate failed", "which check failed", "what gate failed"}:
        return True
    return "哪一关" in normalized or "哪关" in normalized or "gate failed" in normalized or "check failed" in normalized


def _is_tried_question(normalized: str) -> bool:
    if normalized in {"已经试过多少", "已经试过多少个", "how many tried", "how many have we tried", "试过哪些候选"}:
        return True
    if "试过" in normalized or "哪些候选" in normalized:
        return True
    return "how many" in normalized and any(word in normalized for word in ("tried", "round", "candidate"))


def _is_previous_question(normalized: str) -> bool:
    if normalized in {
        "和上一版有何差别",
        "和上一版有什么差别",
        "和上一版",
        "和上一版差在哪",
        "vs previous",
        "compared with the previous version",
        "difference from the previous version",
    }:
        return True
    return "上一版" in normalized or "previous version" in normalized or "vs previous" in normalized


def _shown(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _settings_confirm(research: Research, text: str, updates: tuple, now: datetime) -> Research:
    if research.pending_confirm is not None:
        return _reply(
            research,
            text,
            f"已有待确认卡 {research.pending_confirm.request_id}。活动 brief 未修改。",
            now,
        )
    before_bits: list[str] = []
    after_bits: list[str] = []
    for name, value in updates:
        current = getattr(research.brief, name).value if hasattr(research.brief, name) else None
        before_bits.append(f"{name}={_shown(current)}")
        after_bits.append(f"{name}={_shown(value)}")
    version_number = research.current_version_number or 0
    request = ConfirmRequest(
        request_id=f"settings-{research.research_id}-v{version_number}",
        kind=ConfirmKind.SETTINGS,
        proposed_change=f"改前：{'；'.join(before_bits)} 改后：{'；'.join(after_bits)}",
        reason="这项修改要确认后才会写入。活动 brief 在确认前保持不变。",
        effect="同意后开新版。可拒绝并保持原设定。",
        change_class=ChangeClass.PARAM,
        patch=tuple(updates),
        created_at=now,
        return_status=research.status,
    )
    opened = transition(research, ResearchEvent.REQUEST_CONFIRM, now, request)
    return _reply(
        opened,
        text,
        f"待确认 {request.request_id}。{request.proposed_change} {request.effect}",
        now,
    )


def _reply(research: Research, user: str, answer: str, now: datetime) -> Research:
    with_user = append_dialogue(research, DialogueRole.USER, user, now)
    return append_dialogue(with_user, DialogueRole.ASSISTANT, answer, now)


def _run_command(
    research: Research,
    text: str,
    now: datetime,
    command: dict[str, Any],
    reply: str,
    perform: Perform | None,
) -> Research:
    with_user = append_dialogue(research, DialogueRole.USER, text, now)
    if perform is None:
        return append_dialogue(with_user, DialogueRole.ASSISTANT, reply, now)
    try:
        updated = perform(with_user, command)
    except (ValueError, KeyError) as error:
        return append_dialogue(with_user, DialogueRole.ASSISTANT, str(error), now)
    return append_dialogue(updated, DialogueRole.ASSISTANT, reply, now)


_CHANGE = re.compile(r"^(改逻辑|change the logic|change logic)\b\s*:?\s*(.*)$", re.IGNORECASE)


def apply_runtime_dialogue(
    research: Research,
    message: str,
    now: datetime,
    *,
    store=None,
    perform: Perform | None = None,
) -> Research | None:
    """Return an updated research when the utterance is a runtime action.

    None means the existing draft or modification parser should keep it.
    """
    text = message.strip()
    if not text:
        return None
    normalized = _norm(text)
    allowed = set(executable_commands(research.status))

    if normalized in {"先看看", "just look", "just looking"} or _is_status_question(normalized):
        return _reply(research, text, _answer_status(research), now)

    if _is_gate_question(normalized):
        return _reply(research, text, _answer_gate(research), now)

    if _is_tried_question(normalized):
        return _reply(research, text, _answer_tried(research), now)

    if _is_previous_question(normalized):
        return _reply(research, text, _answer_previous(research), now)

    change = _CHANGE.match(normalized)
    if change is not None and research.status is not ResearchStatus.DRAFT:
        after = change.group(2).strip()
        if research.pending_confirm is not None:
            pending_id = research.pending_confirm.request_id
            return _reply(
                research,
                text,
                f"已有待确认卡 {pending_id}。活动 brief 未修改。{_commands(research)}",
                now,
            )
        request = replace(_logic_request(research, after, now), return_status=research.status)
        opened = transition(research, ResearchEvent.REQUEST_CONFIRM, now, request)
        return _reply(opened, text, f"待确认 {request.request_id}。{request.proposed_change} {request.effect}", now)

    if normalized in {"重验上一轮的稳定性", "reverify last round", "reverify the last round"}:
        choices = _reverify_choices(research)
        if not choices:
            return _reply(research, text, f"{MISSING} {_commands(research)}", now)
        if len(choices) > 1:
            rendered = "；".join(
                f"round_id={round_id} method_id={method_id} revision={revision}"
                for round_id, method_id, revision in choices
            )
            return _reply(research, text, f"重验目标不唯一，请选择：{rendered}", now)
        round_id, method_id, revision = choices[0]
        if "reverify" not in allowed:
            return _reply(research, text, f"当前不能重验。{_commands(research)}", now)
        return _run_command(
            research,
            text,
            now,
            {"type": "reverify", "round_id": round_id, "method_id": method_id, "revision": revision},
            f"已提交与按钮相同的命令：reverify round_id={round_id} method_id={method_id} revision={revision}",
            perform,
        )

    if normalized in {"导出", "export"}:
        return _reply(research, text, _answer_export(research), now)

    if normalized in {"暂停", "pause"}:
        if "pause" not in allowed:
            return _reply(research, text, f"当前不能暂停。{_commands(research)}", now)
        return _run_command(
            research,
            text,
            now,
            {"type": "pause"},
            "已提交与按钮相同的命令：pause",
            perform,
        )

    if normalized in {"恢复", "resume"}:
        if "resume" not in allowed:
            return _reply(research, text, f"当前不能恢复。{_commands(research)}", now)
        return _run_command(
            research,
            text,
            now,
            {"type": "resume"},
            "已提交与按钮相同的命令：resume",
            perform,
        )

    if normalized in {"继续迭代", "continue iterating"}:
        if "continue_iterate" not in allowed:
            return _reply(research, text, f"当前不能继续迭代。{_commands(research)}", now)
        return _run_command(
            research,
            text,
            now,
            {"type": "continue_iterate", "user_confirmed": True},
            "已提交与按钮相同的命令：continue_iterate",
            perform,
        )

    if research.status is not ResearchStatus.DRAFT:
        from engine.dialogue.intent import IntentKind
        from engine.dialogue.modification import interpret_modification

        intent = interpret_modification(text, research)
        if intent.kind is IntentKind.PROVIDE and intent.updates:
            return _settings_confirm(research, text, intent.updates, now)

    if normalized in {
        "建议方法",
        "方法库",
        "有什么检验",
        "suggest a method",
        "suggest methods",
        "what methods",
    } or normalized.startswith(("建议方法 ", "suggest a method ")):
        query = normalized
        for prefix in ("建议方法 ", "suggest a method "):
            if normalized.startswith(prefix):
                query = normalized[len(prefix):].strip()
        return _reply(research, text, _answer_methods(research, store, query), now)

    return None


def apply_logic_proposal(research: Research) -> Research:
    """Apply a stored logic proposal onto the brief at confirm time."""
    proposal = research.logic_proposal
    if proposal is None:
        return research
    brief = research.brief
    for field_name, value in proposal.patch:
        if hasattr(brief, field_name):
            brief = replace(brief, **{field_name: Slot(value, True)})  # type: ignore[arg-type]
    return replace(research, brief=brief, logic_proposal=None)
