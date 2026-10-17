"""Fresh, server-owned Issue #90 authority preparation for a native Reject card.

The host pause hook is the only caller. The pipe contains authenticated server
identity and the winning paused generation; target, account, profile, cost and
expiry policy come from private runtime binding plus fixed source policy.
Preparation performs provider reads only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Callable

from awsops.application.s3_canary_approval import CanaryApprovalApplication
from awsops.domain.models import canonical_digest, require_text
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding, REGION
from awsops.runtime.read_probe import load_config

TOOL = "approve_s3_canary_once"
PREPARATION_TTL_SECONDS = 300
LIFECYCLE_TTL_SECONDS = 900
SPEND_LIMIT_MICROUSD = 1_000_000
EXPECTED_REQUEST_COST_MICROUSD = 540
CLEANUP_RESERVE_MICROUSD = SPEND_LIMIT_MICROUSD - EXPECTED_REQUEST_COST_MICROUSD
BUCKET = re.compile(r"awsops-dev-issue90-s3-canary-[a-z0-9]{12}")


def _private_regular(path: Path, *, max_bytes: int) -> None:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("PRIVATE_RUNTIME_FILE_REQUIRED")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes
            or stat.S_IMODE(info.st_mode) & 0o077
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
        raise ValueError("PRIVATE_RUNTIME_FILE_REQUIRED")


def _private_ledger_parent(path: Path) -> None:
    if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
        raise ValueError("PRIVATE_LEDGER_DIRECTORY_REQUIRED")
    parent = path.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) & 0o077
            or (hasattr(os, "getuid") and parent.st_uid != os.getuid())):
        raise ValueError("PRIVATE_LEDGER_DIRECTORY_REQUIRED")
    if path.exists() or path.is_symlink():
        _private_regular(path, max_bytes=16 * 1024 * 1024)


def _verify_source_revision(path: Path, expected: str) -> None:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("SOURCE_REVISION_FILE_REQUIRED")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size > 64
            or stat.S_IMODE(info.st_mode) != 0o644
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
        raise ValueError("SOURCE_REVISION_FILE_REQUIRED")
    value = path.read_text(encoding="ascii")
    if value != expected + "\n":
        raise ValueError("SOURCE_REVISION_DRIFT")


def _message(value: dict, *, now: int) -> tuple[dict, int]:
    fields = {"version", "operation", "binding", "pause_expires_at"}
    if type(value) is not dict or set(value) != fields or type(value["version"]) is not int or value["version"] != 1 or value["operation"] != "prepare_native_canary":
        raise ValueError("INVALID_CANARY_PREPARATION_MESSAGE")
    binding = value["binding"]
    expected = {"principal_id", "tenant_id", "conversation_id", "action_id",
                "generation_id", "tool_call_id", "tool"}
    if type(binding) is not dict or set(binding) != expected or binding["tool"] != TOOL:
        raise ValueError("INVALID_CANARY_PREPARATION_BINDING")
    for key in expected - {"tool"}:
        require_text(binding[key], r"[A-Za-z0-9_.:-]{1,128}", "native identity")
    if type(value["pause_expires_at"]) is not int or not now < value["pause_expires_at"] <= now + PREPARATION_TTL_SECONDS:
        raise ValueError("INVALID_CANARY_PAUSE_EXPIRY")
    return binding, value["pause_expires_at"]


def prepare_native_canary(message: dict, *, database: Path, binding_file: Path,
                          read_config: Path, source_revision: str, source_version: str,
                          source_revision_file: Path | None = None,
                          session_factory: Callable | None = None,
                          provider_factory: Callable | None = None,
                          clock: Callable[[], float] = time.time) -> dict:
    """Read the fixed target afresh, then persist its owner/job-bound authority."""
    now = int(clock())
    native, pause_expiry = _message(message, now=now)
    require_text(source_revision, r"[a-f0-9]{40}", "source revision")
    require_text(source_version, r"v[0-9]+\.[0-9]+\.[0-9]+-mock", "source version")
    if source_revision_file is None:
        source_revision_file = Path(__file__).resolve().parents[3] / "SOURCE_REVISION"
    _verify_source_revision(source_revision_file, source_revision)
    _private_regular(binding_file, max_bytes=4096)
    _private_regular(read_config, max_bytes=8192)
    _private_ledger_parent(database)
    private = json.loads(binding_file.read_text(encoding="utf-8"))
    if type(private) is not dict or set(private) != {"account_id", "bucket"}:
        raise ValueError("INVALID_PRIVATE_CANARY_BINDING")
    if BUCKET.fullmatch(private["bucket"]) is None:
        raise ValueError("UNAPPROVED_CANARY_TARGET")
    binding = CanaryBinding(private["account_id"], private["bucket"])
    settings, _accounts = load_config(read_config)
    if (settings["profile"] != "amit" or settings["region"] != REGION
            or settings["source_account_id"] != binding.account_id):
        raise ValueError("UNAPPROVED_LAB_BINDING")
    ttl = min(PREPARATION_TTL_SECONDS, pause_expiry - now)
    principal = canonical_digest({"principal_id": native["principal_id"],
                                  "tenant_id": native["tenant_id"]})

    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    if provider_factory is None:
        from awsops.aws.boto3_s3_canary import Boto3CanaryProvider
        provider_factory = Boto3CanaryProvider
    session = session_factory(profile_name=settings["profile"], region_name=REGION)
    provider = provider_factory(session, binding, database)
    adapter = CanaryAdapter(database, binding, provider, source_revision=source_revision,
                            source_version=source_version, clock=clock)
    application = CanaryApprovalApplication(
        database, binding, source_revision=source_revision, source_version=source_version,
        adapter_factory=lambda: adapter, mode="APPROVED_LAB_WRITE", verifier=None, clock=clock)
    batch = application.prepare(
        adapter, principal, now=now,
        estimated_incremental_cost_microusd=EXPECTED_REQUEST_COST_MICROUSD,
        cleanup_reserve_microusd=CLEANUP_RESERVE_MICROUSD,
        incremental_cost_limit_microusd=SPEND_LIMIT_MICROUSD,
        cleanup_expires_at=now + LIFECYCLE_TTL_SECONDS)
    authority, _ = application._load_authority(batch["record"]["batchId"])
    if (authority.source_revision != source_revision
            or authority.principal_binding_digest != principal
            or authority.decision_expires_at > pause_expiry
            or authority.decision_expires_at <= now):
        raise ValueError("CANARY_AUTHORITY_BINDING_FAILURE")
    return {"version": 1, "ok": True, "operation": "prepare_native_canary",
            "dispatch_allowed": False, "control": "s3_canary",
            "batch_id": authority.batch_id, "scope_digest": authority.scope_digest,
            "authority_digest": authority.digest, "source_revision": source_revision,
            "expires_at": authority.decision_expires_at,
            "binding_digest": canonical_digest({
                "binding_digest": canonical_digest(native), "authority_digest": authority.digest})}
