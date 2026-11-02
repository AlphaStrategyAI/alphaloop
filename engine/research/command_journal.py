"""Idempotent command receipts, research revisions, and remote-call claims.

A write looks up the receipt for ``(research_id, command_id)`` before it checks
``expected_revision``. The same id and payload returns the original receipt.
The same id with a different payload is rejected. A stale revision does not
apply, and the caller must submit again with a new id after the user confirms.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from engine.research.models import Research
from engine.research.store import ConcurrentWrite, SQLiteStore
from engine.research.user_errors import UserFacingError

COMMAND_ENVELOPE_REQUIRED = "COMMAND_ENVELOPE_REQUIRED"
COMMAND_PAYLOAD_CONFLICT = "COMMAND_PAYLOAD_CONFLICT"
REVISION_CONFLICT = "REVISION_CONFLICT"
REMOTE_UNKNOWN_NEEDS_AUTH = "REMOTE_UNKNOWN_NEEDS_AUTH"
NEW_PROPOSAL_REQUIRES_CURRENT_CLIENT = "NEW_PROPOSAL_REQUIRES_CURRENT_CLIENT"
CREATE_SOURCE_CONFLICT = "CREATE_SOURCE_CONFLICT"
PROPOSAL_NOT_CURRENT = "PROPOSAL_NOT_CURRENT"

_APPROVAL_DECISIONS = frozenset(
    {"approve_new_version", "accept_lower_floor", "redefine_scope"}
)


def payload_hash(request: dict[str, Any]) -> str:
    """Normalized digest of the command. Locale does not change its meaning."""
    body = {key: value for key, value in request.items() if key != "locale"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def state_snapshot(state_json: str) -> str:
    return hashlib.sha256(state_json.encode("utf-8")).hexdigest()


def command_envelope(request: dict[str, Any]) -> dict[str, Any] | None:
    """Return the journal envelope, or None for a legacy write.

    Any new dialogue field (``reply_to``, ``command_id``, ``expected_revision``)
    requires both ``command_id`` and ``expected_revision``.
    """
    if request.get("type") == "create_draft":
        return None
    command_id = request.get("command_id")
    expected = request.get("expected_revision")
    reply_to = request.get("reply_to")
    if command_id is None and expected is None and reply_to is None:
        return None
    if not isinstance(command_id, str) or not command_id.strip():
        raise UserFacingError(
            COMMAND_ENVELOPE_REQUIRED,
            "这次写入需要命令编号和期望修订。",
        )
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise UserFacingError(
            COMMAND_ENVELOPE_REQUIRED,
            "这次写入需要命令编号和期望修订。",
        )
    return {
        "command_id": command_id,
        "expected_revision": expected,
        "reply_to": reply_to if isinstance(reply_to, str) and reply_to else None,
    }


@dataclass(frozen=True, slots=True)
class Receipt:
    research_id: str
    command_id: str
    payload_hash: str
    revision: int
    result_ref: str
    status: str
    bound_revision: int | None
    bound_version: int | None
    bound_snapshot: str | None
    budget_reserved: int
    operation_key: str | None


@dataclass(frozen=True, slots=True)
class Claim:
    fresh: bool
    receipt: Receipt


def _row_receipt(row: tuple[Any, ...]) -> Receipt:
    return Receipt(
        research_id=str(row[0]),
        command_id=str(row[1]),
        payload_hash=str(row[2]),
        revision=int(row[3]),
        result_ref=str(row[4]),
        status=str(row[5]),
        bound_revision=None if row[6] is None else int(row[6]),
        bound_version=None if row[7] is None else int(row[7]),
        bound_snapshot=None if row[8] is None else str(row[8]),
        budget_reserved=int(row[9]),
        operation_key=None if row[10] is None else str(row[10]),
    )


_RECEIPT_COLUMNS = """
    research_id, command_id, payload_hash, revision, result_ref, status,
    bound_revision, bound_version, bound_snapshot, budget_reserved, operation_key
