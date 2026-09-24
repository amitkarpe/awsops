"""Private, append-only native decision evidence. No executor or cloud client."""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from typing import Callable, Iterator

from awsops.domain.freeze import FrozenScope
from awsops.domain.models import Finding, canonical_digest, require_text

TOOL = "decide_s3_ssl_reject_only"
SCHEMA_VERSION = 1
_TABLE = """CREATE TABLE events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 batch_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('PREPARE_FROZEN','NATIVE_DECISION')),
 payload TEXT NOT NULL,
 prior_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL UNIQUE,
 UNIQUE(batch_id,kind))"""
_TRIGGERS = {
    "events_no_update": "CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'append-only ledger'); END",
    "events_no_delete": "CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'append-only ledger'); END",
}


class DecisionError(ValueError):
    """Safe contract errors; never include submitted identities or raw state."""


@dataclass(frozen=True, repr=False)
class NativeBinding:
    """Server-provided paused-action identity, NOT an authentication token."""
    principal_id: str
    tenant_id: str
    conversation_id: str
    action_id: str
    generation_id: str
    tool_call_id: str
    tool: str = TOOL

    def __post_init__(self) -> None:
        for value in asdict(self).values():
            require_text(value, r"[A-Za-z0-9_.:-]{1,128}", "native identity")
        if self.tool != TOOL:
            raise DecisionError("UNSUPPORTED_TOOL")

    def digest(self) -> str:
        return canonical_digest(asdict(self))


@dataclass(frozen=True)
class DecisionReceipt:
    batch_id: str
    scope_hash: str
    outcome: str
    event_hash: str
    recorded_at: int

    def __post_init__(self) -> None:
        require_text(self.batch_id, r"[a-f0-9]{32}", "receipt batch")
        require_text(self.scope_hash, r"[a-f0-9]{64}", "receipt scope")
        require_text(self.event_hash, r"[a-f0-9]{64}", "receipt hash")
        if self.outcome not in ("REJECTED", "APPROVE_BLOCKED") or type(self.recorded_at) is not int or self.recorded_at < 0:
            raise DecisionError("INVALID_RECEIPT")

    def public_dict(self) -> dict:
        return {"version": SCHEMA_VERSION, **asdict(self), "dispatch_allowed": False}


def _json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _scope(value: dict) -> FrozenScope:
    if set(value) != {"version", "batch_id", "scope_hash", "finding", "issued_at", "expires_at", "live_execution_authorized"}:
        raise DecisionError("INVALID_FROZEN_RECORD")
    frozen = FrozenScope(value["batch_id"], value["scope_hash"], Finding(**value["finding"]),
                         value["issued_at"], value["expires_at"], value["live_execution_authorized"])
    if frozen.public_dict() != value:
        raise DecisionError("INVALID_FROZEN_RECORD")
    return frozen


