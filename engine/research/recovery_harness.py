"""Subprocess entry for crash-barrier and billed-call recovery tests.

The parent seeds the database, sets ``ALPHALOOP_CRASH_BARRIER``, and kills this
process after the ready line. Restarting without the barrier resumes the same
file.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd

from engine.metrics import SimulationReport
from engine.research.clock import TimeBudget
from engine.research.frozen_input import ensure_frozen_version_input
from engine.research.loop import DefaultRoundBuilder, ResearchLoop
from engine.research.models import (
    AssetClass,
    Attempt,
    ChangeClass,
    CoverageFloor,
    Market,
    RoundDraft,
    Slot,
    Universe,
    new_research,
)
from engine.research.runtime import EnginePaths
from engine.research.specify import ProposedChange
from engine.research.state_machine import transition
from engine.research.store import SQLiteStore
from engine.review.subagent import ReviewerPort
from engine.strategy import StrategySpec
from engine.verifiers import VerificationReport, VerifierResult

PIN_START = date(2014, 1, 2)
PIN_END = date(2016, 12, 30)


class _PassReviewer(ReviewerPort):
    def run(self, round_draft: RoundDraft):
        from engine.research.models import ReviewReport

        return ReviewReport(True, ())


class _PanelPort:
    def load_daily(self, symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
        counter = os.environ.get("ALPHALOOP_LOAD_COUNTER", "")
        if counter:
            path = Path(counter)
            current = int(path.read_text(encoding="utf-8") or "0") if path.is_file() else 0
            path.write_text(str(current + 1), encoding="utf-8")
        index = pd.bdate_range(PIN_START, periods=40)
        if symbols == ("SPX",):
            return pd.DataFrame({"SPX": [100.0 + i for i in range(40)]}, index=index)
        return pd.DataFrame(
            {symbol: [10.0 + i for i in range(40)] for symbol in symbols},
            index=index,
        )


class HarnessBuilder(DefaultRoundBuilder):
    def build(self, research, attempt_number: int) -> RoundDraft:
        version = research.versions[research.current_version_number - 1]
        universe = research.brief.universe.value
        if universe is None or research.brief.thesis.value is None:
            raise ValueError("harness research is not runnable")
        ensure_frozen_version_input(
            snapshot_root=self.snapshot_root,
            research=research,
            version_number=version.number,
            symbols=universe.symbols,
            start=PIN_START,
            end=PIN_END,
            thesis=research.brief.thesis.value,
            material_ports=self.material_ports,
            live_port=self.data_port,
        )
        spec = StrategySpec(
            id=f"{research.research_id}-mean_reversion",
            thesis_locked=research.brief.thesis.value,
            universe=universe,
            frequency="1d",
            side="long_only",
            method_set=(),
            model_family="mean_reversion",
            lookback_days=20,
            entry_z=1.0,
        )
        round_number = len(version.rounds) + 1
        snapshot = self.snapshot_root / (
            f"{research.research_id}-v{version.number}-r{round_number}-a{attempt_number}.csv"
        )
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text("date,AAA\n2014-01-02,10\n", encoding="utf-8")
        attempt = Attempt(
            attempt_id=f"v{version.number}-r{round_number}-a{attempt_number}",
            number=attempt_number,
            change_class=ChangeClass.PARAM,
            spec=spec,
            simulation=_simulation(),
            verification=VerificationReport(
                (VerifierResult("scorecard.market", "scorecard-v1", True, {}, "ok"),)
            ),
            data_snapshot_path=snapshot,
        )
        return RoundDraft(version.number, round_number, attempt)

    def retry(self, prior: RoundDraft, review) -> RoundDraft:
        return prior

    def next_change(self, accepted: Attempt) -> ProposedChange:
        return ProposedChange("lookback_days", accepted.spec.lookback_days, accepted.spec.lookback_days)


def _simulation() -> SimulationReport:
    return SimulationReport(
        r_total=0.2,
        r_ann=0.12,
        sharpe=0.9,
        vol_ann=0.13,
        max_drawdown=-0.2,
        benchmark_id="SPX",
        r_bench_ann=0.08,
        excess_ann=0.04,
        tracking_error=0.06,
        information_ratio=2 / 3,
        sharpe_oos=0.7,
        sharpe_is=1.0,
        oos_segment_returns=(0.02, 0.01, -0.005),
        top_20_crowding_sharpe_impact=0.01,
        annual_turnover=1.0,
        observations=252,
        covered_assets=1,
        missing_pct=0.0,
        start=PIN_START,
        end=PIN_END,
    )


def seed_running(store: SQLiteStore, research_id: str, now) -> None:
    from dataclasses import replace

    from engine.research.models import ResearchEvent

    research = new_research(research_id, now)
    store.create(research)
    universe = Universe(Market.US, AssetClass.EQUITY, AssetClass.EQUITY, ("AAA",))
    locked = replace(
        research,
        brief=replace(
            research.brief,
            thesis=Slot("mean reversion", True),
            universe=Slot(universe, True),
            max_effective_hours=Slot(48.0, True),
            round1_methods=Slot((), True),
            coverage_floor=Slot(CoverageFloor(1, 1, 50.0), True),
        ),
        data_window_start=PIN_START,
        data_window_end=PIN_END,
        data_source_id="yahoo_daily",
        symbol_list_version="pool-v1",
    )
    store.save(locked, locked.updated_at)
    running = transition(store.load(research_id), ResearchEvent.CONFIRM_RUN, now)
    store.save(running, store.load(research_id).updated_at)


def main() -> None:
    from datetime import UTC, datetime
    from urllib.request import urlopen

    database = Path(os.environ["ALPHALOOP_RECOVERY_DB"])
    research_id = os.environ["ALPHALOOP_RECOVERY_ID"]
    store = SQLiteStore(database)
    mode = os.environ.get("ALPHALOOP_RECOVERY_MODE", "round")
    if mode == "billed":
        from engine.research.round_store import guarded_billed_call as _call

        def _send() -> str:
            with urlopen(os.environ["ALPHALOOP_FAKE_URL"], timeout=30) as response:
                return response.read().decode("utf-8")

        _call(
            store,
            research_id=research_id,
            version=1,
            round_number=1,
            attempt=1,
            step="review",
            input_hash="billed-key",
            call=_send,
            idempotent=os.environ.get("ALPHALOOP_IDEMPOTENT") == "1",
            authorize=os.environ.get("ALPHALOOP_AUTHORIZE_REBILL") == "1",
        )
        return
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    if store.research_head(research_id) is None:
        seed_running(store, research_id, now)
    paths = EnginePaths.for_colocated_root(database.parent)
    builder = HarnessBuilder(
        material_ports=(),
        data_port=_PanelPort(),
        start=PIN_START,
        end=PIN_END,
        snapshot_root=paths.data.snapshots_dir,
    )
    loop = ResearchLoop(store, builder, _PassReviewer(), TimeBudget(lambda: 0.0), lambda: now)
    loop.run_once(research_id)


if __name__ == "__main__":
    main()