"""


class CommandJournal:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def prepare(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Replay, pending, or reject before a write. None means the write may run."""
        if request.get("type") == "create_draft":
            return None
        envelope = command_envelope(request)
        if envelope is None:
            self.assert_approval_allowed(str(request.get("research_id") or ""), request)
            return None
        research_id = str(request.get("research_id") or "")
        self.assert_approval_allowed(research_id, request)
        receipt = self._receipt(research_id, envelope["command_id"])
        if receipt is None:
            self._assert_reply(research_id, envelope.get("reply_to"))
            if (
                request.get("type") == "confirm_run"
                and not request.get("authorize_rebill")
                and self.has_unknown(research_id)
            ):
                self._trip_resend(research_id)
                raise self._unknown_error(research_id)
            return None
        if receipt.payload_hash != payload_hash(request):
            raise self._payload_conflict()
        if receipt.status == "committed":
            return self._replay(receipt)
        if receipt.status == "pending":
            return self._pending(receipt)
        if receipt.status == "unknown":
            self._trip_resend(str(envelope["command_id"]))
            raise self._unknown_error(research_id)
        if receipt.status == "revision_conflict":
            raise self._revision_conflict(research_id, envelope["command_id"])
        raise self._payload_conflict()

    def assert_approval_allowed(self, research_id: str, request: dict[str, Any]) -> None:
        """Old clients keep their buttons, but cannot approve a new-style proposal."""
        if not research_id or not self._is_approval(request):
            return
        proposal_id = self.open_proposal_id(research_id)
        if proposal_id is None:
            return
        envelope = None
        try:
            envelope = command_envelope(request)
        except UserFacingError:
            envelope = None
        if envelope is not None and request.get("reply_to") == proposal_id:
            return
        raise UserFacingError(
            NEW_PROPOSAL_REQUIRES_CURRENT_CLIENT,
            "这条新式提议需要当前版本的桌面才能批准。",
        )

    def create_research(self, request: dict[str, Any], research: Research) -> dict[str, Any]:
        research_id = str(request.get("research_id") or "")
        command_id = str(request.get("command_id") or "")
        if not research_id or not command_id:
            raise UserFacingError(
                COMMAND_ENVELOPE_REQUIRED,
                "这次写入需要命令编号和期望修订。",
            )
        digest = payload_hash(request)
        from engine.research.removal import forget_research_removed

        with self.store.connection:
            existing = self._receipt_locked(research_id, command_id)
            if existing is not None:
                if existing.payload_hash != digest:
                    raise self._payload_conflict()
                return self._replay(existing)
            head = self.store.research_head(research_id)
            if head is not None:
                create_command_id = head[4]
                if create_command_id == command_id:
                    response = {
                        "research_id": research_id,
                        "revision": head[0],
                        "command_id": command_id,
                        "ok": True,
                    }
                    self._insert_receipt(
                        research_id=research_id,
                        command_id=command_id,
                        digest=digest,
                        revision=head[0],
                        result=response,
                        status="committed",
                        budget_reserved=0,
                        operation_key=None,
                        bound_revision=0,
                        bound_version=None,
                        bound_snapshot=None,
                        created_at=research.updated_at.isoformat(),
                    )
                    return response
                raise UserFacingError(
                    CREATE_SOURCE_CONFLICT,
                    "该研究已存在，且与这条创建命令不是同一次操作。",
                )
            forget_research_removed(research_id)
            self.store.connection.execute(
                """
                INSERT INTO researches(
                    research_id, state_json, updated_at, status, revision, last_seq,
                    create_command_id
                ) VALUES(?,?,?,?,0,1,?)
                """,
                (
                    research.research_id,
                    self.store._encode(research),
                    research.updated_at.isoformat(),
                    research.status.value,
                    command_id,
                ),
            )
            self.store.connection.execute(
                """
                INSERT INTO research_event(
                    research_id, seq, version, kind, refs_json, created_at
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    research.research_id,
                    1,
                    None,
                    "create_draft",
                    json.dumps({"command_id": command_id}, sort_keys=True, separators=(",", ":")),
                    research.updated_at.isoformat(),
                ),
            )
            response = {
                "research_id": research.research_id,
                "revision": 0,
                "command_id": command_id,
                "ok": True,
            }
            self._insert_receipt(
                research_id=research.research_id,
                command_id=command_id,
                digest=digest,
                revision=0,
                result=response,
                status="committed",
                budget_reserved=0,
                operation_key=None,
                bound_revision=None,
                bound_version=None,
                bound_snapshot=None,
                created_at=research.updated_at.isoformat(),
            )
            return response

    def claim_remote(
        self,
        request: dict[str, Any],
        *,
        operation_key: str,
        budget_reserved: int,
        bound_revision: int,
        bound_version: int | None,
        bound_snapshot: str,
        now: datetime,
    ) -> Claim:
        envelope = command_envelope(request)
        if envelope is None:
            raise UserFacingError(
                COMMAND_ENVELOPE_REQUIRED,
                "这次写入需要命令编号和期望修订。",
            )
        research_id = str(request["research_id"])
        command_id = envelope["command_id"]
        digest = payload_hash(request)
        with self.store.connection:
            existing = self._receipt_locked(research_id, command_id)
            if existing is not None:
                if existing.payload_hash != digest:
                    raise self._payload_conflict()
                return Claim(False, existing)
            self._insert_receipt(
                research_id=research_id,
                command_id=command_id,
                digest=digest,
                revision=bound_revision,
                result={"status": "pending", "research_id": research_id, "command_id": command_id},
                status="pending",
                budget_reserved=budget_reserved,
                operation_key=operation_key,
                bound_revision=bound_revision,
                bound_version=bound_version,
                bound_snapshot=bound_snapshot,
                created_at=now.isoformat(),
            )
            stored = self._receipt_locked(research_id, command_id)
            if stored is None:
                raise ConcurrentWrite(research_id)
            return Claim(True, stored)

    def commit(
        self,
        request: dict[str, Any],
        before: Research,
        after: Research,
        event_kind: str,
        response: dict[str, Any],
        *,
        refs: dict[str, Any] | None = None,
        bound_snapshot: str | None = None,
        bound_version: int | None = None,
        keep_budget_on_conflict: bool = False,
        failure: UserFacingError | None = None,
    ) -> dict[str, Any]:
        """CAS the research, append one event, and write the receipt in one transaction."""
        envelope = command_envelope(request)
        if envelope is None:
            raise UserFacingError(
                COMMAND_ENVELOPE_REQUIRED,
                "这次写入需要命令编号和期望修订。",
            )
        research_id = before.research_id
        command_id = envelope["command_id"]
        expected_revision = int(envelope["expected_revision"])
        digest = payload_hash(request)
        conflict_revision: int | None = None
        replay: dict[str, Any] | None = None
        pending: dict[str, Any] | None = None
        with self.store.connection:
            existing = self._receipt_locked(research_id, command_id)
            if existing is not None and existing.payload_hash != digest:
                raise self._payload_conflict()
            if existing is not None and existing.status == "committed":
                replay = self._replay(existing)
            elif existing is not None and existing.status == "unknown":
                raise self._unknown_error(research_id)
            elif existing is not None and existing.status == "revision_conflict":
                conflict_revision = self.store.revision_of(research_id)
            elif existing is not None and existing.status == "pending" and failure is None and bound_snapshot is None:
                pending = self._pending(existing)
            else:
                head = self.store.research_head(research_id)
                if head is None:
                    raise KeyError(research_id)
                revision, _seq, updated_at, state_json, _create_command = head
                snapshot = state_snapshot(state_json)
                version = _version_of(state_json)
                mismatched = revision != expected_revision or updated_at != before.updated_at.isoformat()
                if bound_snapshot is not None and (
                    snapshot != bound_snapshot or version != bound_version or revision != expected_revision
                ):
                    mismatched = True
                if mismatched:
                    self._mark_conflict(
                        existing,
                        request,
                        live_revision=revision,
                        keep_budget=keep_budget_on_conflict,
                        now=after.updated_at,
                    )
                    conflict_revision = revision
                else:
                    try:
                        new_revision = self.store.cas_research_and_event(
                            after,
                            expected_updated_at=updated_at,
                            expected_revision=revision,
                            kind=event_kind,
                            refs=refs or {},
                        )
                    except ConcurrentWrite:
                        live = self.store.revision_of(research_id)
                        self._mark_conflict(
                            existing,
                            request,
                            live_revision=live,
                            keep_budget=keep_budget_on_conflict,
                            now=after.updated_at,
                        )
                        conflict_revision = live
                    else:
                        if failure is None:
                            body = dict(response)
                            body["research_id"] = after.research_id
                            body["status"] = after.status.value
                            body["revision"] = new_revision
                            body["command_id"] = command_id
                            body["ok"] = True
                            if after.current_version_number is not None:
                                body["version"] = after.current_version_number
                            self._upsert_committed(existing, request, new_revision, body, after.updated_at)
                            replay = body
                        else:
                            body = {
                                "ok": False,
                                "code": failure.code,
                                "error": failure.message,
                                "params": dict(failure.params),
                                "research_id": research_id,
                                "command_id": command_id,
                                "revision": new_revision,
                            }
                            self._upsert_committed(
                                existing,
                                request,
                                new_revision,
                                body,
                                after.updated_at,
                                budget_reserved=1 if keep_budget_on_conflict else 0,
                            )
                            replay = body
        if conflict_revision is not None:
            raise self._revision_conflict(research_id, command_id)
        if pending is not None:
            return pending
        if replay is None:
            raise ConcurrentWrite(research_id)
        if failure is not None and replay.get("ok") is False and replay.get("replayed") is not True:
            raise failure
        return replay

    def record_remote_failure(
        self,
        request: dict[str, Any],
        error: UserFacingError,
        *,
        keep_budget: bool,
        now: datetime,
    ) -> None:
        """The remote call finished with a known error and did not change research state."""
        envelope = command_envelope(request)
        if envelope is None:
            raise error
        research_id = str(request["research_id"])
        body = {
            "ok": False,
            "code": error.code,
            "error": error.message,
            "params": dict(error.params),
            "research_id": research_id,
            "command_id": envelope["command_id"],
            "revision": self.store.revision_of(research_id),
        }
        with self.store.connection:
            existing = self._receipt_locked(research_id, envelope["command_id"])
            self._upsert_committed(
                existing,
                request,
                body["revision"],
                body,
                now,
                budget_reserved=1 if keep_budget else 0,
            )

    def record_revision_conflict(self, request: dict[str, Any], *, now: datetime) -> None:
        research_id = str(request["research_id"])
        live = self.store.revision_of(research_id)
        with self.store.connection:
            existing = self._receipt_locked(research_id, str(request["command_id"]))
            if existing is not None and existing.payload_hash != payload_hash(request):
                raise self._payload_conflict()
            if existing is not None and existing.status == "committed":
                return
            self._mark_conflict(existing, request, live_revision=live, keep_budget=False, now=now)

    def record_open_proposal(self, research_id: str, proposal_id: str, now: datetime) -> int:
        research = self.store.load(research_id)
        updated = replace_updated(research, now)
        return self.store.save_with_event(
            updated,
            research.updated_at,
            "proposal",
            {"proposal_id": proposal_id, "status": "open", "style": "new"},
        )

    def open_proposal_id(self, research_id: str) -> str | None:
        row = self.store.connection.execute(
            """
            SELECT refs_json FROM research_event
             WHERE research_id=? AND kind='proposal'
             ORDER BY seq DESC LIMIT 1
            """,
            (research_id,),
        ).fetchone()
        if row is None:
            return None
        refs = json.loads(row[0])
        if not isinstance(refs, dict) or refs.get("status") != "open":
            return None
        proposal_id = refs.get("proposal_id")
        return str(proposal_id) if proposal_id else None

    def has_unknown(self, research_id: str) -> bool:
        row = self.store.connection.execute(
            """
            SELECT 1 FROM command_receipt
             WHERE research_id=? AND status='unknown' AND budget_reserved>0
             LIMIT 1
            """,
            (research_id,),
        ).fetchone()
        return row is not None

    def reserved_budget(self, research_id: str) -> int:
        row = self.store.connection.execute(
            "SELECT COALESCE(SUM(budget_reserved), 0) FROM command_receipt WHERE research_id=?",
            (research_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def _assert_reply(self, research_id: str, reply_to: str | None) -> None:
        if not reply_to:
            return
        open_id = self.open_proposal_id(research_id)
        if open_id is not None:
            if open_id != reply_to:
                raise UserFacingError(
                    PROPOSAL_NOT_CURRENT,
                    "这条回复没有指向当前提议。",
                )
            return
        research = self.store.load(research_id)
        active = research.active_proposal
        active_id = active.proposal_id if active is not None else None
        if active_id != reply_to:
            raise UserFacingError(
                PROPOSAL_NOT_CURRENT,
                "这条回复没有指向当前提议。",
            )

    def _receipt(self, research_id: str, command_id: str) -> Receipt | None:
        row = self.store.connection.execute(
            f"SELECT {_RECEIPT_COLUMNS} FROM command_receipt WHERE research_id=? AND command_id=?",
            (research_id, command_id),
        ).fetchone()
        return None if row is None else _row_receipt(tuple(row))

    def _receipt_locked(self, research_id: str, command_id: str) -> Receipt | None:
        return self._receipt(research_id, command_id)

    def _insert_receipt(
        self,
        *,
        research_id: str,
        command_id: str,
        digest: str,
        revision: int,
        result: dict[str, Any],
        status: str,
        budget_reserved: int,
        operation_key: str | None,
        bound_revision: int | None,
        bound_version: int | None,
        bound_snapshot: str | None,
        created_at: str,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO command_receipt(
                research_id, command_id, payload_hash, revision, result_ref, status,
                bound_revision, bound_version, bound_snapshot, budget_reserved,
                operation_key, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                research_id,
                command_id,
                digest,
                revision,
                json.dumps(result, sort_keys=True, separators=(",", ":")),
                status,
                bound_revision,
                bound_version,
                bound_snapshot,
                budget_reserved,
                operation_key,
                created_at,
            ),
        )

    def _mark_conflict(
        self,
        existing: Receipt | None,
        request: dict[str, Any],
        *,
        live_revision: int,
        keep_budget: bool,
        now: datetime,
    ) -> None:
        research_id = str(request["research_id"])
        command_id = str(request["command_id"])
        body = {
            "ok": False,
            "code": REVISION_CONFLICT,
            "research_id": research_id,
            "command_id": command_id,
            "revision": live_revision,
        }
        budget = existing.budget_reserved if existing is not None and keep_budget else 0
        if existing is None:
            self._insert_receipt(
                research_id=research_id,
                command_id=command_id,
                digest=payload_hash(request),
                revision=live_revision,
                result=body,
                status="revision_conflict",
                budget_reserved=budget,
                operation_key=None,
                bound_revision=request.get("expected_revision") if isinstance(request.get("expected_revision"), int) else None,
                bound_version=None,
                bound_snapshot=None,
                created_at=now.isoformat(),
            )
            return
        self.store.connection.execute(
            """
            UPDATE command_receipt
               SET status='revision_conflict', revision=?, result_ref=?, budget_reserved=?
             WHERE research_id=? AND command_id=?
            """,
            (
                live_revision,
                json.dumps(body, sort_keys=True, separators=(",", ":")),
                budget,
                research_id,
                command_id,
            ),
        )

    def _upsert_committed(
        self,
        existing: Receipt | None,
        request: dict[str, Any],
        revision: int,
        body: dict[str, Any],
        now: datetime,
        *,
        budget_reserved: int | None = None,
    ) -> None:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
        research_id = str(request["research_id"])
        command_id = str(request["command_id"])
        if existing is None:
            self._insert_receipt(
                research_id=research_id,
                command_id=command_id,
                digest=payload_hash(request),
                revision=revision,
                result=body,
                status="committed",
                budget_reserved=0 if budget_reserved is None else budget_reserved,
                operation_key=None,
                bound_revision=request.get("expected_revision") if isinstance(request.get("expected_revision"), int) else None,
                bound_version=None,
                bound_snapshot=None,
                created_at=now.isoformat(),
            )
            return
        budget = existing.budget_reserved if budget_reserved is None else budget_reserved
        self.store.connection.execute(
            """
            UPDATE command_receipt
               SET status='committed', revision=?, result_ref=?, budget_reserved=?
             WHERE research_id=? AND command_id=?
            """,
            (revision, encoded, budget, research_id, command_id),
        )

    def _replay(self, receipt: Receipt) -> dict[str, Any]:
        payload = json.loads(receipt.result_ref)
        if not isinstance(payload, dict):
            payload = {}
        if payload.get("ok") is False and payload.get("code"):
            raise UserFacingError(
                str(payload["code"]),
                str(payload.get("error") or payload["code"]),
                params=payload.get("params") if isinstance(payload.get("params"), dict) else None,
            )
        body = dict(payload)
        body["replayed"] = True
        body["revision"] = receipt.revision
        body["command_id"] = receipt.command_id
        body["research_id"] = receipt.research_id
        return body

    def _pending(self, receipt: Receipt) -> dict[str, Any]:
        return {
            "research_id": receipt.research_id,
            "command_id": receipt.command_id,
            "status": "pending",
            "revision": receipt.bound_revision if receipt.bound_revision is not None else receipt.revision,
            "budget_reserved": receipt.budget_reserved,
            "ok": True,
        }

    def _payload_conflict(self) -> UserFacingError:
        return UserFacingError(
            COMMAND_PAYLOAD_CONFLICT,
            "同一命令编号不能改用另一份内容。请重新确认后再提交。",
        )

    def _revision_conflict(self, research_id: str, command_id: str) -> UserFacingError:
        revision = self.store.revision_of(research_id)
        return UserFacingError(
            REVISION_CONFLICT,
            f"研究已经更新，当前修订是 {revision}。请核对差异后再确认提交。",
            params={"revision": revision, "command_id": command_id, "research_id": research_id},
        )

    def _trip_resend(self, detail: str) -> None:
        from engine.research.dialogue_rollout import note_unauthorized_resend

        note_unauthorized_resend(self.store, detail)

    def _unknown_error(self, research_id: str) -> UserFacingError:
        return UserFacingError(
            REMOTE_UNKNOWN_NEEDS_AUTH,
            "上一次外发是否已经执行无法确认，已计入预留。未经再次授权不会重新发起。",
            params={"budget_reserved": self.reserved_budget(research_id)},
        )

    @staticmethod
    def _is_approval(request: dict[str, Any]) -> bool:
        kind = request.get("type")
        if kind == "confirm_run":
            return True
        return kind == "resolve_confirm" and request.get("decision") in _APPROVAL_DECISIONS


def replace_updated(research: Research, now: datetime) -> Research:
    from dataclasses import replace

    return replace(research, updated_at=now)


def _version_of(state_json: str) -> int | None:
    payload = json.loads(state_json)
    if not isinstance(payload, dict):
        return None
    version = payload.get("current_version_number")
    if version is None:
        return None
    return int(version)
