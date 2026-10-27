from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import signal
import sys
import threading
import time
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import jsonschema
import pandas as pd

from engine.dialogue.slots import first_open_slot, unlock_all_slots, unlock_slot
from engine.dialogue.pool_errors import (
    record_transient_confirm_notice,
    reopen_after_pool_failure,
)
from engine.research.confirm_view import (
    confirm_data_notice,
    symbol_resolution_payload,
    symbol_selection_payload,
)
from engine.research.data_availability import MARKET_DATA_FAILURE_CODES
from engine.research.universe_pool import (
    materialize_default_pool,
    pin_draft_data_source,
    pool_resolvable,
)
from engine.research.universe_validation import (
    answer_symbol_ask,
    apply_symbol_edit,
    choose_default_market,
    dismiss_mismatched_symbol,
    ensure_runnable_universe,
    refresh_symbol_probe,
    remove_market_side,
    revert_symbol_ask,
    use_hinted_symbol,
)
from engine.i18n.errors import build_error_envelope, redact_technical_detail
from engine.i18n.locale import (
    normalize_request_locale,
    push_request_locale,
    reset_request_locale,
)
from engine.research.user_errors import UserFacingError, classify_run_error, http_error_payload
from engine.portfolio import SCHEDULE_COST_MODEL
from engine.research.a2_copy import cn_execution_notice_for, construction_notice_for
from engine.research.thesis_scope import mean_reversion_only_notice
from engine.research.method_body_display import (
    format_method_body_display,
    method_purpose,
    revision_display_label,
    revision_token_from_body,
)
from engine.research.method_labels import format_methods_display
from engine.dialogue.turns import dialogue_turn_view, process_send_dialogue
from engine.export_paths import export_zip_filename
from engine.export import (
    build_research_record_pack,
    build_strategy_pack,
    mark_exports_overturned,
    strategy_pack_eligibility,
)
from engine.research.clock import TimeBudget
from engine.research.gather import (
    LocalMaterialAdapter,
    PapersAdapter,
    SecEdgarAdapter,
    pit_evidence_annotations,
    pit_evidence_from_payloads,
)
from engine.research.desktop_view import (
    format_coverage_floor_display,
    format_coverage_vs_floor,
    format_universe_display,
    last_reverification_summary,
    metrics_for_completed,
    pit_detail_for,
    reverify_options_for,
    rounds_for_desktop,
    selected_method_id,
    universe_label_for,
)
from engine.research.display_names import (
    METHOD_IDS,
    export_blocker_messages,
    format_display_number,
    method_label,
)
from engine.research.glossary import glossary_entries, glossary_intro
from engine.research.symbol_selection_display import format_symbol_selection_summary
from engine.research.time_display import (
    format_remaining_display,
    format_seconds,
    remaining_seconds,
)
from engine.research.data_window import late_pass_presentation, trial_tracking_for_view
from engine.research.run_errors import apply_run_failure, max_consecutive_run_errors
from engine.research.honest_stop import (
    assert_can_manual_continue,
    can_manual_continue_iterate,
    completed_presentation,
    high_suspicion_round_threshold,
    running_budget_hint,
    run_stop_reason,
    trial_budget_increment,
    trial_budget_view,
    validate_continue_iterate_confirm,
)
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.methods import (
    as_method_refs,
    create_method,
    deposit_confirmed_methods,
    distinct_research_usage_count,
    record_method_usage,
    revise_method,
    seed_preset_methods,
)
from engine.research.models import (
    AnomalyBaseline,
    AnomalyPresentation,
    EvidenceKind,
    EvidenceRef,
    ExportKind,
    ExportRecord,
    MethodSource,
    Research,
    ResearchAction,
    ConfirmKind,
    ResearchEvent,
    ResearchStatus,
    Reverification,
    Slot,
    detect_anomalies,
    new_research,
)
from engine.research.progress import (
    ResearchListItem,
    host_status,
    host_status_while_fetching,
    list_items,
    notification_event,
    thesis_divergence_hint,
)
from engine.research.runtime import (
    EngineLock,
    OwnerKind,
    OwnerRecord,
    EnginePaths,
    RuntimePaths,
    publish_ready,
    read_live_owner,
)
from engine.research.simulate import simulate_daily
from engine.research.state_machine import InvalidTransition, all_slots_locked, transition
from engine.research.store import ConcurrentWrite, SQLiteStore
from engine.review.deterministic import DeterministicReviewer
from engine.review.subagent import LLMPort, OpenAICompatibleLLM, SubagentReviewer
from engine.strategy import MarketPanel, MeanReversionStrategy
from engine.verifiers import method_set_excluding_pit, recorded_pit_revision, run_verifiers

PROTOCOL_VERSION = 1

_ACTION_LABELS = {
    ResearchAction.GATHER: "查资料",
    ResearchAction.SPECIFY: "补细节",
    ResearchAction.SIMULATE: "历史模拟",
    ResearchAction.VERIFY: "验证",
    ResearchAction.ITERATE: "迭代",
    ResearchAction.IDLE: "idle",
}


def _accepted_attempt(research: Research):
    if not research.versions or not research.versions[-1].rounds:
        return None
    return research.versions[-1].rounds[-1].accepted_attempt


def _backtest_cutoff(research: Research) -> str | None:
    attempt = _accepted_attempt(research)
    simulation = getattr(attempt, "simulation", None) if attempt is not None else None
    end = getattr(simulation, "end", None)
    if end is not None and hasattr(end, "isoformat"):
        return str(end.isoformat())
    return None


