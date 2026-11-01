"""Draft sentences become checkable proposals. ZH and EN share one schema."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Self

import httpx
import pytest

from engine.dialogue.proposal import (
    DRAFT_INPUT_CHAR_LIMIT,
    DRAFT_TIMEOUT_SECONDS,
    build_draft_messages,
    project_material_query,
    validate_model_object,
)
from engine.dialogue.proposal_model import Proposal
from engine.main import ResearchCommandService
from engine.research.llm_config import (
    LLM_PURPOSE_VERSION,
    LlmCallError,
    LlmEndpoint,
    post_llm_draft,
    resolve_llm,
    resolve_llm_for_purpose,
    write_llm_settings,
)
from engine.research.models import ResearchStatus, Slot
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore
from engine.research.user_errors import UserFacingError
from tests.test_draft_confirm_run_e2e import DIALOGUE_SEQUENCE

pytestmark = pytest.mark.filterwarnings("ignore:.*:DeprecationWarning")


def _service(tmp_path: Path) -> ResearchCommandService:
    return ResearchCommandService(
        SQLiteStore(tmp_path / "proposals.db"),
        EnginePaths.for_colocated_root(tmp_path),
    )


def _create(service: ResearchCommandService, research_id: str = "r-proposal") -> str:
    service.handle(
        {"type": "create_draft", "research_id": research_id, "command_id": f"create-{research_id}"}
    )
    return research_id


def _say(service: ResearchCommandService, research_id: str, message: str, command_id: str) -> dict:
    revision = service.store.revision_of(research_id)
    return service.handle(
        {
            "type": "send_dialogue",
            "research_id": research_id,
            "message": message,
            "command_id": command_id,
            "expected_revision": revision,
        }
    )


def _events(service: ResearchCommandService, research_id: str) -> list[tuple[int, str, dict]]:
    rows = service.store.connection.execute(
        "SELECT seq, kind, refs_json FROM research_event WHERE research_id=? ORDER BY seq",
        (research_id,),
    ).fetchall()
    return [(int(seq), str(kind), json.loads(refs)) for seq, kind, refs in rows]


def _fill(service: ResearchCommandService, research_id: str, messages: tuple[str, ...]) -> None:
    for index, message in enumerate(messages):
        _say(service, research_id, message, f"d-{research_id}-{index}")


def test_chinese_revision_keeps_the_other_fields_and_one_event(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service)
    _fill(service, research_id, ("美股股票的均值回归", "6小时"))
    before = len(_events(service, research_id))
    base = service.store.revision_of(research_id)
    _say(service, research_id, "把刚才的六小时改为两小时，其他照旧", "d-revise")
    loaded = service.store.load(research_id)
    proposal = loaded.active_proposal
    assert proposal is not None
    assert proposal.base_revision == base
    assert proposal.kind == "interpret_brief"
    assert loaded.brief.max_effective_hours.value == pytest.approx(2)
    assert loaded.brief.thesis.value == "美股股票的均值回归"
    assert loaded.brief.universe.value is not None
    assert loaded.brief.universe.value.market.value == "US"
    changes = [item for item in proposal.changes if item.field == "max_effective_hours"]
    assert len(changes) == 1
    assert changes[0].source == "user_specified"
    assert changes[0].hours == pytest.approx(2)
    assert all(item.field == "max_effective_hours" for item in proposal.changes)
    assert proposal.executable_rule_source == "system_suggested"
    assert "user_agreed" not in json.dumps(SQLiteStore._encode(loaded))
    added = _events(service, research_id)[before:]
    assert len(added) == 1
    assert added[0][1] == "send_dialogue"
    assert added[0][2]["proposal_id"] == proposal.proposal_id
    assert added[0][2]["llm_calls"] == 0
    assert added[0][2]["changes"] == [
        {"field": "max_effective_hours", "source": "user_specified", "text": "2.0"}
    ]


def test_english_revision_and_named_symbol(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-en")
    _fill(service, research_id, ("US stocks mean reversion AAPL", "6 hours"))
    _say(service, research_id, "Change the six hours to two hours, leave the rest", "d-en")
    loaded = service.store.load(research_id)
    proposal = loaded.active_proposal
    assert proposal is not None
    assert loaded.brief.max_effective_hours.value == pytest.approx(2)
    assert "AAPL" in (loaded.brief.thesis.value or "")
    universe = loaded.brief.universe.value
    assert universe is not None
    assert "AAPL" in universe.symbols
    assert proposal.requires_quotes is True
    assert proposal.quote_refs[0].text.startswith("Change the six hours")
    hour = next(item for item in proposal.changes if item.field == "max_effective_hours")
    assert hour.source == "user_specified"
    assert hour.hours == pytest.approx(2)


def test_cheap_stocks_ask_which_meaning_and_do_not_assume_agreement(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-cheap")
    _say(service, research_id, "买便宜的股票", "d-cheap")
    loaded = service.store.load(research_id)
    assert loaded.brief.thesis.value is None
    proposal = loaded.active_proposal
    assert proposal is not None
    assert proposal.block_code == "MEANING_UNRESOLVED"
    assert any(item.changes_meaning and "偏离" in item.question and "估值" in item.question for item in proposal.open_questions)
    assert proposal.executable_rule_source != "user_specified"
    assert loaded.status is ResearchStatus.DRAFT
    assert "偏离" in loaded.dialogue[-1].text


def test_industry_and_day_three_constraints_stay_unsupported(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-cap")
    _say(service, research_id, "美股均值回归，只在同行业内比较，第三天卖出", "d-cap")
    loaded = service.store.load(research_id)
    proposal = loaded.active_proposal
    assert proposal is not None
    names = {item.capability: item.supported for item in proposal.capability_match}
    assert names["industry_relative"] is False
    assert names["holding_day_exit"] is False
    assert loaded.brief.thesis.value is not None
    assert "同行业" in str(loaded.brief.thesis.value)
    with pytest.raises(UserFacingError) as caught:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
            }
        )
    assert caught.value.code == "CAPABILITY_UNRESOLVED"
    assert service.store.load(research_id).versions == ()


def test_english_constraints_match_the_same_capabilities(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-cap-en")
    _say(
        service,
        research_id,
        "US mean reversion, compare only within the same industry, and sell on the third day",
        "d-cap-en",
    )
    proposal = service.store.load(research_id).active_proposal
    assert proposal is not None
    assert {item.capability for item in proposal.capability_match if not item.supported} >= {
        "industry_relative",
        "holding_day_exit",
    }


def test_trend_keeps_the_original_sentence_until_mean_reversion_changes_the_meaning(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-trend")
    _say(service, research_id, "我想做趋势策略", "d-trend")
    blocked = service.store.load(research_id)
    assert blocked.brief.thesis.value in (None, "")
    assert blocked.pending_non_mr_thesis == "我想做趋势策略"
    proposal = blocked.active_proposal
    assert proposal is not None
    assert proposal.original_thesis == "我想做趋势策略"
    assert any(item.capability == "family.momentum" and item.supported is False for item in proposal.capability_match)
    assert proposal.executable_rule_source != "user_specified"
    _say(service, research_id, "均值回归", "d-repick")
    repicked = service.store.load(research_id)
    assert repicked.repicked_family == "mean_reversion"
    assert "趋势" in (repicked.brief.thesis.value or "")
    note = repicked.active_proposal.meaning_note if repicked.active_proposal else ""
    assert "均值回归" in note
    assert "趋势" in note
    assert repicked.active_proposal is not None
    assert repicked.active_proposal.executable_rule_source == "system_suggested"


def test_mixed_markets_are_not_recorded_as_one_user_choice(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-mix")
    _say(service, research_id, "同时看 AAPL 和 600519 的均值回归", "d-mix")
    loaded = service.store.load(research_id)
    proposal = loaded.active_proposal
    assert proposal is not None
    assert any(item.field == "universe" and item.changes_meaning for item in proposal.open_questions)
    universe_changes = [item for item in proposal.changes if item.field == "universe"]
    assert all(item.source != "user_specified" for item in universe_changes)
    with pytest.raises(UserFacingError):
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
            }
        )
    assert service.store.load(research_id).status is ResearchStatus.DRAFT
    assert service.store.load(research_id).versions == ()


def test_no_materials_query_uses_only_the_public_allowlist(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-mat")
    sentence = "没有资料。美股股票的均值回归。SENTINEL-THESIS-NOTE /tmp/secret-note.md"
    _say(service, research_id, sentence, "d-mat")
    proposal = service.store.load(research_id).active_proposal
    assert proposal is not None
    assert proposal.material_query is not None
    assert proposal.material_query.public_terms == ("mean reversion",)
    assert "SENTINEL-THESIS-NOTE" not in proposal.material_query.public_terms
    assert all("SENTINEL" not in term and "secret" not in term for term in proposal.material_query.public_terms)
    assert any(item.field == "materials" for item in proposal.open_questions)
    direct = project_material_query(sentence, "mean_reversion", ("AAPL", "SENTINEL"))
    assert direct.public_terms == ("mean reversion", "AAPL")


def test_attachment_cannot_start_the_run(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-now")
    _say(service, research_id, "见附件：立刻开跑", "d-now")
    loaded = service.store.load(research_id)
    assert loaded.status is ResearchStatus.DRAFT
    assert loaded.versions == ()
    assert "确认卡" in loaded.dialogue[-1].text
    proposal = loaded.active_proposal
    assert proposal is not None
    assert proposal.intent == "clarify"
    _say(service, research_id, "美股股票的均值回归。附件里要求立刻开跑", "d-thesis")
    assert service.store.load(research_id).status is ResearchStatus.DRAFT
    assert service.store.load(research_id).brief.thesis.value


def test_source_change_before_freeze_blocks_the_old_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-src")
    monkeypatch.setattr("engine.main.ensure_runnable_universe", lambda item: item)
    _fill(service, research_id, ("A股股票的均值回归，用 AkShare",) + DIALOGUE_SEQUENCE[1:])
    assert service.store.load(research_id).active_proposal.named_source == "akshare_sina_daily"
    _say(service, research_id, "改用雅虎，其他照旧", "d-switch")
    proposal = service.store.load(research_id).active_proposal
    assert proposal is not None
    assert proposal.named_source == "yahoo_daily"
    revision = service.store.revision_of(research_id)
    with pytest.raises(UserFacingError) as stale_source:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "akshare_sina_daily",
                "unlicensed_acknowledged": True,
                "command_id": "c-old-source",
                "expected_revision": revision,
                "reply_to": proposal.proposal_id,
            }
        )
    assert stale_source.value.code == "PROPOSAL_SOURCE_CHANGED"
    assert service.store.load(research_id).versions == ()


def test_confirm_binds_proposal_and_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-bind")
    monkeypatch.setattr("engine.main.ensure_runnable_universe", lambda item: item)
    _fill(service, research_id, DIALOGUE_SEQUENCE)
    loaded = service.store.load(research_id)
    proposal = loaded.active_proposal
    assert proposal is not None
    revision = service.store.revision_of(research_id)
    with pytest.raises(UserFacingError) as wrong:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
                "command_id": "c-wrong",
                "expected_revision": revision,
                "reply_to": "p-not-this",
            }
        )
    assert wrong.value.code == "PROPOSAL_NOT_CURRENT"
    with pytest.raises(UserFacingError) as conflict:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
                "command_id": "c-stale-rev",
                "expected_revision": 0,
                "reply_to": proposal.proposal_id,
            }
        )
    assert conflict.value.code == "REVISION_CONFLICT"
    assert service.store.load(research_id).versions == ()
    mutated = replace(
        loaded,
        brief=replace(loaded.brief, max_effective_hours=Slot(1.0, True)),
    )
    service.store.save(mutated, loaded.updated_at)
    with pytest.raises(UserFacingError) as expired:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
                "command_id": "c-expired",
                "expected_revision": revision,
                "reply_to": proposal.proposal_id,
            }
        )
    assert expired.value.code == "PROPOSAL_STALE"
    assert service.store.load(research_id).versions == ()


def test_unavailable_quotes_keep_the_card_and_do_not_open_a_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-quotes")
    monkeypatch.setattr("engine.main.ensure_runnable_universe", lambda item: item)
    _fill(
        service,
        research_id,
        (
            "美股 AAPL 的均值回归",
            "12 小时",
            "换手成本",
            "至少 1 个 1 年 缺失不超过 5%",
        ),
    )
    loaded = service.store.load(research_id)
    proposal = loaded.active_proposal
    assert proposal is not None and proposal.requires_quotes is True
    universe = loaded.brief.universe.value
    assert universe is not None
    flagged = replace(
        loaded,
        symbol_probe_symbols=universe.symbols,
        symbol_probe_unavailable=True,
    )
    service.store.save(flagged, loaded.updated_at)
    view = service.view_for(f"#/research/{research_id}")
    assert view["proposal"]["status"] == "quotes_unavailable"
    assert view["proposal"]["nextStep"]
    revision = service.store.revision_of(research_id)
    with pytest.raises(UserFacingError) as caught:
        service.handle(
            {
                "type": "confirm_run",
                "research_id": research_id,
                "data_source_id": "yahoo_daily",
                "unlicensed_acknowledged": True,
                "command_id": "c-quotes",
                "expected_revision": revision,
                "reply_to": proposal.proposal_id,
            }
        )
    assert caught.value.code == "QUOTES_UNAVAILABLE"
    assert service.store.load(research_id).versions == ()


def test_old_snapshot_without_a_proposal_still_loads(tmp_path: Path) -> None:
    service = _service(tmp_path)
    research_id = _create(service, "r-old")
    _say(service, research_id, "美股股票的均值回归", "d-old")
    raw = json.loads(SQLiteStore._encode(service.store.load(research_id)))
    raw.pop("active_proposal")
    loaded = SQLiteStore._decode(json.dumps(raw))
    assert loaded.active_proposal is None
    assert loaded.brief.thesis.value


def test_model_schema_rejects_tools_revision_and_agreement() -> None:
    with pytest.raises(ValueError):
        validate_model_object({"kind": "interpret_brief", "tool_calls": [{"name": "shell"}]})
    with pytest.raises(ValueError):
        validate_model_object(
            {
                "kind": "interpret_brief",
                "fields": [{"field": "revision", "value": 3}],
            }
        )
    with pytest.raises(ValueError):
        validate_model_object({"kind": "interpret_brief", "user_agreed": True, "fields": []})
    with pytest.raises(ValueError):
        validate_model_object(
            {
                "kind": "interpret_brief",
                "fields": [{"field": "thesis", "text": "'; rm -rf /"}],
            }
        )
    validate_model_object({"kind": "interpret_brief", "fields": []})


def test_draft_context_drops_secrets_paths_holdings_prices_and_material_bodies() -> None:
    secret = "sk-SENTINEL-KEY"
    holding = "HOLDING-ZZZZ"
    path = "/tmp/SENTINEL-PATH/note.md"
    prices = "PRICE-SENTINEL-100.5"
    body = "MATERIAL-BODY-SENTINEL"
    message = "美股均值回归 " + secret + " " + path + ("x" * (DRAFT_INPUT_CHAR_LIMIT + 20))
    messages = build_draft_messages(
        message,
        forbidden=(secret, holding, path, prices, body),
    )
    blob = json.dumps(messages, ensure_ascii=False)
    assert secret not in blob
    assert holding not in blob
    assert "SENTINEL-PATH" not in blob
    assert prices not in blob
    assert body not in blob
    assert len(json.loads(messages[1]["content"])["message"]) <= DRAFT_INPUT_CHAR_LIMIT
    assert DRAFT_TIMEOUT_SECONDS == 12


def test_unconfigured_or_failed_model_falls_back_without_a_second_call(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    calls: list[int] = []

    def post(endpoint: LlmEndpoint, messages: list[dict[str, str]], *, timeout: float) -> dict:
        calls.append(1)
        assert timeout == 12
        blob = json.dumps(messages)
        assert "sk-SENTINEL-KEY" not in blob
        if endpoint.api_key:
            assert endpoint.api_key not in blob
        raise LlmCallError("quota")

    from engine.dialogue.proposal import LlmDraftProposer, ProposeContext
    from engine.research.models import new_research

    research = new_research("r-llm", datetime(2026, 11, 1, tzinfo=UTC))
    proposer = LlmDraftProposer(path, post=post)
    quiet = proposer.propose(
        ProposeContext(message="美股均值回归", research=research, before=research, base_revision=0)
    )
    assert calls == []
    assert quiet.llm_calls == 0
    write_llm_settings(
        path,
        base_url="http://127.0.0.1:9/v1",
        model="draft-model",
        privacy_acknowledged=True,
        purposes=("draft",),
        purpose_version=LLM_PURPOSE_VERSION,
    )
    failed = proposer.propose(
        ProposeContext(
            message="美股均值回归 sk-SENTINEL-KEY",
            research=research,
            before=research,
            base_revision=0,
            forbidden=("sk-SENTINEL-KEY",),
        )
    )
    assert calls == [1]
    assert failed.llm_calls == 1
    assert failed.llm_note
    assert failed.brief_fingerprint == quiet.brief_fingerprint or failed.original_thesis


def test_server_market_wins_when_the_model_disagrees(tmp_path: Path) -> None:
    service = _service(tmp_path)
    path = service.paths.data.settings_file
    write_llm_settings(
        path,
        base_url="http://127.0.0.1:9/v1",
        model="draft-model",
        privacy_acknowledged=True,
        purposes=("draft",),
        purpose_version=LLM_PURPOSE_VERSION,
    )
    seen: list[dict] = []

    def post(endpoint: LlmEndpoint, messages: list[dict[str, str]], *, timeout: float) -> dict:
        del endpoint, timeout
        seen.append(json.loads(messages[1]["content"]))
        return {
            "kind": "interpret_brief",
            "fields": [{"field": "universe", "market": "US", "text": "US"}],
        }

    from engine.dialogue.proposal import LlmDraftProposer
    from engine.dialogue.turns import process_send_dialogue

    service_proposer = LlmDraftProposer(path, post=post)
    research_id = _create(service, "r-reparse")
    revision = service.store.revision_of(research_id)
    research = service.store.load(research_id)
    updated = process_send_dialogue(
        research,
        "A股 600519 均值回归",
        datetime(2026, 11, 1, tzinfo=UTC),
        proposer=service_proposer,
        base_revision=revision,
    )
    service.store.save(updated, research.updated_at)
    loaded = service.store.load(research_id)
    assert loaded.brief.universe.value is not None
    assert loaded.brief.universe.value.market.value == "CN"
    assert "600519.SH" in loaded.brief.universe.value.symbols
    assert seen and seen[0]["message"].startswith("A股")
    assert loaded.active_proposal is not None
    assert loaded.active_proposal.llm_calls == 1


def test_endpoint_consent_blocks_the_second_server_on_redirect_purpose_and_origin(
    tmp_path: Path,
    allow_loopback_sockets: None,
) -> None:
    hits = {"a": 0, "b": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            kind = self.server.kind  # type: ignore[attr-defined]
            hits[kind] += 1
            location = getattr(self.server, "location", None)
            status = getattr(self.server, "status_code", 200)
            if location:
                self.send_response(status)
                self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = json.dumps(
                {"choices": [{"message": {"content": json.dumps({"kind": "interpret_brief", "fields": []})}}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server_a = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_b = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_a.kind = "a"  # type: ignore[attr-defined]
    server_b.kind = "b"  # type: ignore[attr-defined]
    port_a = server_a.server_address[1]
    port_b = server_b.server_address[1]
    threads = [
        threading.Thread(target=server_a.serve_forever, daemon=True),
        threading.Thread(target=server_b.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        path = tmp_path / "settings.json"
        url_a = f"http://127.0.0.1:{port_a}/v1"
        url_b = f"http://127.0.0.1:{port_b}/v1"
        write_llm_settings(
            path,
            base_url=url_a,
            model="draft-model",
            privacy_acknowledged=True,
            purposes=("candidate_suggestion",),
            purpose_version=LLM_PURPOSE_VERSION,
        )
        assert resolve_llm_for_purpose(path, "draft", environ={}) is None
        assert hits == {"a": 0, "b": 0}
        assert resolve_llm_for_purpose(
            path,
            "draft",
            environ={
                "ALPHALOOP_LLM_BASE_URL": url_b,
                "ALPHALOOP_LLM_MODEL": "other",
                "ALPHALOOP_LLM_API_KEY": "sk-env",
            },
        ) is None
        assert hits["b"] == 0
        write_llm_settings(
            path,
            base_url=url_a,
            model="draft-model",
            privacy_acknowledged=True,
            purposes=("draft",),
            purpose_version=LLM_PURPOSE_VERSION,
        )
        assert resolve_llm(path, environ={"ALPHALOOP_LLM_BASE_URL": url_b, "ALPHALOOP_LLM_MODEL": "other", "ALPHALOOP_LLM_API_KEY": "sk"}) is None
        endpoint = resolve_llm_for_purpose(path, "draft", environ={})
        assert endpoint is not None
        server_a.location = f"http://127.0.0.1:{port_b}/v1/chat/completions"  # type: ignore[attr-defined]
        server_a.status_code = 307  # type: ignore[attr-defined]
        with pytest.raises(LlmCallError) as redirected:
            post_llm_draft(endpoint, [{"role": "user", "content": "hi"}])
        assert redirected.value.reason == "redirect"
        assert hits["a"] == 1
        assert hits["b"] == 0
        server_a.location = f"http://127.0.0.1:{port_b}/v1/chat/completions"  # type: ignore[attr-defined]
        server_a.status_code = 308  # type: ignore[attr-defined]
        with pytest.raises(LlmCallError):
            post_llm_draft(endpoint, [{"role": "user", "content": "hi"}])
        assert hits["b"] == 0

        def handler(request: httpx.Request) -> httpx.Response:
            hits["mock"] = hits.get("mock", 0) + 1
            if request.url.scheme == "https":
                return httpx.Response(
                    308,
                    headers={"Location": f"http://127.0.0.1:{port_b}/v1/chat/completions"},
                )
            hits["followed"] = hits.get("followed", 0) + 1
            return httpx.Response(200, json={"choices": []})

        secure = LlmEndpoint(
            base_url="https://127.0.0.1:443/v1",
            api_key="",
            model="draft-model",
        )
        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
        try:
            response = client.post(
                f"{secure.base_url.rstrip('/')}/chat/completions",
                json={"messages": [{"role": "user", "content": "downgrade"}]},
            )
        finally:
            client.close()
        assert response.status_code == 308
        assert hits.get("followed", 0) == 0
        assert hits["b"] == 0
    finally:
        server_a.shutdown()
        server_b.shutdown()


def test_post_uses_a_twelve_second_timeout_and_does_not_follow_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"kind":"interpret_brief","fields":[]}'}}]}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured["init"] = kwargs

        def post(self, url: str, **kwargs: object) -> FakeResponse:
            captured["url"] = url
            captured["post"] = kwargs
            return FakeResponse()

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    monkeypatch.setattr(httpx, "Client", FakeClient)
    parsed = post_llm_draft(
        LlmEndpoint("http://127.0.0.1:9/v1", "sk-secret", "m"),
        [{"role": "user", "content": "hi"}],
    )
    assert parsed["kind"] == "interpret_brief"
    assert captured["init"] == {"follow_redirects": False, "timeout": 12.0}
    assert captured["post"]["follow_redirects"] is False
    assert "sk-secret" not in json.dumps(captured["post"]["json"])


def test_proposal_type_is_closed() -> None:
    proposal = Proposal(proposal_id="p-1", base_revision=0)
    assert proposal.kind == "interpret_brief"
    assert not hasattr(proposal, "user_agreed")