class DecisionStore:
    """One local database. The hosting server and filesystem are trusted.

    A native platform must authenticate/authorize the caller and win its own
    paused-job claim BEFORE invoking this contract. A hash is not authority.
    """
    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time):
        self.path = Path(path).absolute()
        self.clock = clock
        if not self.path.parent.is_dir():
            raise DecisionError("PRIVATE_PARENT_DIRECTORY_REQUIRED")
        if self.path.is_symlink():
            raise DecisionError("UNSAFE_DATABASE_PATH")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        self._check_file()
        with self._transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            objects = db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
            if version == 0 and not objects:
                db.execute(_TABLE)
                for ddl in _TRIGGERS.values():
                    db.execute(ddl)
                db.execute("PRAGMA user_version=1")
            self._verify(db)

    def _check_file(self) -> None:
        mode = self.path.lstat().st_mode
        if not stat.S_ISREG(mode) or (os.name == "posix" and stat.S_IMODE(mode) & 0o077):
            raise DecisionError("UNSAFE_DATABASE_FILE")

    def _connect(self) -> sqlite3.Connection:
        self._check_file()
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise DecisionError("UNSUPPORTED_JOURNAL_MODE")
            return db
        except BaseException:
            db.close()
            raise

    def _commit(self, db: sqlite3.Connection) -> None:
        db.commit()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                self._commit(db)
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _verify(db: sqlite3.Connection) -> list[dict]:
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise DecisionError("UNSUPPORTED_LEDGER_VERSION")
        schema = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','trigger') AND name NOT LIKE 'sqlite_%'"))
        if schema != {"events": _TABLE, **_TRIGGERS}:
            raise DecisionError("LEDGER_SCHEMA_DRIFT")
        events = []
        previous = "GENESIS"
        prepares = {}
        decisions = set()
        for expected, row in enumerate(db.execute("SELECT sequence,batch_id,kind,payload,prior_hash,event_hash FROM events ORDER BY sequence"), 1):
            number, batch, kind, raw, prior, digest = row
            payload = json.loads(raw)
            envelope = {"sequence": number, "batch_id": batch, "kind": kind, "payload": payload, "prior_hash": prior}
            if number != expected or prior != previous or _json(payload) != raw or canonical_digest(envelope) != digest:
                raise DecisionError("LEDGER_INTEGRITY_FAILURE")
            require_text(batch, r"[a-f0-9]{32}", "ledger batch")
            require_text(payload.get("binding_digest"), r"[a-f0-9]{64}", "binding digest")
            stamp = payload.get("recorded_at")
            if type(stamp) is not int or stamp < 0:
                raise DecisionError("INVALID_LEDGER_TIME")
            if kind == "PREPARE_FROZEN":
                if set(payload) != {"binding_digest", "frozen", "recorded_at"} or batch in prepares:
                    raise DecisionError("INVALID_PREPARE_EVENT")
                frozen = _scope(payload["frozen"])
                if frozen.batch_id != batch or not frozen.issued_at <= stamp < frozen.expires_at:
                    raise DecisionError("INVALID_PREPARE_EVENT")
                prepares[batch] = (payload, digest)
            elif kind == "NATIVE_DECISION":
                if set(payload) != {"binding_digest", "scope_hash", "decision", "outcome", "recorded_at", "prepare_event_hash", "dispatch_allowed"} or batch not in prepares or batch in decisions:
                    raise DecisionError("INVALID_DECISION_EVENT")
                prepared, prepare_hash = prepares[batch]
                expected_outcome = {"reject": "REJECTED", "approve": "APPROVE_BLOCKED"}.get(payload["decision"])
                frozen = prepared["frozen"]
                if (expected_outcome is None or payload["outcome"] != expected_outcome or payload["dispatch_allowed"] is not False
                        or payload["binding_digest"] != prepared["binding_digest"] or payload["scope_hash"] != frozen["scope_hash"]
                        or payload["prepare_event_hash"] != prepare_hash or not prepared["recorded_at"] <= stamp < frozen["expires_at"]):
                    raise DecisionError("INVALID_DECISION_EVENT")
                decisions.add(batch)
            else:
                raise DecisionError("INVALID_EVENT_KIND")
            events.append({**envelope, "event_hash": digest})
            previous = digest
        return events

    @staticmethod
    def _append(db: sqlite3.Connection, events: list[dict], batch: str, kind: str, payload: dict) -> str:
        sequence = len(events) + 1
        prior = events[-1]["event_hash"] if events else "GENESIS"
        digest = canonical_digest({"sequence": sequence, "batch_id": batch, "kind": kind, "payload": payload, "prior_hash": prior})
        db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (sequence, batch, kind, _json(payload), prior, digest))
        return digest

    @staticmethod
    def _binding(binding: NativeBinding) -> str:
        if type(binding) is not NativeBinding:
            raise DecisionError("INVALID_NATIVE_BINDING")
        return NativeBinding(**asdict(binding)).digest()

    def _now(self) -> int:
        value = self.clock()
        if type(value) not in (int, float) or value < 0:
            raise DecisionError("INVALID_SERVER_CLOCK")
        return int(value)

    def register(self, frozen: FrozenScope, binding: NativeBinding) -> str:
        """Trusted server only: freeze must come from provider-backed preparation."""
        if type(frozen) is not FrozenScope:
            raise DecisionError("INVALID_FROZEN_SCOPE")
        frozen = _scope(frozen.public_dict())
        binding_digest = self._binding(binding)
        with self._transaction() as db:
            events = self._verify(db)
            now = self._now()
            if not frozen.issued_at <= now < frozen.expires_at:
                raise DecisionError("PREPARATION_EXPIRED_OR_FUTURE")
            if any(e["batch_id"] == frozen.batch_id for e in events):
                raise DecisionError("PREPARATION_ALREADY_REGISTERED")
            result = self._append(db, events, frozen.batch_id, "PREPARE_FROZEN",
                                  {"frozen": frozen.public_dict(), "binding_digest": binding_digest, "recorded_at": now})
        return result

    def record(self, *, batch_id: str, scope_hash: str, binding: NativeBinding, decision: str) -> DecisionReceipt:
        require_text(batch_id, r"[a-f0-9]{32}", "batch id")
        require_text(scope_hash, r"[a-f0-9]{64}", "scope hash")
        if type(decision) is not str or decision not in ("reject", "approve"):
            raise DecisionError("UNSUPPORTED_DECISION")
        bound = self._binding(binding)
        with self._transaction() as db:
            events = self._verify(db)
            matching = [e for e in events if e["batch_id"] == batch_id]
            if not matching:
                raise DecisionError("PREPARATION_NOT_FOUND")
            prepared = matching[0]["payload"]
            frozen = prepared["frozen"]
            if prepared["binding_digest"] != bound or frozen["scope_hash"] != scope_hash:
                raise DecisionError("NATIVE_SCOPE_BINDING_MISMATCH")
            if len(matching) != 1:
                raise DecisionError("DECISION_ALREADY_RECORDED")
            now = self._now()
            if not prepared["recorded_at"] <= now < frozen["expires_at"]:
                raise DecisionError("PREPARATION_EXPIRED_OR_FUTURE")
            outcome = "REJECTED" if decision == "reject" else "APPROVE_BLOCKED"
            digest = self._append(db, events, batch_id, "NATIVE_DECISION", {
                "scope_hash": scope_hash, "binding_digest": bound, "decision": decision, "outcome": outcome,
                "recorded_at": now, "prepare_event_hash": matching[0]["event_hash"], "dispatch_allowed": False})
            receipt = DecisionReceipt(batch_id, scope_hash, outcome, digest, now)
        # _transaction must have committed before a receipt can escape.
        return receipt

    def timeline(self, batch_id: str, binding: NativeBinding) -> list[dict]:
        require_text(batch_id, r"[a-f0-9]{32}", "batch id")
        bound = self._binding(binding)
        with self._transaction() as db:
            events = [e for e in self._verify(db) if e["batch_id"] == batch_id]
            if not events or events[0]["payload"]["binding_digest"] != bound:
                raise DecisionError("NATIVE_SCOPE_BINDING_MISMATCH")
        return events