def _pit_was_executed(research: Research) -> bool | None:
    attempt = _accepted_attempt(research)
    verification = getattr(attempt, "verification", None) if attempt is not None else None
    if verification is None:
        return False
    return any(item.verifier_id == "pit.consistency" for item in verification.results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alphaloop-engine")
    parser.add_argument("--owner", choices=("desktop", "cli"), required=True)
    return parser


def _handshake(status: str, owner: OwnerRecord) -> None:
    print(
        json.dumps(
            {
                "protocol_version": PROTOCOL_VERSION,
                "status": status,
                "owner": owner.owner,
                "pid": owner.pid,
                "endpoint": owner.endpoint,
                "auth_token": owner.auth_token,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _watch_desktop_stdin(stop: threading.Event) -> None:
    while sys.stdin.buffer.read(1):
        continue
    stop.set()


class SettingsBackedLLM(LLMPort):
    """Read the endpoint when a review runs, so a settings save does not need a restart."""

    def __init__(self, client: httpx.Client, settings_path: Path) -> None:
        self._client = client
        self._settings_path = settings_path

    def complete(self, system: str, user: str) -> str:
        from engine.research.llm_config import resolve_llm

        resolved = resolve_llm(self._settings_path)
        if resolved is None:
            return FailClosedLLM().complete(system, user)
        return OpenAICompatibleLLM(
            self._client,
            resolved.base_url,
            resolved.api_key,
            resolved.model,
        ).complete(system, user)


class FailClosedLLM(LLMPort):
    def complete(self, system: str, user: str) -> str:
        return json.dumps(
            {
                "passed": False,
                "findings": [
                    {
                        "code": "review_unavailable",
                        "message": "No second-LLM reviewer credentials are configured.",
                    }
                ],
                "required_changes": (
                    "Configure ALPHALOOP_LLM_BASE_URL, "
                    "ALPHALOOP_LLM_API_KEY, and ALPHALOOP_LLM_MODEL."
                ),
            }
        )


def build_loop(
    store: SQLiteStore,
    paths: EnginePaths,
    budget: TimeBudget | None = None,
) -> ResearchLoop:
    client = httpx.Client()
    material_root = paths.data.materials_dir
    material_root.mkdir(parents=True, exist_ok=True)
    material_ports = (
        PapersAdapter(client, lambda: datetime.now(UTC)),
        SecEdgarAdapter(
            client,
            lambda: datetime.now(UTC),
            "alphaloop/0.2 research@example.invalid",
        ),
        LocalMaterialAdapter(material_root, lambda: datetime.now(UTC)),
    )
    reviewer_mode = os.environ.get("ALPHALOOP_REVIEWER", "deterministic")
    if reviewer_mode == "subagent":
        reviewer = SubagentReviewer(SettingsBackedLLM(client, paths.data.settings_file))
    else:
        reviewer = DeterministicReviewer()
    builder = DefaultRoundBuilder(
        material_ports=material_ports,
        data_port=None,
        start=None,
        end=None,
        snapshot_root=paths.data.snapshots_dir,
    )
    clock = budget or TimeBudget(time.monotonic)
    return ResearchLoop(
        store,
        builder,
        reviewer,
        clock,
        lambda: datetime.now(UTC),
    )


class ResearchCommandService:
    def __init__(
        self,
        store: SQLiteStore,
        paths: EnginePaths,
        budget: TimeBudget | None = None,
    ) -> None:
        self.store = store
        self.paths = paths
        self.budget = budget
        self._observed_status: dict[str, ResearchStatus] = {}
        self._research_locks_guard = threading.Lock()
        self._research_locks: dict[str, threading.Lock] = {}
        self.last_request_locale: str | None = None
        seed_preset_methods(store)

    def _lock_for_research(self, research_id: str) -> threading.Lock:
        with self._research_locks_guard:
            lock = self._research_locks.get(research_id)
            if lock is None:
                lock = threading.Lock()
                self._research_locks[research_id] = lock
            return lock

    def _save(self, before: Research, after: Research) -> dict[str, Any]:
        if self.budget is not None:
            if before.status is ResearchStatus.RUNNING and after.status is not ResearchStatus.RUNNING:
                after = self.budget.finish(after)
            elif before.status is not ResearchStatus.RUNNING and after.status is ResearchStatus.RUNNING:
                self.budget.begin(after.status)
        self.store.save(after, before.updated_at)
        self._observed_status[after.research_id] = after.status
        payload: dict[str, Any] = {
            "research_id": after.research_id,
            "status": after.status.value,
        }
        event = notification_event(before.status, after.status)
        if event is not None:
            payload["notify"] = event
        return payload

    def _attach_notify(self, payload: dict[str, Any]) -> dict[str, Any]:
        pending: list[str] = []
        for item in self.store.list_research():
            before = self._observed_status.get(item.research_id)
            if before is None:
                self._observed_status[item.research_id] = item.status
                continue
            event = notification_event(before, item.status)
            self._observed_status[item.research_id] = item.status
            if event is not None:
                pending.append(event)
        if pending:
            rank = {"awaiting_confirm": 0, "completed": 1, "ended": 2}
            pending.sort(key=lambda kind: rank[kind])
            payload["notify"] = pending[0]
            if len(pending) > 1:
                payload["notifies"] = pending
        return payload

    def _record_version_methods(
        self,
        research: Research,
        method_set: object | None = None,
    ) -> None:
        selected = as_method_refs(method_set) or research.brief.round1_methods.value or ()
        if research.current_version_number is None or not selected:
            return
        record_method_usage(
            self.store,
            research.research_id,
            research.current_version_number,
            selected,
        )

    @staticmethod
    def _settings(research: Research) -> dict[str, Any]:
        brief = research.brief
        hours = brief.max_effective_hours.value
        selection = symbol_selection_payload(research)
        symbols_line = format_symbol_selection_summary(selection) if selection else ""
        symbol_chips = list(selection["symbols"]) if selection else []
        return {
            "thesis": str(brief.thesis.value or ""),
            "universe": format_universe_display(
                brief.universe.value,
                include_symbols=False,
            ),
            "universe_symbols": symbols_line,
            "universe_symbol_chips": symbol_chips,
            "max_effective_hours": f"{hours:g} 小时" if hours is not None else "",
            "round1_methods": format_methods_display(brief.round1_methods.value),
            "coverage_floor": format_coverage_floor_display(brief.coverage_floor.value),
        }

    def _market_data_status(self) -> dict[str, Any]:
        """Progress without the research lock, so a confirm probe cannot hide it."""
        from engine.research.market_data_progress import market_data_progress_payload

        progress = market_data_progress_payload()
        status = host_status_while_fetching(
            host_status(self.store.list_research()),
            fetching=progress is not None,
        )
        return {"marketDataProgress": progress, "hostStatus": status}

    def _host_payload(
        self,
        payload: dict[str, Any],
        research: Research | None = None,
    ) -> dict[str, Any]:
        from engine.research.market_data_progress import market_data_progress_payload

        progress = market_data_progress_payload()
        payload["hostStatus"] = host_status_while_fetching(
            host_status(self.store.list_research()),
            fetching=progress is not None,
        )
        if progress is not None:
            payload["marketDataProgress"] = progress
        if research is not None and research.thesis_change_hint:
            payload["thesisChangeHint"] = research.thesis_change_hint
        from engine.research.offline_market_data import offline_market_data_enabled

        if offline_market_data_enabled():
            payload["testData"] = True
        return self._attach_notify(payload)

    @staticmethod
    def _list_summary(item: ResearchListItem) -> dict[str, str]:
        return {
            "id": item.research_id,
            "title": item.title,
            "status": item.list_status,
            "universeLabel": item.universe_label,
            "createdAt": item.created_at.isoformat(),
            "updatedAt": item.updated_at.isoformat(),
        }

    @staticmethod
    def _coverage_vs_floor(research: Research) -> str:
        return format_coverage_vs_floor(research)

    @staticmethod
    def _remaining(research: Research) -> str:
        return format_remaining_display(research)

    def _displayed_effective_seconds(self, research: Research) -> float:
        extra = 0.0
        if (
            self.budget is not None
            and research.status is ResearchStatus.RUNNING
        ):
            extra = self.budget.elapsed_open()
        return max(0.0, research.effective_seconds) + extra

    def _time_fields(self, research: Research) -> dict[str, Any]:
        shown = self._displayed_effective_seconds(research)
        # The open slice is display-only. Remaining stays on the stored total
        # so a poll cannot move the budget before the slice is committed.
        fields: dict[str, Any] = {
            "effective": format_seconds(shown),
            "effectiveSeconds": shown,
            "remaining": self._remaining(research),
        }
        remaining = remaining_seconds(research)
        if remaining is not None:
            fields["remainingSeconds"] = remaining
        return fields

    def _attach_unlicensed_choice(self, selection: dict[str, Any], research: Research) -> None:
        from engine.research.price_source_choice import apply_price_source_choice

        universe = research.brief.universe.value
        apply_price_source_choice(
            selection,
            market=universe.market if universe is not None else None,
            explicit_source_id=research.data_source_id,
            settings_path=self.paths.data.settings_file,
        )

    @staticmethod
    def _sources(research: Research) -> str:
        if research.versions and research.versions[-1].rounds:
            evidence = research.versions[-1].rounds[-1].accepted_attempt.evidence_paths
            if evidence:
                return "公开资料已落成本机材料"
            return "未找到相关资料"
        return "公开资料与本机材料"

    @staticmethod
    def _compute_anomaly(research: Research) -> dict[str, object] | None:
        """Compute anomaly presentation for current round if anomalies detected (B5)."""
        if not research.versions or not research.versions[-1].rounds:
            return None
        current_round = research.versions[-1].rounds[-1]
        attempt = current_round.accepted_attempt
        simulation = attempt.simulation
        sharpe = getattr(simulation, "sharpe", None)
        trial_count = attempt.number
        coverage_shrunk = len(research.coverage_history) > 0
        method_revision_age_days = 30
        baseline: AnomalyBaseline | None = None
        version = research.versions[-1]
        if len(version.rounds) >= 2:
            prior = version.rounds[-2].accepted_attempt
            prior_sim = prior.simulation
            baseline = AnomalyBaseline(
                kind="prior_accepted_attempt",
                sharpe=getattr(prior_sim, "sharpe", None),
                trial_count=prior.number,
                attempt_id=prior.attempt_id,
            )
        elif len(research.versions) >= 2:
            prior_version = research.versions[-2]
            if prior_version.rounds:
                prior = prior_version.rounds[-1].accepted_attempt
                prior_sim = prior.simulation
                baseline = AnomalyBaseline(
                    kind="version_1_logic",
                    sharpe=getattr(prior_sim, "sharpe", None),
                    trial_count=prior.number,
                    attempt_id=prior.attempt_id,
                )
        if baseline is None:
            return None
        anomaly = detect_anomalies(
            sharpe=sharpe,
            trial_count=trial_count,
            coverage_shrunk=coverage_shrunk,
            method_revision_age_days=method_revision_age_days,
            baseline=baseline,
        )
        if anomaly is None:
            return None
        return {
            "indicators": [ind.value for ind in anomaly.indicators],
            "expandEvidenceFirst": anomaly.expand_evidence_first,
            "tone": anomaly.tone,
            "baseline": {
                "kind": anomaly.baseline.kind if anomaly.baseline else None,
                "sharpe": anomaly.baseline.sharpe if anomaly.baseline else None,
                "trialCount": anomaly.baseline.trial_count if anomaly.baseline else None,
            } if anomaly.baseline else None,
        }

    @staticmethod
    def _comparison_label(comparison: str) -> str:
        return {
            "gt": "大于",
            "gte": "不小于",
            "eq": "等于",
            "lte": "不大于",
            "lt": "小于",
        }.get(comparison, comparison)

    @staticmethod
    def _dimension_kind_label(kind: str) -> str:
        return {
            "predictive_power": "预测力",
            "stability": "稳定性",
            "pit_consistency": "时点一致性",
            "cost_sensitivity": "成本敏感度",
            "crowding": "集中度",
            "custom": "自定义",
        }.get(kind, kind)

    @staticmethod
    def _method_dimensions(method_id: str, body: str) -> list[dict[str, object]]:
        """Extract Scorecard dimensions from method body (B6)."""
        dimensions: list[dict[str, object]] = []
        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return dimensions
        if method_id == "scorecard.market":
            if "sharpe_oos_min_exclusive" in parsed:
                dimensions.append({
                    "kind": "predictive_power",
                    "kindLabel": "预测力",
                    "name": "夏普比率",
                    "description": "样本外夏普比率下限",
                    "passThreshold": parsed["sharpe_oos_min_exclusive"],
                    "comparison": "gt",
                    "comparisonLabel": "大于",
                    "failureDisplay": "夏普不高于基准",
                })
            if "default_max_drawdown_floor" in parsed:
                dimensions.append({
                    "kind": "stability",
                    "kindLabel": "稳定性",
                    "name": "最大回撤",
                    "description": "回撤上限",
                    "passThreshold": parsed["default_max_drawdown_floor"],
                    "comparison": "gte",
                    "comparisonLabel": "不小于",
                    "failureDisplay": "回撤过大",
                })
        elif method_id == "overfit.walk":
            if "oos_to_is_min" in parsed:
                dimensions.append({
                    "kind": "stability",
                    "kindLabel": "稳定性",
                    "name": "样本外/样本内比",
                    "description": "样本外表现与样本内的比值下限",
                    "passThreshold": parsed["oos_to_is_min"],
                    "comparison": "gte",
                    "comparisonLabel": "不小于",
                    "failureDisplay": "分段表现未保持",
                })
        elif method_id == "stability.oos":
            if "same_sign_ratio_min" in parsed:
                dimensions.append({
                    "kind": "stability",
                    "kindLabel": "稳定性",
                    "name": "同号比例",
                    "description": "样本外分段收益方向一致的比例下限",
                    "passThreshold": parsed["same_sign_ratio_min"],
                    "comparison": "gte",
                    "comparisonLabel": "不小于",
                    "failureDisplay": "样本外方向不稳定",
                })
            if "segments_min" in parsed:
                dimensions.append({
                    "kind": "stability",
                    "kindLabel": "稳定性",
                    "name": "分段数",
                    "description": "样本外分段数量下限",
                    "passThreshold": parsed["segments_min"],
                    "comparison": "gte",
                    "comparisonLabel": "不小于",
                    "failureDisplay": "样本外分段不足",
                })
        elif method_id == "pit.consistency":
            dimensions.append({
                "kind": "pit_consistency",
                "kindLabel": "时点一致性",
                "name": "时点一致性",
                "description": "检查是否存在前视偏差",
                "passThreshold": 1.0,
                "comparison": "eq",
                "comparisonLabel": "等于",
                "failureDisplay": "存在前视偏差",
            })
        for dim in dimensions:
            threshold = dim.get("passThreshold")
            if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
                dim["passThreshold"] = format_display_number(threshold)
        return dimensions

    @staticmethod
    def _method_category(method_id: str) -> str | None:
        """Get method category (B6)."""
        if method_id.startswith("pit."):
            return "时点一致性"
        if method_id.startswith("scorecard."):
            return "计分卡"
        if method_id.startswith("overfit."):
            return "过拟合检测"
        if method_id.startswith("stability."):
            return "稳定性"
        if method_id.startswith("crowding."):
            return "集中度"
        if method_id.startswith("cost."):
            return "成本"
        return None

    def view_for(self, route: str) -> dict[str, Any]:
        if route == "#/glossary" or route.startswith("#/glossary?"):
            return self._host_payload(
                {
                    "kind": "glossary",
                    "intro": glossary_intro(),
                    "entries": [
                        {"id": entry.term_id, "term": entry.term, "body": entry.body}
                        for entry in glossary_entries()
                    ],
                }
            )
        if route.startswith("#/methods"):
            methods = [
                {
                    "id": item.method_id,
                    "name": (
                        method_label(item.method_id)
                        if item.method_id in METHOD_IDS
                        else (item.name or item.method_id)
                    ),
                    "revision": item.revision_hash,
                    "revisionLabel": revision_display_label(
                        revision_token_from_body(item.body) or item.revision_hash[:8]
                    ),
                    "description": method_purpose(item.method_id),
                    "definitionDisplay": format_method_body_display(
                        item.method_id, item.body
                    ),
                    "source": item.source.value,
                    "depositedFromResearchId": item.deposited_from_research_id,
                    "supersedes": item.supersedes,
                    "usageCount": distinct_research_usage_count(
                        self.store, item.method_id
                    ),
                    "category": self._method_category(item.method_id),
                    "dimensions": self._method_dimensions(item.method_id, item.body),
                }
                for item in self.store.list_method_definitions()
            ]
            selected = route.removeprefix("#/methods/") if route.startswith("#/methods/") else None
            if selected:
                try:
                    selected = unquote(selected)
                except ValueError:
                    pass
            return self._host_payload({"kind": "methods", "selected": selected, "methods": methods})
        if route == "#/research" or route.startswith("#/research?"):
            status_raw = None
            if "?" in route:
                for part in route.split("?", 1)[1].split("&"):
                    if part.startswith("status="):
                        status_raw = part.split("=", 1)[1]
                        break
            status_filter = ResearchStatus(status_raw) if status_raw else None
            items = list_items(self.store.list_research(), status_filter)
            summaries = [self._list_summary(item) for item in items]
            awaiting = next(
                (item for item in summaries if item["status"] == "awaiting_confirm"),
                None,
            )
            rows = [item for item in summaries if item is not awaiting]
            return self._host_payload({"kind": "research_list", "awaiting": awaiting, "rows": rows})
        research_id = route.removeprefix("#/research/")
        research = self.store.load(research_id)
        if research.status.value == "draft":
            materialized = pin_draft_data_source(materialize_default_pool(research))
            if all_slots_locked(materialized.brief):
                materialized = refresh_symbol_probe(materialized)
            if (
                materialized.brief != research.brief
                or materialized.data_source_id != research.data_source_id
                or materialized.symbol_probe_symbols != research.symbol_probe_symbols
                or materialized.symbol_probe_missing != research.symbol_probe_missing
                or materialized.symbol_probe_unavailable != research.symbol_probe_unavailable
            ):
                self.store.save(materialized, research.updated_at)
                research = materialized
            view_kind = "confirm_run" if all_slots_locked(research.brief) else "draft"
            universe = research.brief.universe.value
            named_symbols = universe is not None and (
                universe.user_symbols_override or bool(universe.unresolved_tokens)
            )
            from engine.research.family_choice import family_choice_payload, reply_open

            family_reply = reply_open(research)
            chat_enabled = view_kind == "draft" or not pool_resolvable(research) or family_reply
            if view_kind == "confirm_run" and named_symbols and not family_reply:
                chat_enabled = False
            body: dict[str, Any] = {
                "kind": view_kind,
                "researchId": research_id,
                "dialogue": [dialogue_turn_view(turn) for turn in research.dialogue],
                "settings": self._settings(research),
                "chatEnabled": chat_enabled,
                **family_choice_payload(research),
            }
            if view_kind == "confirm_run":
                body["symbolSelection"] = symbol_selection_payload(research)
                resolution = symbol_resolution_payload(research)
                if resolution is not None:
                    body["symbolResolution"] = resolution
                fetch_notice = confirm_data_notice(research)
                if fetch_notice:
                    body["confirmDataNotice"] = fetch_notice["text"]
                    if fetch_notice.get("code"):
                        body["confirmDataNoticeCode"] = fetch_notice["code"]
                        body["confirmDataNoticeParams"] = fetch_notice.get("params") or {}
                notice = mean_reversion_only_notice(
                    str(research.brief.thesis.value or ""),
                    adopted=research.mean_reversion_adopted,
                    repicked_family=research.repicked_family,
                )
                if notice:
                    body["meanReversionOnlyNotice"] = notice
                if research.repicked_family:
                    body["repickedFamily"] = research.repicked_family
                construction = construction_notice_for(research)
                if construction:
                    body["constructionNotice"] = construction
                if universe is not None and not universe.market_unspecified:
                    body["market"] = universe.market.value
                if research.market_switch_market:
                    body["marketSwitch"] = {
                        "market": research.market_switch_market,
                        "benchmark": research.market_switch_benchmark,
                    }
                if universe is not None and universe.market_unspecified:
                    from engine.research.models import AssetClass, Market
                    from engine.research.symbol_pool import pool_for_market

                    cn_pool = pool_for_market(Market.CN, AssetClass.EQUITY, AssetClass.EQUITY)
                    us_pool = pool_for_market(Market.US, AssetClass.EQUITY, AssetClass.EQUITY)
                    body["marketChoice"] = {
                        "pending": True,
                        "cnCount": len(cn_pool.symbols) if cn_pool is not None else 0,
                        "usCount": len(us_pool.symbols) if us_pool is not None else 0,
                    }
                elif universe is not None:
                    from engine.metrics import benchmark_for

                    body["benchmarkName"] = benchmark_for(universe).name
                selection = body.get("symbolSelection")
                if isinstance(selection, dict):
                    self._attach_unlicensed_choice(selection, research)
                from engine.research.run_gate import evaluate_run_gate

                gate = evaluate_run_gate(
                    research,
                    data_source_id=research.data_source_id,
                    unlicensed_acknowledged=False,
                    settings_path=self.paths.data.settings_file,
                )
                gate_payload: dict[str, Any] = {"runnable": gate.runnable, "code": gate.code}
                if gate.params:
                    gate_payload["params"] = gate.params
                body["runGate"] = gate_payload
            return self._host_payload(body, research)
        if research.status.value in {"running", "paused"}:
            version = research.current_version_number or 1
            cutoff = (
                research.data_window_end.isoformat()
                if research.data_window_end is not None
                else (
                    research.last_coverage.end.isoformat()
                    if research.last_coverage is not None
                    else None
                )
            )
            version_notice = None
            if research.dialogue:
                last_turn = research.dialogue[-1]
                if last_turn.role.value == "assistant" and last_turn.text.startswith(
                    "已开始第"
                ):
                    version_notice = last_turn.text
            running_payload: dict[str, Any] = {
                "kind": "running",
                "researchId": research_id,
                "status": research.status.value,
                "version": version,
                **self._time_fields(research),
                "effectiveTimeHint": (
                    "有效研究时间计入「运行中」状态下的采集、建模与验证执行；"
                    "暂停、等待确认与列表轮询间隔不计入。"
                ),
                "coverage": self._coverage_vs_floor(research),
                "rounds": rounds_for_desktop(research, version),
                "sources": self._sources(research),
                "anomaly": self._compute_anomaly(research),
            }
            if cutoff is not None:
                running_payload["dataCutoff"] = cutoff
            budget = trial_budget_view(research)
            hint = running_budget_hint(research, self.store)
            running_payload["trialBudget"] = {
                "used": budget.used,
                "budget": budget.budget,
                "remaining": budget.remaining,
            }
            if hint:
                running_payload["honestStopHint"] = hint
            if version_notice:
                running_payload["versionOpenedNotice"] = version_notice
            if research.current_action is not ResearchAction.IDLE:
                running_payload["currentAction"] = _ACTION_LABELS[research.current_action]
            if research.last_run_error:
                running_payload["lastError"] = {
                    "message": research.last_run_error,
                    "count": research.consecutive_identical_run_errors,
                }
                if research.last_run_error_code:
                    running_payload["lastError"]["code"] = research.last_run_error_code
                if research.last_run_error_params:
                    running_payload["lastError"]["params"] = dict(research.last_run_error_params)
                if research.last_run_error_detail:
                    running_payload["lastError"]["detail"] = redact_technical_detail(
                        research.last_run_error_detail
                    )
            running_payload.update(trial_tracking_for_view(research, self.store))
            running_payload["highSuspicionRoundThreshold"] = high_suspicion_round_threshold()
            late = late_pass_presentation(research)
            if late is not None:
                running_payload["latePassPresentation"] = late
            return self._host_payload(running_payload, research)
        if research.status.value == "awaiting_confirm":
            request = research.pending_confirm
            if request is None:
                raise ValueError("awaiting_confirm research requires ConfirmRequest")
            return self._host_payload(
                {
                    "kind": "awaiting_confirm",
                    "researchId": research_id,
                    "version": research.current_version_number or 1,
                    "confirmKind": request.kind.value,
                    "proposed": request.proposed_change,
                    "reason": request.reason,
                    "effect": request.effect,
                    "whyChange": [
                        {
                            "recordId": ref.record_id,
                            "recordedAt": ref.recorded_at.isoformat(),
                            "kind": ref.kind.value,
                            "summary": ref.summary,
                        }
                        for ref in request.why_change
                    ],
                    "whoPaysOptional": request.who_pays_optional,
                    "createdAt": request.created_at.isoformat() if request.created_at else None,
                    "requestId": request.request_id,
                },
                research,
            )
        rounds = research.versions[-1].rounds if research.versions else ()
        selected_round = rounds[-1] if rounds else None
        eligibility = strategy_pack_eligibility(research)
        presentation = completed_presentation(research, self.store)
        version_number = research.current_version_number or 1
        subtitle = universe_label_for(research)
        return self._host_payload(
            {
                "kind": "completed",
                "researchId": research_id,
                "version": version_number,
                **self._time_fields(research),
                "stopReason": run_stop_reason(research),
                "sources": self._sources(research),
                "status": research.status.value,
                "title": str(research.brief.thesis.value or "研究结果"),
                "meanReversionOnlyNotice": mean_reversion_only_notice(
                    str(research.brief.thesis.value or ""),
                    adopted=research.mean_reversion_adopted,
                    repicked_family=research.repicked_family,
                ),
                "repickedFamily": research.repicked_family or None,
                "cnExecutionNotice": cn_execution_notice_for(research),
                "universeLabel": subtitle,
                "subtitle": presentation.summary,
                "resultHeadline": presentation.headline,
                "honestStopHint": presentation.hint_line or None,
                "failedVerifierIds": list(presentation.failed_verifier_ids),
                "exportKind": presentation.export_kind,
                "trialBudget": {
                    "used": presentation.trial_budget.used,
                    "budget": presentation.trial_budget.budget,
                    "remaining": presentation.trial_budget.remaining,
                },
                "budgetExhausted": presentation.budget_exhausted,
                "canContinueIterate": can_manual_continue_iterate(research),
                "deferredChangeSummary": presentation.deferred_change_summary,
                **trial_tracking_for_view(research, self.store),
                "highSuspicionRoundThreshold": high_suspicion_round_threshold(),
                "latePassPresentation": late_pass_presentation(research),
                "trialCounters": presentation.trial_counters,
                "methodsVerificationPassed": presentation.methods_verification_passed,
                "selectedRoundId": selected_round.round_id if selected_round else "",
                "selectedMethodId": selected_method_id(research),
                "rounds": rounds_for_desktop(research, version_number),
                "metrics": metrics_for_completed(research),
                "failedExportChecks": list(eligibility.failed_checks),
                "exportBlockerMessages": list(
                    export_blocker_messages(
                        eligibility.failed_checks,
                        pit_executed=_pit_was_executed(research),
                    )
                ),
                "symbolSelection": symbol_selection_payload(research),
                "backtestCutoff": _backtest_cutoff(research),
                "reverifyOptions": reverify_options_for(research),
                "lastReverification": last_reverification_summary(research),
                "pitDetail": pit_detail_for(research),
                "eligibility": {
                    "allMethodsPassed": presentation.methods_verification_passed,
                    "noPendingConfirm": "no_pending_confirm" not in eligibility.failed_checks,
                    "reverifiesPassed": "all_reverifies_passed" not in eligibility.failed_checks,
                    "pitExecutedAndPassed": "pit_executed_and_passed" not in eligibility.failed_checks,
                },
                "overturnedExports": any(item.overturned for item in research.exports),
                "currentAction": _ACTION_LABELS[research.current_action],
                "anomaly": self._compute_anomaly(research),
                "recentDialogue": [
                    dialogue_turn_view(turn) for turn in research.dialogue[-8:]
                ],
            },
            research,
        )

    def _confirm_run(
        self,
        research_id: str,
        now: datetime,
        *,
        data_source_id: str | None = None,
        unlicensed_acknowledged: bool = False,
    ) -> dict[str, Any]:
        """Start a draft, or return the current view when that research is already running.

        The per-research lock covers the probe and the write. It is not process-wide:
        a list fetch must stay responsive while this research waits on market data.
        SQLite itself is serialized separately, and only around connection calls.
        """
        with self._lock_for_research(research_id):
            research = self.store.load(research_id)
            if research.status is ResearchStatus.RUNNING:
                view = self.view_for(f"#/research/{research_id}")
                view["research_id"] = research.research_id
                view["status"] = research.status.value
                return view
            from engine.research.run_gate import evaluate_run_gate
            from engine.research.source_acknowledgement import (
                acknowledged_at,
                is_unlicensed_source,
                record_acknowledgement,
            )
            from engine.research.universe_pool import pool_resolvable

            requested = data_source_id.strip() if isinstance(data_source_id, str) else ""
            source = requested or research.data_source_id
            # A draft that still has no symbols keeps the existing pool question.
            # The source gate applies once there is something to price.
            # Preselection is the same rule as the confirm card: one licensed
            # configured source, never Yahoo or AkShare, never the last pick.
            if pool_resolvable(research) and not source:
                from engine.research.price_source_choice import (
                    available_price_sources,
                    preselect_price_source,
                )

                universe = research.brief.universe.value
                if universe is not None:
                    source = preselect_price_source(
                        available_price_sources(universe.market, self.paths.data.settings_file)
                    ) or ""
            gate = evaluate_run_gate(
                research,
                data_source_id=source,
                unlicensed_acknowledged=unlicensed_acknowledged,
                settings_path=self.paths.data.settings_file,
            )
            if not gate.runnable:
                raise UserFacingError(
                    gate.code or "DATA_SOURCE_UNBOUND",
                    gate.message or "",
                    params=gate.params or None,
                )
            if source and is_unlicensed_source(source):
                settings = self.paths.data.settings_file
                if acknowledged_at(source, settings) is None:
                    record_acknowledgement(source, now, settings)
            if source != research.data_source_id:
                research = replace(research, data_source_id=source)
            expected_at = research.updated_at
            try:
                research = ensure_runnable_universe(research)
            except UserFacingError as error:
                if error.code in MARKET_DATA_FAILURE_CODES:
                    updated = record_transient_confirm_notice(research, error, now)
                    self._save(research, updated)
                    raise
                if error.code in {
                    "UNIVERSE_SYMBOLS_EMPTY",
                    "UNIVERSE_MISSING",
                    "UNIVERSE_DEFAULT_TOO_SMALL",
                    "POOL_DATA_SHRINK_TOO_FEW",
                }:
                    reopened = reopen_after_pool_failure(research, error, now)
                    self._save(research, reopened)
                raise
            self.store.save(research, expected_at)
            research = self.store.load(research.research_id)
            research = replace(research, construction_schedule=SCHEDULE_COST_MODEL)
            updated = transition(research, ResearchEvent.CONFIRM_RUN, now)
            self._record_version_methods(updated)
            return self._save(research, updated)

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        locale = normalize_request_locale(request.get("locale"))
        self.last_request_locale = locale
        token = push_request_locale(locale)
        try:
            return self._dispatch(request)
        finally:
            reset_request_locale(token)

    def _dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        kind = request["type"]
        now = datetime.now(UTC)
        if kind == "fetch_view":
            return self.view_for(request["route"])
        if kind == "market_data_progress":
            return self._market_data_status()
        if kind == "create_draft":
            research_id = str(uuid.uuid4())
            self.store.create(new_research(research_id, now))
            return {"research_id": research_id}
        if kind == "install_secrets":
            from engine.research.secret_memory import install_secrets

            secrets = request.get("secrets") or {}
            if not isinstance(secrets, dict):
                raise ValueError("secrets must be an object")
            installed = install_secrets({str(key): str(value) for key, value in secrets.items()})
            return {"ok": True, "ids": list(installed)}
        if kind == "secret_failure_preview":
            from engine.research.secret_memory import DESKTOP_REQUIRED_MESSAGE, peek_secret
            from engine.research.secret_redaction import redact_text

            secret_id = str(request["secret_id"])
            value = peek_secret(secret_id)
            if not value:
                return {"message": DESKTOP_REQUIRED_MESSAGE}
            raw = (
                "error sending request for url "
                f"https://user:{value}@example.invalid/v1/{value}?api_key={value}"
            )
            return {"message": redact_text(raw)}
        if kind == "create_method":
            source = MethodSource(request.get("source", MethodSource.DEPOSITED.value))
            definition = create_method(
                self.store,
                request["method_id"],
                request["name"],
                request["description"],
                request["body"],
                source,
                now,
                deposited_from_research_id=request.get("deposited_from_research_id"),
            )
            return {
                "method_id": definition.method_id,
                "revision_hash": definition.revision_hash,
            }
        if kind == "list_methods":
            return {
                "methods": [
                    {
                        "method_id": item.method_id,
                        "revision_hash": item.revision_hash,
                        "name": item.name,
                        "description": item.description,
                        "body": item.body,
                        "source": item.source.value,
                        "deposited_from_research_id": item.deposited_from_research_id,
                        "supersedes": item.supersedes,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in self.store.list_method_definitions()
                ]
            }
        if kind == "revise_method":
            latest = self.store.latest_method_definition(request["method_id"])
            if latest is None:
                revision = self.store.revise_method(
                    request["method_id"],
                    request["definition"],
                    now,
                    name=request["method_id"],
                    body=request["definition"],
                )
                return {"revision_hash": revision}
            updated_method = revise_method(
                self.store,
                request["method_id"],
                latest.name,
                latest.description,
                request["definition"],
                now,
            )
            return {"revision_hash": updated_method.revision_hash}
        if kind == "confirm_run":
            raw_source = request.get("data_source_id")
            return self._confirm_run(
                str(request["research_id"]),
                now,
                data_source_id=raw_source if isinstance(raw_source, str) else None,
                unlicensed_acknowledged=bool(request.get("unlicensed_acknowledged")),
            )
        if kind == "set_research_symbol":
            research = self.store.load(str(request["research_id"]))
            updated = apply_symbol_edit(research, str(request["symbol"]), now)
            return self._save(research, updated)
        if kind == "set_price_source":
            from engine.research.price_source_choice import remember_price_source

            research_id = str(request["research_id"])
            # Same lock as confirm_run. An acknowledgement that lands while the
            # run is probing must not bump updated_at under that snapshot.
            with self._lock_for_research(research_id):
                research = self.store.load(research_id)
                updated = remember_price_source(
                    research,
                    str(request.get("data_source_id") or ""),
                    unlicensed_acknowledged=bool(request.get("unlicensed_acknowledged")),
                    now=now,
                    settings_path=self.paths.data.settings_file,
                )
                if updated is research:
                    return {
                        "research_id": research.research_id,
                        "status": research.status.value,
                    }
                return self._save(research, updated)
        if kind == "answer_symbol_ask":
            research = self.store.load(str(request["research_id"]))
            updated = answer_symbol_ask(
                research,
                str(request["token"]),
                bool(request["accept"]),
                now,
            )
            return self._save(research, updated)
        if kind == "use_hinted_symbol":
            research = self.store.load(str(request["research_id"]))
            updated = use_hinted_symbol(research, str(request["symbol"]), now)
            return self._save(research, updated)
        if kind == "revert_symbol_ask":
            research = self.store.load(str(request["research_id"]))
            updated = revert_symbol_ask(research, str(request["token"]), now)
            return self._save(research, updated)
        if kind == "remove_market_side":
            research = self.store.load(str(request["research_id"]))
            updated = remove_market_side(research, str(request["side"]), now)
            return self._save(research, updated)
        if kind == "dismiss_mismatched_symbol":
            research = self.store.load(str(request["research_id"]))
            updated = dismiss_mismatched_symbol(research, str(request["symbol"]), now)
            return self._save(research, updated)
        if kind == "choose_default_market":
            research = self.store.load(str(request["research_id"]))
            updated = choose_default_market(research, str(request["market"]), now)
            return self._save(research, updated)

        research = self.store.load(request["research_id"])
        if kind == "delete_research":
            self.store.delete(research.research_id)
            return {"research_id": research.research_id, "deleted": True}
        if kind == "send_dialogue":
            updated = process_send_dialogue(research, request["message"], now)
        elif kind == "unlock_brief":
            from engine.dialogue.prompts import QUESTIONS, SlotName
            from engine.dialogue.turns import append_dialogue
            from engine.research.models import DialogueRole

            slot = request.get("slot")
            if slot:
                updated = unlock_slot(research, str(slot), now)
                updated = append_dialogue(
                    updated,
                    DialogueRole.ASSISTANT,
                    QUESTIONS[SlotName(str(slot))],
                    now,
                )
            else:
                updated = unlock_all_slots(research, now)
                open_slot = first_open_slot(updated.brief)
                if open_slot is not None:
                    updated = append_dialogue(
                        updated,
                        DialogueRole.ASSISTANT,
                        QUESTIONS[open_slot],
                        now,
                    )
        elif kind == "pause":
            updated = transition(research, ResearchEvent.PAUSE, now)
        elif kind == "resume":
            updated = transition(research, ResearchEvent.RESUME, now)
        elif kind == "confirm_modification":
            if research.status is ResearchStatus.RUNNING:
                raise UserFacingError(
                    "RUNNING_CANNOT_MODIFY",
                    "研究仍在运行中，请先暂停再确认修改。",
                )
            from engine.dialogue.modification import brief_differs_from_latest_version

            if not brief_differs_from_latest_version(research):
                raise UserFacingError(
                    "MODIFICATION_UNCHANGED",
                    "研究设定没有变化。请先用上方输入说明要改什么，再确认开新版。",
                )
            previous = ""
            if research.versions:
                previous = research.versions[-1].brief_snapshot.thesis.value or ""
            proposed = research.brief.thesis.value or ""
            updated = transition(research, ResearchEvent.MODIFY_CONFIRM, now)
            from engine.dialogue.modification import finalize_modification_confirm_dialogue

            updated = finalize_modification_confirm_dialogue(updated, now)
            updated = replace(
                updated,
                thesis_change_hint=thesis_divergence_hint(previous, proposed),
            )
            self._record_version_methods(updated)
        elif kind == "continue_iterate":
            validate_continue_iterate_confirm(
                research,
                user_confirmed=bool(request.get("user_confirmed")),
                high_suspicion_acknowledged=bool(
                    request.get("high_suspicion_acknowledged")
                ),
                store=self.store,
            )
            assert_can_manual_continue(research)
            increment = trial_budget_increment()
            boosted = replace(
                research,
                implementation_trial_budget=research.implementation_trial_budget + increment,
                updated_at=now,
            )
            self.store.save(boosted, research.updated_at)
            resumed = transition(boosted, ResearchEvent.CONTINUE_ITERATE, now)
            return self._save(boosted, resumed)
        elif kind == "extend_research":
            current_hours = research.brief.max_effective_hours.value or 0.0
            extended = replace(
                research,
                brief=replace(
                    research.brief,
                    max_effective_hours=Slot(
                        current_hours + float(request["hours"]),
                        True,
                    ),
                ),
                updated_at=now,
            )
            updated = transition(extended, ResearchEvent.EXTEND_CONFIRM, now)
            self._record_version_methods(updated)
        elif kind == "resolve_confirm":
            event = {
                "approve_new_version": ResearchEvent.CONFIRM_APPROVE,
                "reject_keep_logic": ResearchEvent.CONFIRM_REJECT,
                "pause_and_edit": ResearchEvent.CONFIRM_PAUSE,
                "accept_lower_floor": ResearchEvent.CONFIRM_APPROVE,
                "supply_local_materials": ResearchEvent.CONFIRM_PAUSE,
                "redefine_scope": ResearchEvent.CONFIRM_APPROVE,
            }[request["decision"]]
            if event is ResearchEvent.CONFIRM_APPROVE and research.pending_confirm is not None:
                pending = research.pending_confirm
                refs: list[EvidenceRef] = []
                for item in request.get("why_change") or ():
                    refs.append(
                        EvidenceRef(
                            record_id=item["record_id"],
                            recorded_at=datetime.fromisoformat(item["recorded_at"]),
                            kind=EvidenceKind(item["kind"]),
                            summary=item.get("summary"),
                        )
                    )
                if refs:
                    pending = replace(
                        pending,
                        why_change=tuple(refs),
                        created_at=pending.created_at or now,
                    )
                if (
                    request["decision"] == "approve_new_version"
                    and pending.kind is ConfirmKind.ECONOMIC
                ):
                    who_pays = request.get("who_pays")
                    text = (
                        who_pays if isinstance(who_pays, str) and who_pays.strip() else "未作答"
                    )
                    pending = replace(
                        pending,
                        patch=pending.patch + (("who_pays_optional", text),),
                    )
                research = replace(research, pending_confirm=pending)
            if event is ResearchEvent.CONFIRM_APPROVE:
                deposit_confirmed_methods(self.store, research, now)
            updated = transition(research, event, now, store=self.store)
            if event is ResearchEvent.CONFIRM_APPROVE:
                patch = dict(research.pending_confirm.patch) if research.pending_confirm else {}
                self._record_version_methods(
                    updated,
                    patch.get("round1_methods") or patch.get("method_set"),
                )
        elif kind == "reverify":
            matching = [
                round_
                for version in research.versions
                for round_ in version.rounds
                if round_.round_id == request["round_id"]
            ]
            if len(matching) != 1:
                raise ValueError("reverify requires one frozen round_id")
            accepted = matching[0].accepted_attempt
            if accepted.data_snapshot_path is None:
                raise ValueError("reverify requires the selected round's frozen data")
            frozen = pd.read_csv(
                accepted.data_snapshot_path,
                index_col="date",
                parse_dates=True,
            )

            class FrozenDataPort:
                def load_daily(
                    self,
                    symbols: tuple[str, ...],
                    start: date,
                    end: date,
                ) -> pd.DataFrame:
                    if symbols == (accepted.simulation.benchmark_id,):
                        return frozen[["__benchmark__"]].rename(
                            columns={"__benchmark__": accepted.simulation.benchmark_id}
                        )
                    return frozen[list(symbols)]

            rerun_simulation = simulate_daily(
                MeanReversionStrategy(accepted.spec),
                FrozenDataPort(),
                frozen.index.min().date(),
                frozen.index.max().date(),
            )
            pit_revision = recorded_pit_revision(accepted.verification)
            evidence_payloads = tuple(
                json.loads(path.read_text(encoding="utf-8"))
                for path in accepted.evidence_paths
            )
            evidence_as_of, missing_as_of, undated_excluded = pit_evidence_from_payloads(
                evidence_payloads,
                revision=pit_revision,
            )
            rerun = run_verifiers(
                rerun_simulation,
                accepted.spec,
                evidence_as_of=evidence_as_of,
                missing_as_of_material_ids=missing_as_of,
                undated_excluded=undated_excluded,
                evidence_annotations=pit_evidence_annotations(evidence_payloads),
                pit_revision=pit_revision,
            )
            matching_method = [
                result
                for result in rerun.results
                if result.verifier_id == request["method_id"]
            ]
            if len(matching_method) != 1:
                raise ValueError("method_id is not frozen on the selected round")
            record = Reverification(
                round_id=request["round_id"],
                method_id=request["method_id"],
                report=rerun,
                passed=matching_method[0].passed,
                created_at=now,
            )
            with_rerun = replace(
                research,
                reverifications=research.reverifications + (record,),
                updated_at=now,
            )
            if not record.passed:
                with_rerun = mark_exports_overturned(with_rerun)
            updated = transition(
                with_rerun,
                ResearchEvent.REVERIFY_PASS
                if record.passed
                else ResearchEvent.REVERIFY_FAIL,
                now,
            )
        elif kind == "export_artifact":
            export_root = self.paths.data.exports_dir
            export_root.mkdir(parents=True, exist_ok=True)
            eligibility = strategy_pack_eligibility(research)
            if request["kind"] == "research_record":
                destination = export_root / export_zip_filename(
                    research, "research_record", now=now
                )
                build_research_record_pack(research, destination)
                export_kind = ExportKind.RESEARCH_RECORD
                failed_checks = eligibility.failed_checks
            else:
                if not eligibility.eligible:
                    raise ValueError(
                        f"research is not strategy-pack eligible: {eligibility.failed_checks}"
                    )
                if not research.versions or not research.versions[-1].rounds:
                    raise ValueError("strategy pack requires a completed round")
                attempt = research.versions[-1].rounds[-1].accepted_attempt
                if attempt.data_snapshot_path is None:
                    raise ValueError("strategy pack requires a frozen data snapshot")
                snapshot = pd.read_csv(
                    attempt.data_snapshot_path,
                    index_col="date",
                    parse_dates=True,
                )
                prices = snapshot.drop(columns=["__benchmark__"], errors="ignore")
                benchmark = (
                    snapshot["__benchmark__"]
                    if "__benchmark__" in snapshot.columns
                    else None
                )
                destination = export_root / export_zip_filename(
                    research, "strategy_pack", now=now
                )
                build_strategy_pack(
                    research,
                    MeanReversionStrategy(attempt.spec),
                    MarketPanel(prices, now, benchmark),
                    destination,
                )
                export_kind = ExportKind.STRATEGY_PACK
                failed_checks = ()
            updated = replace(
                research,
                exports=research.exports
                + (
                    ExportRecord(
                        str(uuid.uuid4()),
                        export_kind,
                        str(destination),
                        research.current_version_number,
                        now,
                        failed_checks,
                        False,
                    ),
                ),
                updated_at=now,
            )
            payload = self._save(research, updated)
            payload["path"] = str(destination)
            return payload
        else:
            raise ValueError(f"unknown desktop request type: {kind}")
        return self._save(research, updated)


class EngineApiHandler(BaseHTTPRequestHandler):
    service: ResearchCommandService
    auth_token: str
    request_schema: dict[str, Any]

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        if self.path != "/commands":
            self._send(404, {"error": "not_found"})
            return
        if self.headers.get("Authorization") != f"Bearer {self.auth_token}":
            self._send(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            if isinstance(request, dict) and request.get("type") == "install_secrets":
                from engine.research.secret_redaction import register_secret

                secrets = request.get("secrets")
                if isinstance(secrets, dict):
                    for value in secrets.values():
                        if isinstance(value, str):
                            register_secret(value)
            jsonschema.validate(request, self.request_schema)
            self._send(200, self.service.handle(request))
        except UserFacingError as error:
            self._send(400, http_error_payload(error))
        except (
            ValueError,
            KeyError,
            json.JSONDecodeError,
            jsonschema.ValidationError,
        ) as error:
            self._send(400, http_error_payload(error))
        except InvalidTransition as error:
            self._send(400, http_error_payload(error))
        except Exception as error:  # noqa: BLE001
            logging.exception("engine command failed: %s", type(error).__name__)
            self._send(
                500,
                build_error_envelope(
                    code="internal_error",
                    message="服务器内部错误，请稍后重试。",
                ),
            )

    def log_message(self, format: str, *args: object) -> None:
        return


def start_api(
    service: ResearchCommandService,
    token: str,
) -> tuple[ThreadingHTTPServer, str]:
    bundle_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    )
    schema = json.loads(
        (bundle_root / "contracts" / "desktop-api.schema.json").read_text(
            encoding="utf-8"
        )
    )
    handler = type(
        "BoundEngineApiHandler",
        (EngineApiHandler,),
        {"service": service, "auth_token": token, "request_schema": schema},
    )
    # ThreadingHTTPServer: confirm_run / fetch_view market probes must not wedge all /commands.
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    endpoint = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name="engine-loopback-api",
    ).start()
    return server, endpoint


def advance_running_research(
    store: SQLiteStore,
    loop: ResearchLoop,
    research_id: str,
) -> None:
    """Run one tick for a running id. A deleted id is cancellation, not a crash."""
    from engine.research.removal import ResearchRemoved

    try:
        loop.run_once(research_id)
    except ResearchRemoved:
        return
    except Exception as error:  # noqa: BLE001
        try:
            before = store.load(research_id)
        except KeyError:
            return
        now = datetime.now(UTC)
        code, message = classify_run_error(error)
        detail = error.detail if isinstance(error, UserFacingError) else None
        if detail is None:
            technical = str(error)
            if technical and technical != message:
                detail = technical
        params = error.params if isinstance(error, UserFacingError) else None
        after = apply_run_failure(
            before,
            message,
            now,
            code=code,
            params=params,
            detail=detail,
        )
        try:
            store.save(after, before.updated_at)
        except ConcurrentWrite:
            try:
                store.load(research_id)
            except KeyError:
                return
            raise
        store.record_error(
            research_id,
            message,
            now,
            force=after.status.value == "paused"
            and after.consecutive_identical_run_errors >= max_consecutive_run_errors(),
        )


def configure_engine_file_log(path: Path) -> logging.Handler:
    """Append engine logs to the contracted ``engine.log``. Returns the handler."""
    from engine.research.build_info import read_build_info

    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    version, sha = read_build_info()
    logging.getLogger("alphaloop.engine").info("alphaloop %s %s", version, sha)
    return handler


def serve(owner_kind: OwnerKind, paths: EnginePaths) -> int:
    configure_engine_file_log(paths.data.engine_log)
    from engine.research.offline_market_data import offline_market_data_enabled

    if offline_market_data_enabled():
        logging.getLogger("alphaloop.engine").warning(
            "ALPHALOOP_OFFLINE_MARKET_DATA=1: synthetic market data is on; not for a release"
        )
    try:
        lock = EngineLock.acquire(paths.runtime, owner_kind)
    except RuntimeError:
        deadline = time.monotonic() + 10.0
        owner = read_live_owner(paths.runtime)
        while (
            owner is not None
            and (
                owner.phase != "ready"
                or owner.endpoint is None
                or owner.auth_token is None
            )
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)
            owner = read_live_owner(paths.runtime)
        if owner is None:
            return 1
        if owner.phase != "ready" or owner.endpoint is None or owner.auth_token is None:
            return 1
        _handshake("already_running", owner)
        return 0

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    from engine.research.secret_memory import configure_process_owner
    from engine.research.secret_redaction import install_redacting_log_filter

    configure_process_owner(owner_kind)
    install_redacting_log_filter()
    store = SQLiteStore(paths.data.database_file)
    seed_preset_methods(store)
    budget = TimeBudget(time.monotonic)
    loop = build_loop(store, paths, budget)
    service = ResearchCommandService(SQLiteStore(paths.data.database_file), paths, budget)
    token = secrets.token_urlsafe(32)
    server, endpoint = start_api(service, token)
    owner = publish_ready(lock, endpoint, token)
    _handshake("ready", owner)
    if owner_kind == "desktop":
        threading.Thread(
            target=_watch_desktop_stdin,
            args=(stop,),
            daemon=True,
            name="desktop-parent-eof",
        ).start()
    try:
        while not stop.wait(1.0):
            for research_id in store.running_ids():
                advance_running_research(store, loop, research_id)
            store.heartbeat(owner, datetime.now(UTC))
    finally:
        server.shutdown()
        server.server_close()
        lock.close()
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return serve(args.owner, EnginePaths.default())


if __name__ == "__main__":
    raise SystemExit(main())
