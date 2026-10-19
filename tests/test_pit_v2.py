"""P0-1: publication dates, pit-v2 diagnostics, and strict PIT."""

from __future__ import annotations

import json
import os
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import jsonschema
import pandas as pd
import pytest

from engine.export import build_research_record_pack, build_strategy_pack, strategy_pack_eligibility
from engine.main import ResearchCommandService
from engine.research.clock import TimeBudget
from engine.research.gather import (
    CROSSREF_MAILTO,
    LocalMaterialAdapter,
    Material,
    PapersAdapter,
    SecEdgarAdapter,
    published_at_from_crossref_issued,
    published_at_from_markdown,
)
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.models import (
    AssetClass,
    Market,
    MethodRef,
    ResearchEvent,
    ResearchStatus,
    ReviewReport,
    Universe,
    new_research,
)
from engine.research.runtime import EnginePaths
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.review.deterministic import DeterministicReviewer
from engine.strategy import MarketPanel, MeanReversionStrategy
from engine.verifiers import (
    NO_EXTERNAL_EVIDENCE_NOTE,
    PIT_REVISION_V2,
    PIT_SCOPE,
    run_verifiers,
)
from tests.fixtures.honest_reversal_panel import honest_reversal_frames
from tests.test_export_pack import completed_research
from tests.test_verifiers import passing_report, spec

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_crossref_issued_year_only_uses_year_end() -> None:
    assert published_at_from_crossref_issued({"date-parts": [[2019]]}) == date(2019, 12, 31)


def test_crossref_issued_year_month_uses_month_end() -> None:
    assert published_at_from_crossref_issued({"date-parts": [[2019, 5]]}) == date(2019, 5, 31)
    assert published_at_from_crossref_issued({"date-parts": [[2019, 2]]}) == date(2019, 2, 28)
    assert published_at_from_crossref_issued({"date-parts": [[2016, 2]]}) == date(2016, 2, 29)


def test_crossref_issued_full_date_and_missing() -> None:
    assert published_at_from_crossref_issued({"date-parts": [[2019, 5, 17]]}) == date(2019, 5, 17)
    assert published_at_from_crossref_issued(None) is None
    assert published_at_from_crossref_issued({}) is None
    assert published_at_from_crossref_issued({"date-parts": []}) is None
    assert published_at_from_crossref_issued({"date-parts": [[2019, 2, 30]]}) is None
    created_only = {"created": {"date-parts": [[2019, 1, 2]]}}
    assert published_at_from_crossref_issued(created_only.get("issued")) is None


def test_markdown_header_date_is_not_mtime(tmp_path: Path) -> None:
    dated = tmp_path / "dated.md"
    dated.write_text("---\npublished: 2018-03-04\n---\n\nbody published: 1999-01-01\n", encoding="utf-8")
    os.utime(dated, (1_700_000_000, 1_700_000_000))
    assert published_at_from_markdown(dated.read_text(encoding="utf-8")) == date(2018, 3, 4)
    undated = tmp_path / "undated.md"
    undated.write_text("published: 2018-03-04\nno front matter\n", encoding="utf-8")
    os.utime(undated, (1_700_000_000, 1_700_000_000))
    assert published_at_from_markdown(undated.read_text(encoding="utf-8")) is None


class _Response:
    def __init__(self, payload: dict[str, object], status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://api.crossref.org/works")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("crossref", request=request, response=response)

    def json(self) -> dict[str, object]:
        return self._payload


class _Client:
    def __init__(self, payload: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.payload = payload or {"message": {"items": []}}
        self.error = error
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object] | None = None, headers: dict[str, str] | None = None, timeout: float | None = None) -> _Response:
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        if self.error is not None:
            raise self.error
        status = 429 if params and params.get("status") == 429 else 200
        return _Response(self.payload, status)


