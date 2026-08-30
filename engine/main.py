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
from engine.export import build_strategy_pack
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
from engine.research.models import (
    Research,
    ResearchEvent,
    Reverification,
    Round,
    Slot,
    new_research,
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
from engine.research.store import CONVERTER, SQLiteStore
from engine.review.subagent import LLMPort, OpenAICompatibleLLM, SubagentReviewer
from engine.strategy import MarketPanel, MeanReversionStrategy
from engine.verifiers import run_verifiers

PROTOCOL_VERSION = 1


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

    def _save(self, before: Research, after: Research) -> None:
        self.store.save(after, before.updated_at)

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

    def view_for(self, route: str) -> dict[str, Any]:
        if route.startswith("#/methods"):
            methods = [
                {
                    "id": method_id,
                    "name": method_id,
                    "revision": revision,
                    "description": definition,
                }
                for method_id, revision, definition in self.store.list_methods()
            ]
            selected = route.removeprefix("#/methods/") if route.startswith("#/methods/") else None
            return {"kind": "methods", "selected": selected, "methods": methods}
        if route == "#/research":
            summaries = [
                {
                    "id": research.research_id,
                    "title": str(research.brief.thesis.value or "新研究"),
                    "status": research.status.value,
                }
                for research in self.store.list_research()
            ]
            awaiting = next(
                (item for item in summaries if item["status"] == "awaiting_confirm"),
                None,
            )
            rows = [item for item in summaries if item is not awaiting]
            return {"kind": "research_list", "awaiting": awaiting, "rows": rows}
        research_id = route.removeprefix("#/research/")
        research = self.store.load(research_id)
        if research.status.value == "draft":
            kind = "confirm_run" if all_slots_locked(research.brief) else "draft"
            return {
                "kind": kind,
                "researchId": research_id,
                "messages": [],
                "settings": self._settings(research),
            }
        if research.status.value in {"running", "paused"}:
            version = research.current_version_number or 1
            rounds = research.versions[version - 1].rounds if research.versions else ()
            return {
                "kind": "running",
                "researchId": research_id,
                "status": research.status.value,
                "version": version,
                "effective": f"{research.effective_seconds / 3600:.2f}h",
                "coverage": str(research.brief.coverage_floor.value or ""),
                "rounds": [round_.accepted_attempt.spec.id for round_ in reversed(rounds)],
            }
        if research.status.value == "awaiting_confirm":
            request = research.pending_confirm
            if request is None:
                raise ValueError("awaiting_confirm research requires ConfirmRequest")
            return {
                "kind": "awaiting_confirm",
                "researchId": research_id,
                "version": research.current_version_number or 1,
                "proposed": request.proposed_change,
                "reason": request.reason,
                "effect": request.effect,
            }
        rounds = research.versions[-1].rounds if research.versions else ()
        selected_round: Round | None = rounds[-1] if rounds else None
        return {
            "kind": "completed",
            "researchId": research_id,
            "status": research.status.value,
            "title": str(research.brief.thesis.value or "研究结果"),
            "selectedRoundId": selected_round.round_id if selected_round else "",
            "selectedMethodId": "overfit.walk",
            "eligibility": {
                "allMethodsPassed": (
                    selected_round is not None
                    and selected_round.accepted_attempt.verification.passed
                ),
                "noPendingConfirm": research.pending_confirm is None,
                "reverifiesPassed": all(
                    item.passed
                    for item in research.reverifications
                    if selected_round is not None and item.round_id == selected_round.round_id
                ),
            },
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        kind = request["type"]
        now = datetime.now(UTC)
        if kind == "fetch_view":
            return self.view_for(request["route"])
        if kind == "create_draft":
            research_id = str(uuid.uuid4())
            self.store.create(new_research(research_id, now))
            return {"research_id": research_id}
        if kind == "revise_method":
            revision = self.store.revise_method(
                request["method_id"],
                request["definition"],
                now,
            )
            return {"revision_hash": revision}

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
        elif kind == "pause":
            updated = transition(research, ResearchEvent.PAUSE, now)
        elif kind == "resume":
            updated = transition(research, ResearchEvent.RESUME, now)
        elif kind == "confirm_modification":
            updated = transition(research, ResearchEvent.MODIFY_CONFIRM, now)
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
        elif kind == "resolve_confirm":
            event = {
                "approve_new_version": ResearchEvent.CONFIRM_APPROVE,
                "reject_keep_logic": ResearchEvent.CONFIRM_REJECT,
                "pause_and_edit": ResearchEvent.CONFIRM_PAUSE,
            }[request["decision"]]
            updated = transition(research, event, now)
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
            if request["kind"] == "research_record":
                destination = export_root / f"{research.research_id}-research-record.json"
                destination.write_text(
                    json.dumps(
                        CONVERTER.unstructure(research),
                        sort_keys=True,
                        default=str,
                    ),
                    encoding="utf-8",
                )
                return {"path": str(destination)}
            if not research.versions or not research.versions[-1].rounds:
                raise ValueError("strategy pack requires a completed round")
            attempt = research.versions[-1].rounds[-1].accepted_attempt
            if attempt.data_snapshot_path is None:
                raise ValueError("strategy pack requires a frozen data snapshot")
            prices = pd.read_csv(
                attempt.data_snapshot_path,
                index_col="date",
                parse_dates=True,
            )
            destination = export_root / f"{research.research_id}-strategy-pack.zip"
            build_strategy_pack(
                research,
                MeanReversionStrategy(attempt.spec),
                MarketPanel(prices, now),
                destination,
            )
            return {"path": str(destination)}
        else:
            raise ValueError(f"unknown desktop request type: {kind}")
        self._save(research, updated)
        return {"research_id": research.research_id, "status": updated.status.value}


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
