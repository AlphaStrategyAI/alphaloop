from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import sys
import threading
import time
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx
import jsonschema
import pandas as pd

from engine.dialogue.intent import interpret
from engine.dialogue.slots import apply_intent
from engine.export import (
    build_research_record_pack,
    build_strategy_pack,
    mark_exports_overturned,
    strategy_pack_eligibility,
)
from engine.research.clock import TimeBudget
from engine.research.gather import (
    AkShareDataAdapter,
    LocalMaterialAdapter,
    PapersAdapter,
    RoutingDataAdapter,
    SecEdgarAdapter,
    YahooDataAdapter,
)
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.methods import (
    as_method_refs,
    create_method,
    deposit_confirmed_methods,
    list_method_usage,
    record_method_usage,
    revise_method,
    seed_preset_methods,
)
from engine.research.models import (
    AnomalyBaseline,
    AnomalyPresentation,
    ExportKind,
    ExportRecord,
    MethodSource,
    Research,
    ResearchAction,
    ResearchEvent,
    ResearchStatus,
    Reverification,
    Round,
    Slot,
    detect_anomalies,
    new_research,
)
from engine.research.progress import (
    ResearchListItem,
    host_status,
    list_items,
    notification_event,
    thesis_divergence_hint,
)
from engine.research.runtime import (
    EngineLock,
    OwnerKind,
    OwnerRecord,
    RuntimePaths,
    publish_ready,
    read_live_owner,
)
from engine.research.simulate import simulate_daily
from engine.research.state_machine import all_slots_locked, transition
from engine.research.store import SQLiteStore
from engine.review.subagent import LLMPort, OpenAICompatibleLLM, SubagentReviewer
from engine.strategy import MarketPanel, MeanReversionStrategy
from engine.verifiers import run_verifiers

PROTOCOL_VERSION = 1

_ACTION_LABELS = {
    ResearchAction.GATHER: "查资料",
    ResearchAction.SPECIFY: "补细节",
    ResearchAction.SIMULATE: "历史模拟",
    ResearchAction.VERIFY: "验证",
    ResearchAction.ITERATE: "迭代",
    ResearchAction.IDLE: "idle",
}


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


def build_loop(store: SQLiteStore, paths: RuntimePaths) -> ResearchLoop:
    client = httpx.Client()
    material_root = paths.root / "materials"
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
    data_port = RoutingDataAdapter(YahooDataAdapter(), AkShareDataAdapter())
    base_url = os.environ.get("ALPHALOOP_LLM_BASE_URL")
    api_key = os.environ.get("ALPHALOOP_LLM_API_KEY")
    model = os.environ.get("ALPHALOOP_LLM_MODEL")
    llm: LLMPort = (
        OpenAICompatibleLLM(client, base_url, api_key, model)
        if base_url and api_key and model
        else FailClosedLLM()
    )
    today = datetime.now(UTC).date()
    builder = DefaultRoundBuilder(
        material_ports=material_ports,
        data_port=data_port,
        start=today - timedelta(days=365 * 12),
        end=today,
        snapshot_root=paths.root / "snapshots",
    )
    return ResearchLoop(
        store,
        builder,
        SubagentReviewer(llm),
        TimeBudget(time.monotonic),
        lambda: datetime.now(UTC),
    )


