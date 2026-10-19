"""fetch_view routes must pass the desktop API schema on the real /commands path."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine.main import ResearchCommandService, start_api
from engine.research.models import new_research
from engine.research.runtime import EnginePaths
from engine.research.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_SRC = ROOT / "apps" / "desktop" / "src"
ALLOWED_PREFIXES = frozenset({"research", "methods", "glossary"})

NOW = datetime(2026, 10, 19, 8, 0, tzinfo=UTC)

pytestmark = pytest.mark.usefixtures("allow_loopback_sockets")

# Routes the desktop actually sends (list, detail, method id, glossary, queries).
FRONTEND_ROUTES = (
    ("#/research", "research_list"),
    ("#/research?status=draft", "research_list"),
    ("#/research/r-front", "draft"),
    ("#/methods", "methods"),
    ("#/methods/overfit.walk", "methods"),
    ("#/glossary", "glossary"),
    ("#/glossary?section=gates", "glossary"),
)


def _post(endpoint: str, token: str, body: dict) -> tuple[int, dict]:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint}/commands",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


@pytest.fixture
def api(tmp_path: Path):
    store = SQLiteStore(tmp_path / "routes.db")
    store.create(new_research("r-front", NOW))
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path))
    token = "route-token"
    server, endpoint = start_api(service, token)
    yield endpoint, token
    server.shutdown()


@pytest.mark.parametrize(("route", "kind"), FRONTEND_ROUTES)
def test_http_fetch_view_accepts_frontend_route(api: tuple[str, str], route: str, kind: str) -> None:
    endpoint, token = api
    status, body = _post(endpoint, token, {"type": "fetch_view", "route": route})
    assert status == 200, body
    assert body["kind"] == kind
    if route.startswith("#/glossary"):
        terms = {item["term"] for item in body["entries"]}
        assert "分段稳健性检验" in terms
        assert "集中度" in terms
        assert body["intro"]
    if route == "#/methods/overfit.walk":
        assert body["selected"] == "overfit.walk"


def _frontend_hash_prefixes() -> set[str]:
    """Hash prefixes the desktop shell can send. Tests are not the product."""
    found: set[str] = set()
    for path in DESKTOP_SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx"} or ".test." in path.name:
            continue
        found.update(re.findall(r"#/([a-z][a-z0-9-]*)", path.read_text(encoding="utf-8")))
    return found


def test_frontend_hash_prefixes_stay_inside_the_schema_allowlist() -> None:
    found = _frontend_hash_prefixes()
    assert found == ALLOWED_PREFIXES


def test_http_fetch_view_rejects_unknown_route(api: tuple[str, str]) -> None:
    endpoint, token = api
    status, body = _post(endpoint, token, {"type": "fetch_view", "route": "#/orders"})
    assert status == 400
    assert "does not match" in body["error"]
    assert "#/orders" in body["error"]
    assert "research|methods|glossary" in body["error"]
