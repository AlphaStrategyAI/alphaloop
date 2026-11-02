"""Stage an export privately, authorize it, then publish by atomic rename.

The SQLite authorization row is the handoff. A ZIP without that row is not a
pack anyone can recover into the visible directory.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from engine.export import (
    ExportEligibility,
    build_research_record_pack,
    build_strategy_pack,
    strategy_pack_eligibility,
)
from engine.export_paths import export_zip_filename
from engine.research.e2e_hooks import export_crash_after_authorize, export_recheck_failures
from engine.research.models import ExportKind, ExportRecord, Research
from engine.strategy import MarketPanel, MeanReversionStrategy


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_hash(research: Research, kind: str, round_id: str | None) -> str:
    payload = {
        "research_id": research.research_id,
        "kind": kind,
        "version": research.current_version_number,
        "round_id": round_id,
        "status": research.status.value,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _round_binding(research: Research) -> tuple[str | None, str, str]:
    if not research.versions or not research.versions[-1].rounds:
        return None, "", ""
    attempt = research.versions[-1].rounds[-1].accepted_attempt
    round_id = research.versions[-1].rounds[-1].round_id
    input_hash = ""
    if attempt.data_snapshot_path is not None and attempt.data_snapshot_path.is_file():
        input_hash = _sha256(attempt.data_snapshot_path)
    revision = ""
    spec = attempt.spec
    refs = tuple(getattr(spec, "method_set", ()) or ())
    if refs:
        revision = ",".join(f"{item.method_id}@{item.revision_hash}" for item in refs)
    return round_id, input_hash, revision


def _record_from_json(payload: str) -> ExportRecord:
    raw = json.loads(payload)
    return ExportRecord(
        export_id=str(raw["export_id"]),
        kind=ExportKind(raw["kind"]),
        path=str(raw["path"]),
        version_number=raw.get("version_number"),
        created_at=datetime.fromisoformat(raw["created_at"]),
        failed_checks=tuple(raw.get("failed_checks") or ()),
        overturned=bool(raw.get("overturned", False)),
        round_id=raw.get("round_id"),
        input_hash=raw.get("input_hash"),
        method_revision=raw.get("method_revision"),
        association=str(raw.get("association") or ""),
        fingerprint=str(raw.get("fingerprint") or ""),
        command_id=str(raw.get("command_id") or ""),
    )


def _record_json(record: ExportRecord) -> str:
    payload = asdict(record)
    payload["kind"] = record.kind.value
    payload["created_at"] = record.created_at.isoformat()
    payload["failed_checks"] = list(record.failed_checks)
    return json.dumps(payload, sort_keys=True)


def _hash_matches(path: Path, fingerprint: str) -> bool:
    return path.is_file() and _sha256(path) == fingerprint


def recover_publish(store, research: Research) -> Research:
    """Publish only when an authorization row exists and the bytes match it."""
    rows = store.connection.execute(
        """
        SELECT command_id, fingerprint, private_path, final_path, receipt_json
          FROM publish_authorization
         WHERE research_id=?
         ORDER BY created_at
        """,
        (research.research_id,),
    ).fetchall()
    exports = list(research.exports)
    known = {item.export_id for item in exports}
    for command_id, fingerprint, private_path, final_path, receipt_json in rows:
        final = Path(final_path)
        private = Path(private_path)
        if _hash_matches(final, fingerprint):
            source = final
        elif _hash_matches(private, fingerprint):
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(private, final)
            source = final
        elif not private.is_file() and not final.is_file():
            raise ValueError(
                f"publish recovery missing file for command {command_id}"
            )
        else:
            raise ValueError(
                f"publish recovery hash mismatch for command {command_id}"
            )
        if not _hash_matches(source, fingerprint):
            raise ValueError(f"publish recovery hash mismatch for command {command_id}")
        record = _record_from_json(receipt_json)
        if record.export_id not in known:
            exports.append(record)
            known.add(record.export_id)
    if tuple(exports) == research.exports:
        return research
    return replace(research, exports=tuple(exports))


def _refuse(store, research: Research, eligibility, now: datetime) -> None:
    reason = " ".join(eligibility.reasons) if eligibility.reasons else ""
    message = f"research is not strategy-pack eligible: {eligibility.failed_checks}"
    if reason:
        message = f"{message} {reason}"
    store.save_with_event(
        research,
        research.updated_at,
        "export_refused",
        {"failed_checks": list(eligibility.failed_checks), "reason": reason or message},
    )
    raise ValueError(message)


def publish_export(store, paths, research: Research, request: dict[str, Any], now: datetime):
    """Return (research, destination, fingerprint, command_id) after a visible publish."""
    kind_name = str(request["kind"])
    command_id = str(request.get("command_id") or "")
    if not command_id:
        import uuid

        command_id = str(uuid.uuid4())
    eligibility = strategy_pack_eligibility(research)
    if kind_name != "research_record" and not eligibility.eligible:
        _refuse(store, research, eligibility, now)
    filename = export_zip_filename(
        research,
        "research_record" if kind_name == "research_record" else "strategy_pack",
        now=now,
    )
    private_path = paths.data.root / "export-private" / command_id / filename
    final_path = paths.data.exports_dir / command_id / filename
    existing = store.get_publish_authorization(research.research_id, command_id)
    if existing is not None:
        restored = recover_publish(store, research)
        final = Path(existing["final_path"])
        if not _hash_matches(final, existing["fingerprint"]):
            raise ValueError(f"publish recovery hash mismatch for command {command_id}")
        return restored, final, existing["fingerprint"], command_id

    private_path.parent.mkdir(parents=True, exist_ok=True)
    round_id, input_hash, method_revision = _round_binding(research)
    if kind_name == "research_record":
        build_research_record_pack(research, private_path)
        export_kind = ExportKind.RESEARCH_RECORD
        failed_checks = eligibility.failed_checks
    else:
        if not research.versions or not research.versions[-1].rounds:
            raise ValueError("strategy pack requires a completed round")
        attempt = research.versions[-1].rounds[-1].accepted_attempt
        if attempt.data_snapshot_path is None:
            raise ValueError("strategy pack requires a frozen data snapshot")
        snapshot = pd.read_csv(attempt.data_snapshot_path, index_col="date", parse_dates=True)
        prices = snapshot.drop(columns=["__benchmark__"], errors="ignore")
        benchmark = snapshot["__benchmark__"] if "__benchmark__" in snapshot.columns else None
        build_strategy_pack(
            research,
            MeanReversionStrategy(attempt.spec),
            MarketPanel(prices, now, benchmark),
            private_path,
        )
        export_kind = ExportKind.STRATEGY_PACK
        failed_checks = ()
    override = export_recheck_failures()
    recheck = strategy_pack_eligibility(research)
    if override is not None and kind_name != "research_record":
        recheck = ExportEligibility(False, override, ("injected recheck failure",))
    if kind_name != "research_record" and not recheck.eligible:
        _refuse(store, research, recheck, now)
    fingerprint = _sha256(private_path)
    record = ExportRecord(
        command_id,
        export_kind,
        str(final_path),
        research.current_version_number,
        now,
        failed_checks,
        False,
        round_id=round_id,
        input_hash=input_hash or None,
        method_revision=method_revision or None,
        fingerprint=fingerprint,
        command_id=command_id,
    )
    store.insert_publish_authorization(
        research_id=research.research_id,
        command_id=command_id,
        kind=export_kind.value,
        fingerprint=fingerprint,
        snapshot_hash=_snapshot_hash(research, kind_name, round_id),
        private_path=str(private_path),
        final_path=str(final_path),
        receipt_json=_record_json(record),
        created_at=now.isoformat(),
    )
    if export_crash_after_authorize():
        raise RuntimeError("injected crash after publish authorization")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(private_path, final_path)
    if not _hash_matches(final_path, fingerprint):
        raise ValueError(f"publish recovery hash mismatch for command {command_id}")
    updated = replace(
        research,
        exports=research.exports + (record,),
        updated_at=now,
    )
    return updated, final_path, fingerprint, command_id
