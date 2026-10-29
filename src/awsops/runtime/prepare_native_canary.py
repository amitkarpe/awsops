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
import sqlite3
import time
from typing import Callable

from awsops.approval.decisions import DecisionStore
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
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("PRIVATE_RUNTIME_FILE_REQUIRED") from None
    if not path.is_absolute() or resolved != path:
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


class _LedgerOnlyProvider:
    """Inert MOCK dependency used only by existing constructors to create schemas."""
    mode = "MOCK"

    def __getattr__(self, _name):
        raise ValueError("LEDGER_INITIALIZATION_ONLY")


_APPLICATION_TABLES = {
    "canaries": {"batch_id", "payload", "principal", "binding", "decision", "result"},
    "operations": {"batch_id", "step", "state"},
    "application_authority": {"batch_id", "authority_json", "authority_digest", "principal_digest",
                              "packet_digest", "assurance", "verifier_id", "choice", "verified_at",
                              "cleanup_status"},
    "native_owner_decisions": {"batch_id", "record_json", "record_hash"},
}


def _existing_application_tables(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.exists():
        return {}
    _private_regular(path, max_bytes=16 * 1024 * 1024)
    if path.stat().st_size == 0:
        return {}
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            names = [row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            if any(name not in _APPLICATION_TABLES for name in names):
                raise ValueError("APPLICATION_LEDGER_SCHEMA_UNSUPPORTED")
            tables = {name: tuple(row[1] for row in db.execute(f'PRAGMA table_info("{name}")'))
                      for name in names}
    except sqlite3.Error:
        raise ValueError("APPLICATION_LEDGER_SCHEMA_UNSUPPORTED") from None
    for name, columns in tables.items():
        if set(columns) != _APPLICATION_TABLES[name]:
            raise ValueError("APPLICATION_LEDGER_SCHEMA_UNSUPPORTED")
    return tables


def _provision_ledgers(native_database: Path | None, application_database: Path,
                       binding: CanaryBinding, *, source_revision: str,
                       source_version: str, clock: Callable[[], float]) -> None:
    """Use the existing stores/adapters to initialize only absent private schema."""
    _private_ledger_parent(application_database)
    before = _existing_application_tables(application_database)
    if native_database is not None:
        if native_database.resolve() == application_database.resolve():
            raise ValueError("LEDGER_PATH_COLLISION")
        _private_ledger_parent(native_database)
        DecisionStore(native_database, clock=clock)
    inert = _LedgerOnlyProvider()
    seed_adapter = CanaryAdapter(application_database, binding, inert,
                                 source_revision=source_revision,
                                 source_version=source_version, clock=clock)
    CanaryApprovalApplication(application_database, binding,
        source_revision=source_revision, source_version=source_version,
        adapter_factory=lambda: seed_adapter, mode="MOCK", verifier=None, clock=clock)
    after = _existing_application_tables(application_database)
    if not {"canaries", "operations", "application_authority"}.issubset(after):
        raise ValueError("APPLICATION_LEDGER_NOT_READY")
    if any(before.get(name) != after.get(name) for name in before):
        raise ValueError("APPLICATION_LEDGER_EXISTING_STATE_CHANGED")
    _private_regular(application_database, max_bytes=16 * 1024 * 1024)


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
                          native_database: Path | None = None,
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
    _provision_ledgers(native_database, database, binding,
                       source_revision=source_revision, source_version=source_version,
                       clock=clock)
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
        cleanup_expires_at=now + LIFECYCLE_TTL_SECONDS,
        decision_expires_at=pause_expiry)
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


def initialize_application_ledger(*, expected_native_sha256: str,
                                  expected_binding_sha256: str,
                                  source_revision: str,
                                  root: Path = Path('/opt/awsops-native-canary')) -> dict:
    """Explicit operator setup, never an owner decision or pause preparation.

    Only an absent application file may be initialized. Existing/partial files
    require reconciliation; neither native records nor application rows are
    replaced. The CLI fixes root; injection is for local deployment fixtures.
    """
    import hashlib

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    for value in (expected_native_sha256, expected_binding_sha256):
        require_text(value, r"[a-f0-9]{64}", "private input digest")
    require_text(source_revision, r"[a-f0-9]{40}", "source revision")
    if os.getuid() == 0 or not root.is_absolute() or root.resolve(strict=True) != root:
        raise ValueError("PRIVATE_RUNTIME_ROOT_REQUIRED")
    state = root / 'state'
    for directory in (root, state):
        st = directory.lstat()
        if (not stat.S_ISDIR(st.st_mode) or directory.is_symlink()
                or (st.st_uid, st.st_gid) != (os.getuid(), os.getgid())
                or stat.S_IMODE(st.st_mode) != 0o700):
            raise ValueError("PRIVATE_RUNTIME_ROOT_REQUIRED")
    native_file, read_file, binding_file = (state / n for n in
                                           ('native.json', 'read.json', 'binding.private.json'))
    for path, limit in ((native_file, 8192), (read_file, 8192), (binding_file, 4096)):
        _private_regular(path, max_bytes=limit)
    if digest(native_file) != expected_native_sha256 or digest(binding_file) != expected_binding_sha256:
        raise ValueError("INITIALIZATION_PRIVATE_BINDING_DRIFT")
    native = json.loads(native_file.read_text())
    fields = {'version','enabled','agent_id','python','source_root','database',
              'source_revision','application_database','application_binding','source_version'}
    if (type(native) is not dict or set(native) != fields
            or type(native['version']) is not int or native['version'] != 1
            or native['enabled'] is not True or native['python'] != '/usr/bin/python3'
            or native['source_root'] != str(root / 'awsops')
            or native['database'] not in {str(state / 'receipt.sqlite3'), str(state / 'native.sqlite')}
            or native['application_database'] != str(state / 'canary.sqlite')
            or native['application_binding'] != str(binding_file)
            or native['source_revision'] != source_revision):
        raise ValueError("INITIALIZATION_NATIVE_CONFIG_UNSUPPORTED")
    require_text(native['agent_id'], r"[A-Za-z0-9_.:-]{1,128}", "existing agent")
    require_text(native['source_version'], r"v[0-9]+\.[0-9]+\.[0-9]+-mock", "source version")
    _verify_source_revision(root / 'awsops/SOURCE_REVISION', source_revision)
    private = json.loads(binding_file.read_text())
    if (type(private) is not dict or set(private) != {'account_id', 'bucket'}
            or type(private['bucket']) is not str or BUCKET.fullmatch(private['bucket']) is None):
        raise ValueError("INVALID_PRIVATE_CANARY_BINDING")
    binding = CanaryBinding(private['account_id'], private['bucket'])
    settings, _ = load_config(read_file)
    if (settings['profile'] != 'amit' or settings['region'] != REGION
            or settings['source_account_id'] != binding.account_id):
        raise ValueError("UNAPPROVED_LAB_BINDING")
    application = state / 'canary.sqlite'
    native_database = Path(native['database'])
    _private_regular(native_database, max_bytes=16 * 1024 * 1024)
    if (stat.S_IMODE(native_database.stat().st_mode) != 0o600
            or native_database.stat().st_gid != os.getgid()):
        raise ValueError("PRIVATE_RUNTIME_FILE_REQUIRED")
    DecisionStore.validate_existing(native_database)  # Read-only; never initializes it.
    before = digest(native_database)
    for path in (application, *(Path(str(application) + s) for s in ('-journal','-wal','-shm'))):
        if path.exists() or path.is_symlink():
            raise ValueError("APPLICATION_LEDGER_ALREADY_EXISTS_RECONCILE")
    # Exclusive reservation prevents a concurrent initializer from adopting an
    # existing file. A later failure preserves this partial file for inspection.
    fd = os.open(application, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    finally:
        os.close(fd)
    _provision_ledgers(None, application, binding, source_revision=source_revision,
                       source_version=native['source_version'], clock=time.time)
    with sqlite3.connect(application.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        if any(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
               for table in ('canaries', 'operations', 'application_authority')):
            raise ValueError("INITIALIZATION_UNEXPECTED_RECORDS")
    if digest(native_database) != before:
        raise ValueError("INITIALIZATION_NATIVE_LEDGER_CHANGED")
    with application.open('rb') as stream:
        os.fsync(stream.fileno())
    fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'state': 'INITIALIZED_SCHEMA_ONLY', 'native_source_revision': source_revision,
            'initializer_sha256': digest(Path(__file__)),
            'native_ledger_sha256': before, 'application_ledger_sha256': digest(application),
            'authority_records': 0, 'decision_records': 0, 'dispatch_allowed': False}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Explicit absent application-ledger setup; no AWS or decisions.')
    parser.add_argument('--initialize-application-ledger', action='store_true')
    parser.add_argument('--expected-native-sha256', required=True)
    parser.add_argument('--expected-binding-sha256', required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args(argv)
    if not args.initialize_application_ledger:
        parser.error('requires --initialize-application-ledger')
    try:
        result = initialize_application_ledger(expected_native_sha256=args.expected_native_sha256,
            expected_binding_sha256=args.expected_binding_sha256, source_revision=args.source_revision)
    except Exception:
        print('{"state":"REFUSED","code":"APPLICATION_LEDGER_INITIALIZATION_REFUSED","dispatch_allowed":false}')
        return 2
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