def test_papers_adapter_uses_issued_not_created_or_fetched_at() -> None:
    client = _Client(
        {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/year",
                        "title": ["Year only"],
                        "URL": "https://example.test/year",
                        "abstract": "abstract",
                        "issued": {"date-parts": [[2019]]},
                        "created": {"date-parts": [[2024, 1, 2]]},
                    },
                    {
                        "DOI": "10.1000/none",
                        "title": ["No date"],
                        "created": {"date-parts": [[2018, 1, 1]]},
                    },
                ]
            }
        }
    )
    fetched_at = datetime(2026, 10, 19, 1, 2, tzinfo=UTC)
    adapter = PapersAdapter(client, lambda: fetched_at)  # type: ignore[arg-type]
    materials = adapter.fetch("mean reversion")
    params = client.calls[0]["params"]
    assert isinstance(params, dict)
    assert "issued" in str(params.get("select"))
    assert "created" not in str(params.get("select"))
    assert params.get("mailto") == CROSSREF_MAILTO
    by_id = {item.material_id: item for item in materials}
    assert by_id["doi:10.1000/year"].published_at == date(2019, 12, 31)
    assert by_id["doi:10.1000/year"].published_precision == "year"
    assert by_id["doi:10.1000/year"].published_at != fetched_at.date()
    assert by_id["doi:10.1000/none"].published_at is None
    assert by_id["doi:10.1000/none"].fetched_at == fetched_at


def test_papers_adapter_fetch_failure_is_recorded_and_empty() -> None:
    client = _Client(error=httpx.ConnectError("down"))
    adapter = PapersAdapter(client, lambda: NOW)  # type: ignore[arg-type]
    assert adapter.fetch("mean reversion") == ()
    assert adapter.fetch_errors
    assert "crossref" in adapter.fetch_errors[0]


def test_sec_adapter_never_uses_fetched_at_as_published_at() -> None:
    client = _Client(
        {
            "0": {"cik_str": 1234, "ticker": "MEAN", "title": "Mean Reversion Inc"},
        }
    )
    # SEC adapter reads the top-level mapping, not message.items.
    adapter = SecEdgarAdapter(client, lambda: NOW, "alphaloop/0.2 research@example.invalid")  # type: ignore[arg-type]
    materials = adapter.fetch("mean reversion")
    assert materials
    assert all(item.published_at is None for item in materials)
    assert all(item.fetched_at == NOW for item in materials)


def test_local_adapter_reads_front_matter_only(tmp_path: Path) -> None:
    root = tmp_path / "notes"
    root.mkdir()
    (root / "dated.md").write_text("---\npublished: 2014-07-09\n---\nmean reversion\n", encoding="utf-8")
    (root / "bare.md").write_text("mean reversion without a header date\n", encoding="utf-8")
    os.utime(root / "dated.md", (1_600_000_000, 1_600_000_000))
    os.utime(root / "bare.md", (1_600_000_000, 1_600_000_000))
    adapter = LocalMaterialAdapter(root, lambda: NOW)
    materials = {item.material_id: item for item in adapter.fetch("mean reversion")}
    assert materials["local:dated.md"].published_at == date(2014, 7, 9)
    assert materials["local:bare.md"].published_at is None


def test_pit_v2_reports_scope_and_keeps_strict_failures() -> None:
    report = passing_report()
    base = spec()
    passed = run_verifiers(
        report,
        base,
        evidence_as_of=(("doi:10.1000/old", "2014-01-01"),),
        undated_excluded=("local:bare.md",),
        pit_revision=PIT_REVISION_V2,
    )
    pit = next(item for item in passed.results if item.verifier_id == "pit.consistency")
    assert pit.revision == PIT_REVISION_V2
    assert pit.passed is True
    assert pit.evidence_used == 1
    assert pit.undated_excluded == ("local:bare.md",)
    assert pit.scope == PIT_SCOPE
    assert pit.note == ""
    assert pit.rule == "all evidence as_of <= backtest cutoff"

    late = run_verifiers(
        report,
        base,
        evidence_as_of=(("doi:10.37155/3041-0827-0207-3", "2026-12-31"),),
        evidence_annotations=(("doi:10.37155/3041-0827-0207-3", "年份论文", "year"),),
        pit_revision=PIT_REVISION_V2,
    )
    late_pit = next(item for item in late.results if item.verifier_id == "pit.consistency")
    assert late_pit.passed is False
    assert any("doi:10.37155/3041-0827-0207-3" in item for item in late_pit.violations)
    assert late_pit.violation_details[0].title == "年份论文"
    assert late_pit.violation_details[0].precision == "year"
    assert late_pit.violation_details[0].published_at == "2026-12-31"
    assert late_pit.backtest_cutoff == report.end.isoformat()
    v1_late = run_verifiers(
        report,
        base,
        evidence_as_of=(("doi:10.37155/3041-0827-0207-3", "2026-12-31"),),
        evidence_annotations=(("doi:10.37155/3041-0827-0207-3", "年份论文", "year"),),
    )
    v1_pit = next(item for item in v1_late.results if item.verifier_id == "pit.consistency")
    assert v1_pit.revision == "pit-v1"
    assert v1_pit.violation_details == ()

    missing = run_verifiers(
        report,
        base,
        missing_as_of_material_ids=("local:claimed.md",),
        pit_revision=PIT_REVISION_V2,
    )
    missing_pit = next(item for item in missing.results if item.verifier_id == "pit.consistency")
    assert missing_pit.passed is False
    assert any("missing as_of" in item for item in missing_pit.violations)