class ResearchCommandService:
    def __init__(self, store: SQLiteStore, paths: RuntimePaths) -> None:
        self.store = store
        self.paths = paths
        self._observed_status: dict[str, ResearchStatus] = {}
        seed_preset_methods(store)

    def _save(self, before: Research, after: Research) -> dict[str, Any]:
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
    def _settings(research: Research) -> dict[str, str]:
        brief = research.brief
        return {
            "thesis": str(brief.thesis.value or ""),
            "universe": str(brief.universe.value or ""),
            "max_effective_hours": str(brief.max_effective_hours.value or ""),
            "round1_methods": " · ".join(
                method.method_id for method in (brief.round1_methods.value or ())
            ),
            "coverage_floor": str(brief.coverage_floor.value or ""),
        }

    def _host_payload(
        self,
        payload: dict[str, Any],
        research: Research | None = None,
    ) -> dict[str, Any]:
        payload["hostStatus"] = host_status(self.store.list_research())
        if research is not None and research.thesis_change_hint:
            payload["thesisChangeHint"] = research.thesis_change_hint
        return self._attach_notify(payload)

    @staticmethod
    def _list_summary(item: ResearchListItem) -> dict[str, str]:
        return {
            "id": item.research_id,
            "title": item.title,
            "status": item.status.value,
            "universeLabel": item.universe_label,
            "createdAt": item.created_at.isoformat(),
            "updatedAt": item.updated_at.isoformat(),
        }

    @staticmethod
    def _coverage_vs_floor(research: Research) -> str:
        floor = research.brief.coverage_floor.value
        observed = research.last_coverage
        if observed is None:
            return str(floor or "")
        current = (
            f"{len(observed.assets)}资产/{observed.years:.1f}年/缺失{observed.missing_pct:.1f}%"
        )
        if floor is None:
            return current
        return (
            f"{current} vs 底线 {floor.min_assets}资产/{floor.min_years}年/"
            f"缺失≤{floor.max_missing_pct:.1f}%"
        )

    @staticmethod
    def _remaining(research: Research) -> str:
        max_hours = research.brief.max_effective_hours.value
        used = research.effective_seconds / 3600
        if max_hours is None:
            return ""
        return f"{max(0.0, max_hours - used):.2f}h"

    @staticmethod
    def _sources(research: Research) -> str:
        if research.versions and research.versions[-1].rounds:
            evidence = research.versions[-1].rounds[-1].accepted_attempt.evidence_paths
            if evidence:
                return "公开资料已落成本机材料"
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
        baseline = AnomalyBaseline(
            kind="version_1_logic",
            sharpe=0.5,
            trial_count=5,
        )
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
                    "name": "夏普比率",
                    "description": "样本外夏普比率下限",
                    "passThreshold": parsed["sharpe_oos_min_exclusive"],
                    "comparison": "gt",
                    "failureDisplay": "夏普不高于基准",
                })
            if "default_max_drawdown_floor" in parsed:
                dimensions.append({
                    "kind": "stability",
                    "name": "最大回撤",
                    "description": "回撤上限",
                    "passThreshold": parsed["default_max_drawdown_floor"],
                    "comparison": "gte",
                    "failureDisplay": "回撤过大",
                })
        elif method_id == "overfit.walk":
            if "oos_to_is_min" in parsed:
                dimensions.append({
                    "kind": "stability",
                    "name": "样本外/样本内比",
                    "description": "样本外表现与样本内的比值下限",
                    "passThreshold": parsed["oos_to_is_min"],
                    "comparison": "gte",
                    "failureDisplay": "样本外走样",
                })
        elif method_id == "pit.consistency":
            dimensions.append({
                "kind": "pit_consistency",
                "name": "时点一致性",
                "description": "检查是否存在前视偏差",
                "passThreshold": 1.0,
                "comparison": "eq",
                "failureDisplay": "存在前视偏差",
            })
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
            return "拥挤度"
        if method_id.startswith("cost."):
            return "成本"
        return None

    def view_for(self, route: str) -> dict[str, Any]:
        if route.startswith("#/methods"):
            methods = [
                {
                    "id": item.method_id,
                    "name": item.name or item.method_id,
                    "revision": item.revision_hash,
                    "description": item.description,
                    "source": item.source.value,
                    "depositedFromResearchId": item.deposited_from_research_id,
                    "supersedes": item.supersedes,
                    "usageCount": len({
                        row.research_id
                        for row in list_method_usage(self.store, item.method_id)
                    }),
                    "category": self._method_category(item.method_id),
                    "dimensions": self._method_dimensions(item.method_id, item.body),
                }
                for item in self.store.list_method_definitions()
            ]
            selected = route.removeprefix("#/methods/") if route.startswith("#/methods/") else None
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
            kind = "confirm_run" if all_slots_locked(research.brief) else "draft"
            return self._host_payload(
                {
                    "kind": kind,
                    "researchId": research_id,
                    "messages": [],
                    "settings": self._settings(research),
                },
                research,
            )
        if research.status.value in {"running", "paused"}:
            version = research.current_version_number or 1
            rounds = research.versions[version - 1].rounds if research.versions else ()
            return self._host_payload(
                {
                    "kind": "running",
                    "researchId": research_id,
                    "status": research.status.value,
                    "version": version,
                    "effective": f"{research.effective_seconds / 3600:.2f}h",
                    "remaining": self._remaining(research),
                    "coverage": self._coverage_vs_floor(research),
                    "rounds": [
                        {
                            "roundId": round_.round_id,
                            "number": round_.number,
                            "logicStatement": {
                                "statement": round_.accepted_attempt.spec.id,
                                "changedFromPrior": idx > 0,
                                "changeDescription": None,
                                "baselineVersion": version,
                            },
                            "implementationDelta": {
                                "researchMethodChanges": [],
                                "modelChanges": [],
                                "paramChanges": [],
                            },
                            "trialCounters": {
                                "candidatesEvaluated": round_.accepted_attempt.number,
                                "candidatesPassed": 1 if round_.accepted_attempt.verification.passed else 0,
                                "conclusionAttemptNumber": round_.accepted_attempt.number,
                            },
                            "verificationPassed": round_.accepted_attempt.verification.passed,
                            "pitPassed": None,
                        }
                        for idx, round_ in enumerate(reversed(rounds))
                    ],
                    "currentAction": _ACTION_LABELS[research.current_action],
                    "sources": self._sources(research),
                    "dataCutoff": (
                        research.last_coverage.end.isoformat()
                        if research.last_coverage is not None
                        else ""
                    ),
                    "anomaly": self._compute_anomaly(research),
                },
                research,
            )
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
        selected_round: Round | None = rounds[-1] if rounds else None
        eligibility = strategy_pack_eligibility(research)
        return self._host_payload(
            {
                "kind": "completed",
                "researchId": research_id,
                "status": research.status.value,
                "title": str(research.brief.thesis.value or "研究结果"),
                "selectedRoundId": selected_round.round_id if selected_round else "",
                "selectedMethodId": "overfit.walk",
                "eligibility": {
                    "allMethodsPassed": "all_current_methods_passed" not in eligibility.failed_checks,
                    "noPendingConfirm": "no_pending_confirm" not in eligibility.failed_checks,
                    "reverifiesPassed": "all_reverifies_passed" not in eligibility.failed_checks,
                    "pitExecutedAndPassed": "pit_executed_and_passed" not in eligibility.failed_checks,
                },
                "overturnedExports": any(item.overturned for item in research.exports),
                "currentAction": _ACTION_LABELS[research.current_action],
                "anomaly": self._compute_anomaly(research),
            },
            research,
        )

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        kind = request["type"]
        now = datetime.now(UTC)
        if kind == "fetch_view":
            return self.view_for(request["route"])
        if kind == "create_draft":
            research_id = str(uuid.uuid4())
            self.store.create(new_research(research_id, now))
            return {"research_id": research_id}
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

        research = self.store.load(request["research_id"])
        if kind == "delete_research":
            self.store.delete(research.research_id)
            return {"research_id": research.research_id, "deleted": True}
        if kind == "send_dialogue":
            updated = apply_intent(
                research,
                interpret(request["message"], research),
                now,
            )
        elif kind == "confirm_run":
            updated = transition(research, ResearchEvent.CONFIRM_RUN, now)
            self._record_version_methods(updated)
        elif kind == "pause":
            updated = transition(research, ResearchEvent.PAUSE, now)
        elif kind == "resume":
            updated = transition(research, ResearchEvent.RESUME, now)
        elif kind == "confirm_modification":
            previous = ""
            if research.versions:
                previous = research.versions[-1].brief_snapshot.thesis.value or ""
            proposed = research.brief.thesis.value or ""
            updated = transition(research, ResearchEvent.MODIFY_CONFIRM, now)
            updated = replace(
                updated,
                thesis_change_hint=thesis_divergence_hint(previous, proposed),
            )
            self._record_version_methods(updated)
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
            rerun = run_verifiers(rerun_simulation, accepted.spec)
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
            export_root = self.paths.root / "exports"
            export_root.mkdir(parents=True, exist_ok=True)
            eligibility = strategy_pack_eligibility(research)
            if request["kind"] == "research_record":
                destination = export_root / f"{research.research_id}-research-record.zip"
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
                destination = export_root / f"{research.research_id}-strategy-pack.zip"
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
            jsonschema.validate(request, self.request_schema)
            self._send(200, self.service.handle(request))
        except (
            ValueError,
            KeyError,
            json.JSONDecodeError,
            jsonschema.ValidationError,
        ) as error:
            self._send(400, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        return


def start_api(
    service: ResearchCommandService,
    token: str,
) -> tuple[HTTPServer, str]:
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
    server = HTTPServer(("127.0.0.1", 0), handler)
    endpoint = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name="engine-loopback-api",
    ).start()
    return server, endpoint


def serve(owner_kind: OwnerKind, paths: RuntimePaths) -> int:
    try:
        lock = EngineLock.acquire(paths, owner_kind)
    except RuntimeError:
        deadline = time.monotonic() + 10.0
        owner = read_live_owner(paths)
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
            owner = read_live_owner(paths)
        if owner is None:
            return 1
        if owner.phase != "ready" or owner.endpoint is None or owner.auth_token is None:
            return 1
        _handshake("already_running", owner)
        return 0

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    store = SQLiteStore(paths.database_file)
    seed_preset_methods(store)
    loop = build_loop(store, paths)
    service = ResearchCommandService(SQLiteStore(paths.database_file), paths)
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
                try:
                    loop.run_once(research_id)
                except Exception as error:  # noqa: BLE001
                    store.record_error(research_id, str(error), datetime.now(UTC))
            store.heartbeat(owner, datetime.now(UTC))
    finally:
        server.shutdown()
        server.server_close()
        lock.close()
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return serve(args.owner, RuntimePaths.default())


if __name__ == "__main__":
    raise SystemExit(main())
