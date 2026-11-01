"""Turn a draft sentence into a schema-limited proposal.

The rules parser is the authority for markets, symbols, and hard constraints.
A configured model may only return the closed object. On timeout, bad JSON,
a missing key, or quota failure the draft falls back to field questions.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Protocol

from engine.dialogue.intent import hour_correction_conflict
from engine.dialogue.proposal_model import (
    CapabilityMatch,
    FieldChange,
    MaterialQuery,
    OpenQuestion,
    Proposal,
    QuoteRef,
)
from engine.dialogue.slots import dialogue_brief_fingerprint
from engine.research.family_intent import classify_thesis as family_of
from engine.research.llm_config import (
    DRAFT_TIMEOUT_SECONDS,
    LlmCallError,
    post_llm_draft,
    resolve_llm_for_purpose,
)
from engine.research.models import Research
from engine.research.state_machine import all_slots_locked
from engine.research.symbol_identity import extract_symbol_mentions
from engine.research.user_errors import UserFacingError

DRAFT_INPUT_CHAR_LIMIT = 4000
PROMPT_VERSION = "draft-2026-11-01"
MATERIAL_POLICY_REVISION = "material-query-2026-11-01"
CHEAP_QUESTION = (
    "“便宜”会改变策略含义。你指的是价格相对近期的偏离，还是估值便宜？"
    "还没说明之前，不会当成你已经同意均值回归。"
)
CAPABILITY_QUESTION = (
    "同行业比较和第三天卖出，当前引擎做不到。若改成不带这两条的均值回归，含义会变。"
    "要这样继续，还是先保留原话？"
)
RUN_NOW_NOTE = "开跑要在确认卡上核对这份提议后再按。附件或这句话不能代替确认。"
LLM_FALLBACK_NOTE = "模型没有给出可用的提议，下面仍按字段提问。"
MEANING_NOTE = (
    "原来的说法不会照原样执行。改成均值回归后，赚的是价格偏离后的回归，不是原来的趋势或突破。"
)
EXECUTABLE_MEAN_REVERSION = "日频截面均值回归（前一日信号）。未支持的限制不会悄悄删掉。"
PROPOSAL_STALE = "PROPOSAL_STALE"
PROPOSAL_STALE_ZH = "这份提议已经过期。请再核对设定，确认后才能开跑。"
PROPOSAL_SOURCE_CHANGED = "PROPOSAL_SOURCE_CHANGED"
PROPOSAL_SOURCE_CHANGED_ZH = "数据源和提议里写的不一样。先核对来源，再确认开跑。"
QUOTES_UNAVAILABLE = "QUOTES_UNAVAILABLE"
QUOTES_UNAVAILABLE_ZH = "报价现在不可用。等数据恢复，或改用有报价的标的后再开跑。"
CAPABILITY_UNRESOLVED = "CAPABILITY_UNRESOLVED"
CAPABILITY_UNRESOLVED_ZH = "有些限制当前做不到。请确认是否改变含义后再开跑。"
MEANING_UNRESOLVED = "MEANING_UNRESOLVED"
MEANING_UNRESOLVED_ZH = "“便宜”还没说清是价格偏离还是估值。说清之前不能开跑。"

CAPABILITIES = (
    "propose_brief",
    "family.mean_reversion",
    "market.US",
    "market.CN",
    "method.overfit.walk",
    "method.stability.oos",
    "method.crowding.load",
    "method.cost.turnover",
    "coverage_floor",
)
_ALLOWED_FIELDS = frozenset(
    {"thesis", "universe", "max_effective_hours", "round1_methods", "coverage_floor"}
)
_CLOSED_TOP = frozenset({"kind", "intent", "fields", "open_questions", "capability_match"})
_FORBIDDEN_KEYS = frozenset(
    {
        "user_agreed",
        "useragreed",
        "agreed",
        "revision",
        "base_revision",
        "proposal_id",
        "tool",
        "tool_calls",
        "function_call",
        "shell",
        "sql",
        "path",
        "url",
        "command",
        "tools",
    }
)
_INJECTION = re.compile(
    r"(?:;|\|\||&&|`|\$\(|\bDROP\b|\bSELECT\b|\bINSERT\b|https?://|[A-Za-z]:\\|/(?:home|Users|tmp|var)/)",
    re.IGNORECASE,
)
_RUN_NOW = re.compile(
    r"立刻开跑|马上开跑|立即开跑|start(?: the)? run(?: now)?|\brun now\b",
    re.IGNORECASE,
)
_CHEAP = re.compile(r"便宜|cheap", re.IGNORECASE)
_CHEAP_RESOLVED = re.compile(
    r"价格偏离|偏离|估值|valuation|price deviation|z-?score",
    re.IGNORECASE,
)
_INDUSTRY = re.compile(
    r"同行业|行业内|行业中性|within the same industry|same-industry|industry-neutral",
    re.IGNORECASE,
)
_HOLDING_DAY = re.compile(
    r"第\s*[三3]\s*天|第三天卖出|sell on (?:the )?(?:third|3rd) day|\bday\s*3\b",
    re.IGNORECASE,
)
_WAIVE = re.compile(
    r"去掉(?:这两条|行业|持有|第三天)|不带这两条|drop the industry|without those limits|leave out the industry",
    re.IGNORECASE,
)
_NO_MATERIALS = re.compile(
    r"无资料|没有资料|没资料|没有文献|no materials|without materials|no papers",
    re.IGNORECASE,
)
_SOURCE_MARKS = (
    ("akshare_sina_daily", re.compile(r"akshare|阿克|新浪", re.IGNORECASE)),
    ("yahoo_daily", re.compile(r"yahoo|雅虎", re.IGNORECASE)),
)
_SOURCE_CHANGE = re.compile(r"改用|换成|改为|switch to|instead", re.IGNORECASE)
_PATH = re.compile(r"(?:[A-Za-z]:\\[^\s\"']+|/(?:home|Users|tmp|var|opt|private)/[^\s\"']+)")
_PUBLIC_FAMILY_TERMS = {
    "mean_reversion": ("mean reversion",),
    "fundamental_factor": ("fundamental factor",),
    "low_volatility": ("low volatility",),
    "stock_bond_rebalance": ("stock bond rebalance",),
    "all_weather": ("all weather",),
    "momentum": ("momentum",),
    "growth": ("growth",),
    "arbitrage": ("arbitrage",),
    "rotation": ("rotation",),
}
_PUBLIC_ISSUERS = frozenset({"AAPL", "MSFT", "SPY"})
_CN_SUFFIX = (".SH", ".SZ", ".BJ")

SYSTEM_PROMPT = (
    "Return one JSON object and nothing else. "
    'kind must be "interpret_brief". '
    "fields may only use thesis, universe, max_effective_hours, round1_methods, coverage_floor. "
    "Do not emit tools, shell, SQL, paths, URLs, revision, or user_agreed."
)


@dataclass(frozen=True, slots=True)
class ProposeContext:
    message: str
    research: Research
    before: Research
    base_revision: int
    forbidden: tuple[str, ...] = ()
    prompt_version: str = PROMPT_VERSION
    role: str = "draft_interpreter"


class Proposer(Protocol):
    def propose(self, context: ProposeContext) -> Proposal:
        """Read one turn and return a closed proposal."""


def is_run_now_attachment(text: str) -> bool:
    """True when the turn only demands an immediate start, including via an attachment."""
    if _RUN_NOW.search(text) is None:
        return False
    remainder = _RUN_NOW.sub(" ", text)
    remainder = re.sub(
        r"附件|attachment|见|里|中|要求|请|：|:|，|,|。|\.|\s+",
        "",
        remainder,
        flags=re.IGNORECASE,
    )
    return remainder == ""


def strip_run_now(text: str) -> str:
    return _RUN_NOW.sub(" ", text).strip()


def cheap_ambiguity(text: str) -> bool:
    return _CHEAP.search(text) is not None and _CHEAP_RESOLVED.search(text) is None


def project_material_query(
    thesis: str,
    family_id: str,
    authorized_issuers: tuple[str, ...] = (),
) -> MaterialQuery:
    """Allowlisted public terms. The raw thesis is not a query, even if it matches nothing else."""
    del thesis  # retained so callers cannot pass it in by position as a term
    terms = list(_PUBLIC_FAMILY_TERMS.get(family_id, ()))
    for issuer in authorized_issuers:
        token = issuer.strip().upper()
        if token in _PUBLIC_ISSUERS:
            terms.append(token)
    unique = tuple(dict.fromkeys(terms))
    return MaterialQuery(
        public_terms=unique,
        provider_id="crossref",
        purpose="public_literature",
        policy_revision=MATERIAL_POLICY_REVISION,
    )


def scrub_model_text(text: str, forbidden: tuple[str, ...]) -> str:
    cleaned = text[:DRAFT_INPUT_CHAR_LIMIT]
    for item in forbidden:
        if item:
            cleaned = cleaned.replace(item, "")
    return _PATH.sub("", cleaned)


def build_draft_messages(
    message: str,
    *,
    forbidden: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = CAPABILITIES,
    open_questions: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    user = {
        "role": "draft_interpreter",
        "prompt_version": PROMPT_VERSION,
        "message": scrub_model_text(message, forbidden),
        "capabilities": list(capabilities),
        "open_questions": list(open_questions),
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def validate_model_object(payload: object) -> None:
    """Reject anything outside the closed draft schema, including tool calls."""
    if not isinstance(payload, dict):
        raise TypeError("schema")
    keys = {str(key) for key in payload}
    if keys - _CLOSED_TOP or payload.get("kind") != "interpret_brief":
        raise ValueError("schema")
    if keys & _FORBIDDEN_KEYS:
        raise ValueError("forbidden")
    fields = payload.get("fields", [])
    if not isinstance(fields, list):
        raise TypeError("schema")
    for item in fields:
        if not isinstance(item, dict) or item.get("field") not in _ALLOWED_FIELDS:
            raise ValueError("unregistered")
    _reject_injections(payload)


def _reject_injections(value: object) -> None:
    if isinstance(value, str):
        if _INJECTION.search(value):
            raise ValueError("injection")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValueError("forbidden")
            _reject_injections(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_injections(item)


def _proposal_id(research_id: str, base_revision: int, message: str, turns: int) -> str:
    raw = f"{research_id}\n{base_revision}\n{turns}\n{message}"
    return "p-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cn_mention(mention: object) -> bool:
    raw = str(getattr(mention, "raw", ""))
    canonical = str(getattr(mention, "canonical", "") or "")
    if re.fullmatch(r"\d{6}(?:\.[A-Za-z]{2})?", raw):
        return True
    return canonical.endswith(_CN_SUFFIX)


def _mixed_markets(message: str) -> bool:
    mentions = extract_symbol_mentions(message)
    cn = any(_cn_mention(mention) for mention in mentions)
    us = any(
        getattr(mention, "canonical", None) and not _cn_mention(mention) for mention in mentions
    )
    return cn and us


def _named_symbols(message: str) -> bool:
    return any(getattr(mention, "kind", "") == "symbol" for mention in extract_symbol_mentions(message))


def _mentioned_source(message: str) -> str:
    found: list[tuple[int, str]] = []
    for source_id, pattern in _SOURCE_MARKS:
        for match in pattern.finditer(message):
            found.append((match.start(), source_id))
    if not found:
        return ""
    found.sort()
    if len(found) == 1:
        return found[0][1]
    if _SOURCE_CHANGE.search(message):
        return found[-1][1]
    return ""


def _hard_constraints(message: str) -> tuple[CapabilityMatch, ...]:
    found: list[CapabilityMatch] = []
    if _INDUSTRY.search(message):
        found.append(
            CapabilityMatch(
                constraint="只在同行业内比较",
                capability="industry_relative",
                supported=False,
                note="引擎没有行业相对比较。这条限制会保留，不会悄悄删掉。",
            )
        )
    if _HOLDING_DAY.search(message):
        found.append(
            CapabilityMatch(
                constraint="第三天卖出",
                capability="holding_day_exit",
                supported=False,
                note="引擎没有固定第 N 天卖出。这条限制会保留，不会悄悄删掉。",
            )
        )
    return tuple(found)


def _merge_capabilities(
    prior: tuple[CapabilityMatch, ...],
    fresh: tuple[CapabilityMatch, ...],
) -> tuple[CapabilityMatch, ...]:
    by_name = {item.capability: item for item in prior}
    for item in fresh:
        by_name[item.capability] = item
    return tuple(by_name.values())


def _field_changes(before: Research, after: Research, message: str) -> tuple[FieldChange, ...]:
    changes: list[FieldChange] = []
    if before.brief.thesis.value != after.brief.thesis.value:
        text = str(after.brief.thesis.value or "")
        changes.append(
            FieldChange(
                field="thesis",
                value_kind="thesis",
                source="user_specified",
                quote_ref="q0",
                text=text,
            )
        )
    before_universe = before.brief.universe.value
    after_universe = after.brief.universe.value
    before_key = None if before_universe is None else (
        before_universe.market.value,
        before_universe.market_unspecified,
        before_universe.user_symbols_override,
        before_universe.symbols if before_universe.user_symbols_override else (),
    )
    after_key = None if after_universe is None else (
        after_universe.market.value,
        after_universe.market_unspecified,
        after_universe.user_symbols_override,
        after_universe.symbols if after_universe.user_symbols_override else (),
    )
    if before_key != after_key and after_universe is not None:
        if _mixed_markets(message) or after_universe.market_unspecified:
            source = "pending_confirm"
        elif re.search(r"美股|美国|A\s*股|中国|沪深|\bUS\b|\bCN\b", message, re.IGNORECASE):
            source = "user_specified"
        else:
            source = "derived_from_data"
        changes.append(
            FieldChange(
                field="universe",
                value_kind="universe",
                source=source,
                quote_ref="q0",
                text=after_universe.market.value,
                market=after_universe.market.value,
                asset=after_universe.asset_class.value,
                symbols=after_universe.symbols if after_universe.user_symbols_override else (),
            )
        )
    if before.brief.max_effective_hours.value != after.brief.max_effective_hours.value:
        hours = after.brief.max_effective_hours.value
        changes.append(
            FieldChange(
                field="max_effective_hours",
                value_kind="hours",
                source="user_specified",
                quote_ref="q0",
                text="" if hours is None else str(hours),
                hours=None if hours is None else float(hours),
            )
        )
    before_methods = before.brief.round1_methods.value or ()
    after_methods = after.brief.round1_methods.value or ()
    if before_methods != after_methods:
        changes.append(
            FieldChange(
                field="round1_methods",
                value_kind="methods",
                source="user_specified",
                quote_ref="q0",
                text=",".join(item.method_id for item in after_methods),
                method_ids=tuple(item.method_id for item in after_methods),
            )
        )
    if before.brief.coverage_floor.value != after.brief.coverage_floor.value:
        floor = after.brief.coverage_floor.value
        changes.append(
            FieldChange(
                field="coverage_floor",
                value_kind="coverage",
                source="user_specified",
                quote_ref="q0",
                text="" if floor is None else f"{floor.min_assets}/{floor.min_years}/{floor.max_missing_pct}",
                min_assets=None if floor is None else floor.min_assets,
                min_years=None if floor is None else floor.min_years,
                max_missing_pct=None if floor is None else floor.max_missing_pct,
            )
        )
    return tuple(changes)


def rules_propose(context: ProposeContext) -> Proposal:
    message = context.message.strip()
    research = context.research
    before = context.before
    prior = before.active_proposal
    original = str(research.brief.thesis.value or research.pending_non_mr_thesis or message)
    family = family_of(original)
    questions: list[OpenQuestion] = []
    capabilities = _merge_capabilities(
        prior.capability_match if prior is not None else (),
        _hard_constraints(message),
    )
    waived = bool(prior and prior.constraints_waived) or _WAIVE.search(message) is not None
    if waived:
        capabilities = _merge_capabilities(capabilities, _hard_constraints(message))
    block_code = ""
    next_step = ""
    primary = ""
    meaning = ""
    executable = ""
    executable_source = ""
    intent = "provide"

    unsupported = tuple(item for item in capabilities if not item.supported)
    if unsupported and not waived and family.outcome == "run":
        block_code = CAPABILITY_UNRESOLVED
        next_step = CAPABILITY_UNRESOLVED_ZH
        primary = CAPABILITY_QUESTION
        questions.append(OpenQuestion("thesis", CAPABILITY_QUESTION, True))
    if research.repicked_family == "mean_reversion" and family.outcome == "block":
        meaning = MEANING_NOTE
        executable = EXECUTABLE_MEAN_REVERSION
        executable_source = "system_suggested"
        block_code = ""
        next_step = ""
        primary = ""
        intent = "correct"
    elif family.outcome == "block":
        capabilities = _merge_capabilities(
            capabilities,
            (
                CapabilityMatch(
                    constraint=original,
                    capability="family.momentum",
                    supported=False,
                    note="趋势、动量和突破不能在这里执行。原话会保留，不会改写成均值回归。",
                ),
            ),
        )
        intent = "clarify"
        executable = ""
        executable_source = ""
    elif family.outcome == "run" and not unsupported:
        executable = EXECUTABLE_MEAN_REVERSION
        executable_source = "system_suggested"
    elif waived and family.outcome == "run":
        meaning = "去掉未支持的限制后，实际执行的是日频均值回归，和原话不是同一个含义。"
        executable = EXECUTABLE_MEAN_REVERSION
        executable_source = "system_suggested"
        intent = "correct"

    if cheap_ambiguity(message) and family.outcome == "none":
        questions.insert(0, OpenQuestion("thesis", CHEAP_QUESTION, True))
        block_code = MEANING_UNRESOLVED
        next_step = MEANING_UNRESOLVED_ZH
        primary = CHEAP_QUESTION
        intent = "clarify"
        executable = ""
        executable_source = ""
    elif cheap_ambiguity(message) and family.outcome == "run" and not block_code:
        questions.insert(0, OpenQuestion("thesis", CHEAP_QUESTION, True))
        block_code = MEANING_UNRESOLVED
        next_step = MEANING_UNRESOLVED_ZH
        primary = CHEAP_QUESTION
    elif cheap_ambiguity(message) and family.outcome == "run":
        questions.insert(0, OpenQuestion("thesis", CHEAP_QUESTION, True))

    if hour_correction_conflict(message, before):
        questions.insert(
            0,
            OpenQuestion(
                "max_effective_hours",
                "你说的原来的时长和现在记下的不一样。要改成哪一个？",
                True,
            ),
        )
        if not block_code:
            block_code = MEANING_UNRESOLVED
            next_step = "你说的原来的时长和现在记下的不一样。要改成哪一个？"
            primary = next_step

    if _mixed_markets(message):
        questions.insert(
            0,
            OpenQuestion(
                "universe",
                "这句话同时有美股和 A 股。一次研究只能留一个市场。",
                True,
            ),
        )

    if _NO_MATERIALS.search(message):
        questions.append(
            OpenQuestion(
                "materials",
                "没有本地资料。公开检索只会使用白名单里的家族词，不会把原话发给资料源。",
                False,
            )
        )

    if is_run_now_attachment(message):
        intent = "clarify"
        next_step = RUN_NOW_NOTE
        primary = RUN_NOW_NOTE
        questions.append(OpenQuestion("confirm", RUN_NOW_NOTE, False))

    questions.sort(key=lambda item: not item.changes_meaning)
    mentioned = _mentioned_source(message)
    if mentioned:
        named_source = mentioned
    elif prior is not None:
        named_source = prior.named_source
    else:
        named_source = ""
    both_sources = sum(1 for _, pattern in _SOURCE_MARKS if pattern.search(message)) > 1
    if both_sources and not _SOURCE_CHANGE.search(message):
        named_source = prior.named_source if prior is not None else ""
        questions.append(
            OpenQuestion("data_source", "这句话点了两个行情源。要换成哪一个？", True)
        )

    family_id = family.family_id if family.outcome != "none" else ""
    material = project_material_query(message, family_id)
    user_turns = sum(1 for turn in before.dialogue if turn.role.value == "user")
    return Proposal(
        proposal_id=_proposal_id(research.research_id, context.base_revision, message, user_turns),
        base_revision=context.base_revision,
        kind="interpret_brief",
        intent=intent,
        quote_refs=(QuoteRef("q0", message[:2000]),),
        changes=_field_changes(before, research, message),
        open_questions=tuple(questions),
        capability_match=capabilities,
        material_query=material,
        executable_rule=executable,
        executable_rule_source=executable_source,
        original_thesis=original[:2000],
        meaning_note=meaning,
        brief_fingerprint=dialogue_brief_fingerprint(research.brief),
        named_source=named_source,
        requires_quotes=_named_symbols(message) or bool(prior and prior.requires_quotes),
        block_code=block_code,
        next_step=next_step,
        constraints_waived=waived and not unsupported or (waived and family.outcome == "run"),
        primary_question=primary,
    )


class RulesProposer:
    def propose(self, context: ProposeContext) -> Proposal:
        return rules_propose(context)


class LlmDraftProposer:
    """Call an authorized draft endpoint. Field values still come from the rules parser."""

    def __init__(self, settings_path, *, post=None, timeout: float = DRAFT_TIMEOUT_SECONDS) -> None:
        self.settings_path = settings_path
        self.post = post or post_llm_draft
        self.timeout = timeout
        self.calls = 0

    def propose(self, context: ProposeContext) -> Proposal:
        rules = rules_propose(context)
        endpoint = resolve_llm_for_purpose(self.settings_path, "draft")
        if endpoint is None:
            return rules
        self.calls += 1
        forbidden = context.forbidden + (str(self.settings_path), endpoint.api_key)
        messages = build_draft_messages(context.message, forbidden=forbidden)
        try:
            payload = self.post(endpoint, messages, timeout=self.timeout)
            validate_model_object(payload)
            _assert_server_market(context.message, payload)
        except (LlmCallError, ValueError, TypeError, TimeoutError, OSError):
            return replace(rules, llm_calls=self.calls, llm_note=LLM_FALLBACK_NOTE)
        return replace(rules, llm_calls=self.calls)


def _assert_server_market(message: str, payload: dict[str, object]) -> None:
    """A model market that disagrees with the server parser is rejected."""
    from engine.dialogue.intent import _named_market

    server = _named_market(message)
    if server is None:
        return
    fields = payload.get("fields")
    if not isinstance(fields, list):
        return
    for item in fields:
        if not isinstance(item, dict):
            continue
        if item.get("field") not in {"universe", "market"}:
            continue
        claimed = str(item.get("market") or item.get("text") or item.get("value") or "")
        token = _market_token(claimed)
        if token and token != server.value:
            raise ValueError("server reparse")


def proposal_live_status(research: Research, data_source_id: str = "") -> str:
    proposal = research.active_proposal
    if proposal is None:
        return "open"
    if proposal.block_code == CAPABILITY_UNRESOLVED:
        return "capability"
    if proposal.block_code == MEANING_UNRESOLVED:
        return "meaning"
    source = (data_source_id or "").strip()
    if proposal.named_source and source and source != proposal.named_source:
        return "source_changed"
    if proposal.requires_quotes and research.symbol_probe_unavailable:
        return "quotes_unavailable"
    if (
        all_slots_locked(research.brief)
        and dialogue_brief_fingerprint(research.brief) != proposal.brief_fingerprint
    ):
        return "stale"
    return "open"


def proposal_blocks_run(research: Research, data_source_id: str) -> tuple[str, str] | None:
    """Gate codes that apply even to a legacy confirm. Stale binding is separate."""
    proposal = research.active_proposal
    if proposal is None:
        return None
    if proposal.block_code == CAPABILITY_UNRESOLVED:
        return CAPABILITY_UNRESOLVED, proposal.next_step or CAPABILITY_UNRESOLVED_ZH
    if proposal.block_code == MEANING_UNRESOLVED:
        return MEANING_UNRESOLVED, proposal.next_step or MEANING_UNRESOLVED_ZH
    source = (data_source_id or "").strip()
    if proposal.named_source and source and source != proposal.named_source:
        return PROPOSAL_SOURCE_CHANGED, PROPOSAL_SOURCE_CHANGED_ZH
    return None


def assert_reply_binds_proposal(research: Research, command: dict[str, object]) -> None:
    """A journaled confirm names the current proposal and its still-current brief."""
    reply = command.get("reply_to")
    if not isinstance(reply, str) or not reply:
        return
    proposal = research.active_proposal
    if proposal is None:
        return
    if proposal.proposal_id != reply:
        raise UserFacingError("PROPOSAL_NOT_CURRENT", "这条回复没有指向当前提议。")
    if proposal.requires_quotes and research.symbol_probe_unavailable:
        raise UserFacingError(QUOTES_UNAVAILABLE, QUOTES_UNAVAILABLE_ZH)
    if (
        all_slots_locked(research.brief)
        and dialogue_brief_fingerprint(research.brief) != proposal.brief_fingerprint
    ):
        raise UserFacingError(PROPOSAL_STALE, PROPOSAL_STALE_ZH)


def proposal_view(research: Research, data_source_id: str = "") -> dict[str, object]:
    proposal = research.active_proposal
    if proposal is None:
        return {}
    material = proposal.material_query
    status = proposal_live_status(research, data_source_id)
    next_step = proposal.next_step
    if status == "quotes_unavailable":
        next_step = QUOTES_UNAVAILABLE_ZH
    elif status == "source_changed":
        next_step = PROPOSAL_SOURCE_CHANGED_ZH
    elif status == "stale":
        next_step = PROPOSAL_STALE_ZH
    return {
        "proposalId": proposal.proposal_id,
        "baseRevision": proposal.base_revision,
        "kind": proposal.kind,
        "intent": proposal.intent,
        "status": status,
        "nextStep": next_step,
        "originalThesis": proposal.original_thesis,
        "executableRule": proposal.executable_rule,
        "executableRuleSource": proposal.executable_rule_source,
        "meaningNote": proposal.meaning_note,
        "blockCode": proposal.block_code,
        "quotes": [{"ref": item.ref, "text": item.text} for item in proposal.quote_refs],
        "changes": [
            {
                "field": item.field,
                "source": item.source,
                "text": item.text,
                "quoteRef": item.quote_ref,
            }
            for item in proposal.changes
        ],
        "openQuestions": [
            {
                "field": item.field,
                "question": item.question,
                "changesMeaning": item.changes_meaning,
            }
            for item in proposal.open_questions
        ],
        "capabilityMatch": [
            {
                "constraint": item.constraint,
                "capability": item.capability,
                "supported": item.supported,
                "note": item.note,
            }
            for item in proposal.capability_match
        ],
        "materialQuery": None
        if material is None
        else {
            "publicTerms": list(material.public_terms),
            "providerId": material.provider_id,
            "purpose": material.purpose,
            "policyRevision": material.policy_revision,
        },
        "llmCalls": proposal.llm_calls,
    }


def proposal_event_refs(proposal: Proposal) -> dict[str, object]:
    return {
        "proposal_id": proposal.proposal_id,
        "llm_calls": proposal.llm_calls,
        "changes": [
            {"field": item.field, "source": item.source, "text": item.text}
            for item in proposal.changes
        ],
    }


def _market_token(value: str) -> str:
    if re.search(r"A\s*股|中国|沪深|\bCN\b", value, re.IGNORECASE):
        return "CN"
    if re.search(r"美股|美国|\bUS\b", value, re.IGNORECASE):
        return "US"
    return value.strip()