def test_pit_v2_empty_evidence_passes_with_disclosure() -> None:
    result = run_verifiers(passing_report(), spec(), pit_revision=PIT_REVISION_V2)
    pit = next(item for item in result.results if item.verifier_id == "pit.consistency")
    assert pit.passed is True
    assert pit.evidence_used == 0
    assert pit.undated_excluded == ()
    assert pit.note == NO_EXTERNAL_EVIDENCE_NOTE
    assert pit.scope == PIT_SCOPE


def test_default_run_verifiers_stays_on_pit_v1() -> None:
    pit = next(
        item
        for item in run_verifiers(passing_report(), spec()).results
        if item.verifier_id == "pit.consistency"
    )
    assert pit.revision == "pit-v1"
    assert pit.evidence_used == 0
    assert pit.scope == ""
    assert pit.note == ""


class _PanelPort:
    def __init__(self) -> None:
        self.prices, self.benchmark = honest_reversal_frames()

    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        if symbols == ("SPX",):
            return self.benchmark
        return self.prices[list(symbols)]


class _RaisingPort:
    def fetch(self, query: str) -> tuple[Material, ...]:
        raise RuntimeError("crossref down")


class _MixedPort:
    def fetch(self, query: str) -> tuple[Material, ...]:
        return (
            Material(
                material_id="doi:10.1000/used",
                source="papers",
                title="Used",
                url="https://example.test/used",
                text="mean reversion",
                fetched_at=NOW,
                published_at=date(2011, 1, 15),
            ),
            Material(
                material_id="local:bare.md",
                source="local",
                title="Bare",
                url="file:///bare.md",
                text="mean reversion",
                fetched_at=NOW,
                published_at=None,
            ),
        )


def _running_research(store: SQLiteStore, research_id: str = "pit-run") -> None:
    prices, _benchmark = honest_reversal_frames()
    research = new_research(research_id, NOW)
    store.create(research)
    universe = Universe(
        Market.US,
        AssetClass.EQUITY,
        AssetClass.EQUITY,
        tuple(str(column) for column in prices.columns),
    )
    methods = (
        MethodRef("overfit.walk", "walk-v1"),
        MethodRef("stability.oos", "stability-v1"),
        MethodRef("crowding.load", "crowding-v1"),
        MethodRef("cost.turnover", "cost-v1"),
    )
    from engine.research.models import CoverageFloor, Slot

    locked = replace(
        research,
        brief=replace(
            research.brief,
            thesis=Slot("cross sectional mean reversion", True),
            universe=Slot(universe, True),
            max_effective_hours=Slot(48.0, True),
            round1_methods=Slot(methods, True),
            coverage_floor=Slot(CoverageFloor(len(universe.symbols), 5, 0.2), True),
        ),
    )
    store.save(locked, locked.updated_at)
    running = transition(locked, ResearchEvent.CONFIRM_RUN, NOW)
    store.save(running, running.updated_at)


