"""Private server-to-server pipe protocol; never register it as an MCP/HTTP tool.

The hosting server owns authentication, fresh preparation, paused-job identity
and the native single-winner claim. OS/server trust is required: JSON and
NativeBinding values do not establish that authority. No AWS or network calls.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from awsops.approval.decisions import DecisionStore, NativeBinding
from awsops.domain.freeze import FrozenScope
from awsops.domain.models import Finding
from awsops.runtime.native_decision import NativeDecisionAdapter

MAX_INPUT = 16384
_BINDING_FIELDS = {"principal_id", "tenant_id", "conversation_id", "action_id",
                   "generation_id", "tool_call_id", "tool"}
_SCOPE_FIELDS = {"version", "batch_id", "scope_hash", "finding", "issued_at",
                 "expires_at", "live_execution_authorized"}


def _keys(value: Any, expected: set[str]) -> None:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("INVALID_PIPE_MESSAGE")


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_KEY")
        result[key] = value
    return result


def _bad_constant(_value: str) -> None:
    raise ValueError("INVALID_JSON")


def _private_database(path: Path) -> None:
    # The runtime provisions a ledger separately. A lost/deleted ledger must
    # never silently initialize a replacement during a decision request.
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("UNSAFE_DATABASE_PATH")
    for current, directory in ((path.parent, True), (path, False)):
        info = current.lstat()
        correct_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not correct_type or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("PRIVATE_DATABASE_REQUIRED")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise ValueError("DATABASE_OWNER_MISMATCH")
    if path.stat().st_size == 0:
        raise ValueError("LEDGER_NOT_PROVISIONED")


def dispatch(store: DecisionStore, message: dict) -> dict:
    """Internal protocol only. Caller must supply authoritative server context."""
    if type(message) is not dict or message.get("version") != 1 or type(message["version"]) is not int:
        raise ValueError("INVALID_PIPE_VERSION")
    operation = message.get("operation")
    common = {"version", "operation", "binding"}
    fields = {"register": common | {"frozen"},
              "record": common | {"batch_id", "scope_hash", "decision"},
              "inspect": common | {"batch_id"}}
    if type(operation) is not str or operation not in fields:
        raise ValueError("UNSUPPORTED_OPERATION")
    _keys(message, fields[operation])
    _keys(message["binding"], _BINDING_FIELDS)
    binding = NativeBinding(**message["binding"])
    if operation == "register":
        raw = message["frozen"]
        _keys(raw, _SCOPE_FIELDS)
        frozen = FrozenScope(raw["batch_id"], raw["scope_hash"], Finding(**raw["finding"]),
                             raw["issued_at"], raw["expires_at"], raw["live_execution_authorized"])
        if frozen.public_dict() != raw:
            raise ValueError("INVALID_FROZEN_RECORD")
        event = store.register(frozen, binding)
        return {"version": 1, "ok": True, "operation": "register", "event_hash": event,
                "batch_id": frozen.batch_id, "scope_hash": frozen.scope_hash, "dispatch_allowed": False}
    if operation == "inspect":
        events = store.timeline(message["batch_id"], binding)
        # Audit read cannot mint a continuation, even after a lost ACK.
        return {"version": 1, "ok": True, "operation": "inspect", "dispatch_allowed": False,
                "events": [{"kind": event["kind"], "event_hash": event["event_hash"],
                            "outcome": event["payload"].get("outcome"),
                            "recorded_at": event["payload"]["recorded_at"]} for event in events]}
    result = NativeDecisionAdapter(store).after_native_claim(
        batch_id=message["batch_id"], scope_hash=message["scope_hash"], binding=binding, decision=message["decision"])
    return {"version": 1, "ok": True, "operation": "record", "dispatch_allowed": False,
            "receipt": result.receipt.public_dict(), "resume_value": result.resolution()}


def main(argv: list[str] | None = None) -> int:
    try:
        parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
        parser.add_argument("--database", type=Path, required=True)
        args = parser.parse_args(argv)
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if not raw or len(raw) > MAX_INPUT:
            raise ValueError("INVALID_INPUT_SIZE")
        message = json.loads(raw, object_pairs_hook=_object, parse_constant=_bad_constant)
        _private_database(args.database)
        result = dispatch(DecisionStore(args.database), message)
        output = json.dumps(result, separators=(",", ":"), allow_nan=False)
        if len(output.encode("utf-8")) > MAX_INPUT:
            raise ValueError("INVALID_OUTPUT_SIZE")
    except Exception:
        # No provider/private path/native identity or traceback crosses the pipe.
        print('{"version":1,"ok":false,"code":"RECEIPT_UNAVAILABLE","dispatch_allowed":false}')
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
