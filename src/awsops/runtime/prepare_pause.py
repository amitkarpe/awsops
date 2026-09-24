"""Trusted native pause producer -> fresh provider preparation -> durable binding.

Not an MCP/HTTP method. Only the authenticated native server may launch this
process. The decision receipt process remains separate and has no AWS access.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import time
from typing import Callable

from awsops.approval.decisions import DecisionStore, NativeBinding, _scope
from awsops.domain.freeze import MAX_EVIDENCE_AGE, freeze_finding
from awsops.domain.models import Finding, require_text
from awsops.runtime.receipt_stdio import (
    MAX_INPUT, _BINDING_FIELDS, _bad_constant, _keys, _object, _private_database,
)
from awsops.runtime.s3_ssl_service import S3SslService


def _candidate(message: dict, now: int) -> tuple[NativeBinding, dict, int]:
    _keys(message, {"version", "operation", "binding", "candidate", "pause_expires_at"})
    if type(message["version"]) is not int or message["version"] != 1 or message["operation"] != "prepare_pause":
        raise ValueError("INVALID_PAUSE_MESSAGE")
    _keys(message["binding"], _BINDING_FIELDS)
    binding = NativeBinding(**message["binding"])
    value = message["candidate"]
    _keys(value, {"control", "account_alias", "resource_ref", "expected_evidence_digest"})
    if value["control"] != "s3_ssl":
        raise ValueError("UNSUPPORTED_CONTROL")
    require_text(value["account_alias"], r"lab-(dev|poc|qa|sec)", "alias")
    require_text(value["resource_ref"], r"bucket-ref-[a-f0-9]{20}", "resource reference")
    require_text(value["expected_evidence_digest"], r"[a-f0-9]{64}", "evidence digest")
    expires = message["pause_expires_at"]
    if type(expires) is not int or not now < expires <= now + 86400:
        raise ValueError("INVALID_PAUSE_EXPIRY")
    return binding, value, expires


def prepare_and_register(service: S3SslService, store: DecisionStore, message: dict,
                         *, clock: Callable[[], float] = time.time) -> dict:
    """Never accept caller evidence or a caller FrozenScope. Read it afresh."""
    binding, candidate, expiry = _candidate(message, int(clock()))
    prepared = service.prepare(alias=candidate["account_alias"], resource_ref=candidate["resource_ref"],
                               expected_evidence_digest=candidate["expected_evidence_digest"])
    now = int(clock())
    ttl = min(prepared.expires_at, expiry) - now
    if ttl < 1:
        raise ValueError("PAUSE_EXPIRED_DURING_READ")
    # Bind to the remaining native lifetime; never lengthen the provider freeze.
    frozen = freeze_finding(prepared.finding, now=now, ttl=ttl)
    event_hash = store.register(frozen, binding)
    # No readiness response escapes before the actual registration commit.
    return {"version": 1, "ok": True, "operation": "prepare_pause", "dispatch_allowed": False,
            "batch_id": frozen.batch_id, "scope_hash": frozen.scope_hash,
            "expires_at": frozen.expires_at, "event_hash": event_hash,
            "candidate": dict(candidate), "binding_digest": binding.digest()}


def _readback_message(message: dict) -> NativeBinding:
    _keys(message, {"version", "operation", "binding", "batch_id", "scope_hash"})
    if type(message["version"]) is not int or message["version"] != 1 or message["operation"] != "readback":
        raise ValueError("INVALID_READBACK_MESSAGE")
    _keys(message["binding"], _BINDING_FIELDS)
    require_text(message["batch_id"], r"[a-f0-9]{32}", "batch")
    require_text(message["scope_hash"], r"[a-f0-9]{64}", "scope")
    return NativeBinding(**message["binding"])


def readback_after_reject(service: S3SslService, store: DecisionStore, message: dict,
                          *, clock: Callable[[], float] = time.time) -> dict:
    """Audit comparison only: reopen a consumed receipt, never recreate a job."""
    binding = _readback_message(message)
    events = store.timeline(message["batch_id"], binding)
    if (len(events) != 2 or events[-1]["kind"] != "NATIVE_DECISION"
            or events[-1]["payload"]["outcome"] != "REJECTED"):
        raise ValueError("REJECT_RECEIPT_REQUIRED")
    frozen = _scope(events[0]["payload"]["frozen"])
    if frozen.scope_hash != message["scope_hash"]:
        raise ValueError("READBACK_SCOPE_MISMATCH")
    result = {"version": 1, "ok": True, "operation": "readback", "dispatch_allowed": False,
              "batch_id": frozen.batch_id, "scope_hash": frozen.scope_hash,
              "receipt_event_hash": events[-1]["event_hash"], "state": "UNAVAILABLE",
              "unchanged": False, "read_only": True, "observed_at": int(clock())}
    # Expiry denies a success claim, not access to previously bound audit evidence.
    if not events[-1]["payload"]["recorded_at"] <= int(clock()) < frozen.expires_at:
        return result
    try:
        report = service.status()
        if report["complete"] is not True or any(a.get("identity_verified") is not True or a.get("complete") is not True for a in report["accounts"]):
            return result
        rows = [r for r in report["findings"] if r["account_alias"] == frozen.finding.account_alias
                and r["resource_ref"] == frozen.finding.resource_ref]
        if len(rows) != 1:
            return result
        finding = Finding(**rows[0])
        now = int(clock())
        if now >= frozen.expires_at or not 0 <= now - finding.observed_at <= MAX_EVIDENCE_AGE:
            return result
    except Exception:
        return result  # Provider errors never become unchanged or raw public output.
    result.update(observed_at=now, state=finding.provider_status,
                  finding_evidence_digest=finding.evidence_digest,
                  unchanged=finding.provider_status == frozen.finding.provider_status
                  and finding.evidence_version == frozen.finding.evidence_version
                  and finding.evidence_digest == frozen.finding.evidence_digest)
    return result


def _private_config(path: Path) -> None:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("PRIVATE_CONFIG_REQUIRED")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("PRIVATE_CONFIG_REQUIRED")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise ValueError("PRIVATE_CONFIG_OWNER_MISMATCH")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
        parser.add_argument("--database", type=Path, required=True)
        parser.add_argument("--read-config", type=Path, required=True)
        args = parser.parse_args(argv)
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if not raw or len(raw) > MAX_INPUT:
            raise ValueError("INVALID_INPUT_SIZE")
        message = json.loads(raw, object_pairs_hook=_object, parse_constant=_bad_constant)
        if type(message) is not dict:
            raise ValueError("INVALID_PIPE_MESSAGE")
        operation = message.get("operation")
        if operation == "prepare_pause":
            _candidate(message, int(time.time()))
        elif operation == "readback":
            _readback_message(message)
        else:
            raise ValueError("UNSUPPORTED_OPERATION")
        _private_database(args.database)
        _private_config(args.read_config)
        from awsops.runtime.read_probe import load_config
        from awsops.aws.boto3_s3_ssl import assume_role_factory
        from awsops.aws.s3_ssl import REGION, collect
        import boto3
        config, bindings = load_config(args.read_config)
        source = boto3.Session(profile_name=config["profile"], region_name=REGION)
        factory = assume_role_factory(source, expected_source_account=config["source_account_id"])
        service = S3SslService(lambda: collect(bindings, factory))
        store = DecisionStore(args.database)
        handler = prepare_and_register if operation == "prepare_pause" else readback_after_reject
        result = handler(service, store, message)
        output = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(output.encode()) > MAX_INPUT:
            raise ValueError("OVERSIZED_RESPONSE")
    except Exception:
        print('{"version":1,"ok":false,"code":"PAUSE_PREPARATION_UNAVAILABLE","dispatch_allowed":false}')
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