def test_zero_materials_and_fetch_failure_do_not_abort(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "empty.db")
    _running_research(store)
    paths = EnginePaths.for_colocated_root(tmp_path)
    research = store.load("pit-run")
    builder = DefaultRoundBuilder(
        material_ports=(),
        data_port=_PanelPort(),
        start=date(2012, 1, 3),
        end=date(2018, 1, 1),
        snapshot_root=paths.data.snapshots_dir,
    )
    draft = builder.build(research, 1)
    pit = next(item for item in draft.attempt.verification.results if item.verifier_id == "pit.consistency")
    assert pit.passed is True
    assert pit.revision == PIT_REVISION_V2
    assert pit.evidence_used == 0
    assert pit.note == NO_EXTERNAL_EVIDENCE_NOTE

    failing = DefaultRoundBuilder(
        material_ports=(_RaisingPort(),),  # type: ignore[arg-type]
        data_port=_PanelPort(),
        start=date(2012, 1, 3),
        end=date(2018, 1, 1),
        snapshot_root=paths.data.snapshots_dir,
    )
    degraded = failing.build(replace(research, research_id="pit-fail"), 1)
    degraded_pit = next(
        item for item in degraded.attempt.verification.results if item.verifier_id == "pit.consistency"
    )
    assert degraded_pit.passed is True
    assert degraded_pit.note == NO_EXTERNAL_EVIDENCE_NOTE
    failure_log = paths.data.snapshots_dir.parent / "materials" / "gather-failures.json"
    assert failure_log.is_file()
    assert "crossref down" in failure_log.read_text(encoding="utf-8")


def test_build_and_retry_exclude_undated_materials(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mix.db")
    _running_research(store, "pit-mix")
    paths = EnginePaths.for_colocated_root(tmp_path)
    research = store.load("pit-mix")
    builder = DefaultRoundBuilder(
        material_ports=(_MixedPort(),),  # type: ignore[arg-type]
        data_port=_PanelPort(),
        start=date(2012, 1, 3),
        end=date(2018, 1, 1),
        snapshot_root=paths.data.snapshots_dir,
    )
    draft = builder.build(research, 1)
    pit = next(item for item in draft.attempt.verification.results if item.verifier_id == "pit.consistency")
    assert pit.passed is True
    assert pit.evidence_used == 1
    assert pit.undated_excluded == ("local:bare.md",)
    assert pit.evidence_timestamps == (("doi:10.1000/used", "2011-01-15"),)
    retried = builder.retry(draft, ReviewReport(passed=False, findings=()))
    retried_pit = next(
        item for item in retried.attempt.verification.results if item.verifier_id == "pit.consistency"
    )
    assert retried_pit.revision == PIT_REVISION_V2
    assert retried_pit.passed is True
    assert retried_pit.evidence_used == 1
    assert retried_pit.undated_excluded == ("local:bare.md",)


def _reverify_research(tmp_path: Path, *, revision: str, evidence: dict[str, object], research_id: str):
    index = pd.bdate_range("2020-01-02", periods=40)
    frame = pd.DataFrame(
        {
            "AAA": range(40, 80),
            "BBB": range(20, 60),
            "__benchmark__": range(100, 140),
        },
        index=index,
    )
    snapshot = tmp_path / f"{research_id}.csv"
    frame.to_csv(snapshot, index_label="date")
    evidence_path = tmp_path / f"{research_id}-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    research = completed_research()
    attempt = research.versions[0].rounds[0].accepted_attempt
    pit = next(item for item in attempt.verification.results if item.verifier_id == "pit.consistency")
    updated_pit = replace(pit, revision=revision, passed=True, violations=())
    updated_results = tuple(
        updated_pit if item.verifier_id == "pit.consistency" else item
        for item in attempt.verification.results
    )
    updated_attempt = replace(
        attempt,
        verification=type(attempt.verification)(updated_results),
        data_snapshot_path=snapshot,
        evidence_paths=(evidence_path,),
    )
    updated = replace(
        research,
        research_id=research_id,
        versions=(
            replace(
                research.versions[0],
                rounds=(
                    replace(
                        research.versions[0].rounds[0],
                        round_id=f"{research_id}-r1",
                        accepted_attempt=updated_attempt,
                    ),
                ),
            ),
        ),
    )
    store = SQLiteStore(tmp_path / f"{research_id}.db")
    service = ResearchCommandService(store, EnginePaths.for_colocated_root(tmp_path / research_id))
    service.store.create(updated)
    service.handle(
        {
            "type": "reverify",
            "research_id": research_id,
            "round_id": f"{research_id}-r1",
            "method_id": "pit.consistency",
        }
    )
    loaded = service.store.load(research_id)
    report = loaded.reverifications[-1].report
    assert isinstance(report, dict)
    return next(item for item in report["results"] if item["verifier_id"] == "pit.consistency")


def test_reverify_keeps_pit_v1_and_can_run_pit_v2(tmp_path: Path) -> None:
    legacy = _reverify_research(
        tmp_path,
        revision="pit-v1",
        evidence={
            "material_id": "doi:10.1000/legacy",
            "source": "papers",
            "title": "Legacy",
            "url": "https://example.test/legacy",
            "text": "no date",
            "fetched_at": "2020-01-01T00:00:00+00:00",
        },
        research_id="pit-legacy",
    )
    assert legacy["revision"] == "pit-v1"
    assert legacy["passed"] is False
    assert any("missing as_of" in item for item in legacy["violations"])

    current = _reverify_research(
        tmp_path,
        revision=PIT_REVISION_V2,
        evidence={
            "material_id": "doi:10.1000/current",
            "source": "papers",
            "title": "Current",
            "url": "https://example.test/current",
            "text": "dated",
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "published_at": "2019-06-01",
        },
        research_id="pit-current",
    )
    assert current["revision"] == PIT_REVISION_V2
    assert current["passed"] is True
    assert current["evidence_used"] == 1
    assert current["scope"] == PIT_SCOPE


def test_old_state_json_roundtrip_keeps_numbers(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "old.db")
    research = completed_research()
    store.create(research)
    raw = store.connection.execute(
        "SELECT state_json FROM researches WHERE research_id=?",
        (research.research_id,),
    ).fetchone()[0]
    payload = json.loads(raw)
    simulation = payload["versions"][0]["rounds"][0]["accepted_attempt"]["simulation"]
    expected = {
        "sharpe": simulation["sharpe"],
        "sharpe_oos": simulation["sharpe_oos"],
        "excess_ann": simulation["excess_ann"],
        "max_drawdown": simulation["max_drawdown"],
        "r_ann": simulation["r_ann"],
    }

    def strip(value: object) -> object:
        if isinstance(value, dict):
            if value.get("verifier_id") == "pit.consistency":
                for key in ("evidence_used", "undated_excluded", "scope", "note"):
                    value.pop(key, None)
                value.pop("violation_details", None)
            return {key: strip(item) for key, item in value.items()}
        if isinstance(value, list):
            return [strip(item) for item in value]
        return value

    stripped = json.dumps(strip(payload), sort_keys=True)
    with store.connection:
        store.connection.execute(
            "UPDATE researches SET state_json=? WHERE research_id=?",
            (stripped, research.research_id),
        )
    loaded = store.load(research.research_id)
    attempt = loaded.versions[0].rounds[0].accepted_attempt
    for field, value in expected.items():
        assert getattr(attempt.simulation, field) == value
    pit = next(item for item in attempt.verification.results if item.verifier_id == "pit.consistency")
    assert pit.passed is True
    assert pit.revision == "pit-v1"
    assert pit.evidence_used == 0
    assert pit.undated_excluded == ()
    assert pit.scope == ""
    assert pit.note == ""


def test_offline_honest_panel_reaches_four_green_gates(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "honest.db")
    _running_research(store, "honest")
    paths = EnginePaths.for_colocated_root(tmp_path)
    loop = ResearchLoop(
        store,
        DefaultRoundBuilder(
            material_ports=(_MixedPort(),),  # type: ignore[arg-type]
            data_port=_PanelPort(),
            start=date(2012, 1, 3),
            end=date(2018, 1, 1),
            snapshot_root=paths.data.snapshots_dir,
        ),
        DeterministicReviewer(),
        TimeBudget(lambda: 0.0),
        lambda: NOW,
    )
    current = store.load("honest")
    for _ in range(6):
        if current.status is ResearchStatus.COMPLETED:
            break
        current = loop.run_once(current.research_id)
    assert current.status is ResearchStatus.COMPLETED
    attempt = current.versions[-1].rounds[-1].accepted_attempt
    by_id = {item.verifier_id: item for item in attempt.verification.results}
    assert by_id["scorecard.market"].passed is True
    assert by_id["overfit.walk"].passed is True
    assert by_id["stability.oos"].passed is True
    assert by_id["crowding.load"].passed is True
    assert by_id["cost.turnover"].passed is True
    assert by_id["pit.consistency"].passed is True
    assert by_id["pit.consistency"].revision == PIT_REVISION_V2
    assert by_id["pit.consistency"].evidence_used == 1
    assert by_id["pit.consistency"].undated_excluded == ("local:bare.md",)
    assert by_id["pit.consistency"].scope == PIT_SCOPE
    eligibility = strategy_pack_eligibility(current)
    assert eligibility.eligible is True
    assert "pit_executed_and_passed" not in eligibility.failed_checks
    prices, benchmark = honest_reversal_frames()
    panel = MarketPanel(prices, NOW, benchmark["SPX"])
    archive = build_strategy_pack(
        current,
        MeanReversionStrategy(attempt.spec),
        panel,
        tmp_path / "strategy-pack.zip",
    )
    manifest = json.loads(zipfile.ZipFile(archive).read("manifest.json"))
    schema = json.loads(Path("contracts/strategy-pack.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)
    assert manifest["schema_version"] == "1"
    assert manifest["live_handoff_eligible"] is True
    pit_block = manifest["pit_verification"]
    assert pit_block["passed"] is True
    assert pit_block["evidence_used"] == 1
    assert pit_block["undated_excluded"] == ["local:bare.md"]
    assert pit_block["scope"] == PIT_SCOPE
    sources = json.loads(zipfile.ZipFile(archive).read("materials/sources.json"))
    assert [item["material_id"] for item in sources["used"]] == ["doi:10.1000/used"]
    assert [item["material_id"] for item in sources["browsed_not_used"]] == ["local:bare.md"]
    record = build_research_record_pack(current, tmp_path / "record.zip")
    record_text = zipfile.ZipFile(record).read("history/pit_verification.json").decode("utf-8")
    assert PIT_SCOPE in record_text
    why = json.loads(zipfile.ZipFile(record).read("why_not_live.json"))
    assert why["pit_scope"] == PIT_SCOPE


@pytest.mark.network
@pytest.mark.skipif(
    os.environ.get("ALPHALOOP_ACCEPTANCE_NETWORK") != "1",
    reason="live Crossref PIT check requires ALPHALOOP_ACCEPTANCE_NETWORK=1",
)
def test_live_crossref_pit_is_not_a_missing_date_failure() -> None:
    adapter = PapersAdapter(httpx.Client(), lambda: datetime.now(UTC))
    materials = adapter.fetch("equity mean reversion")
    assert adapter.fetch_errors == []
    assert materials
    dated = tuple(item for item in materials if item.published_at is not None)
    undated = tuple(item for item in materials if item.published_at is None)
    assert dated, "Crossref issued dates should parse for at least one work"
    cutoff = date.today()
    live_report = replace(passing_report(), end=cutoff)
    verification = run_verifiers(
        live_report,
        spec(),
        evidence_as_of=tuple((item.material_id, item.published_at.isoformat()) for item in dated),
        undated_excluded=tuple(item.material_id for item in undated),
        pit_revision=PIT_REVISION_V2,
    )
    pit = next(item for item in verification.results if item.verifier_id == "pit.consistency")
    assert pit.evidence_used == len(dated)
    assert pit.undated_excluded == tuple(item.material_id for item in undated)
    assert pit.scope == PIT_SCOPE
    assert all("missing as_of" not in item for item in pit.violations)
    late = [item.material_id for item in dated if item.published_at > cutoff]
    if late:
        assert pit.passed is False
        for material_id in late:
            assert any(material_id in item for item in pit.violations)
    else:
        assert pit.passed is True
    citable = tuple(item for item in dated if item.published_at <= cutoff)
    if citable:
        cited = run_verifiers(
            live_report,
            spec(),
            evidence_as_of=tuple(
                (item.material_id, item.published_at.isoformat()) for item in citable
            ),
            pit_revision=PIT_REVISION_V2,
        )
        cited_pit = next(item for item in cited.results if item.verifier_id == "pit.consistency")
        assert cited_pit.passed is True
        assert cited_pit.evidence_used == len(citable)
