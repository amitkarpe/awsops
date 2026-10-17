"""Internal bridge from the pinned host's authenticated winning Reject.

The host gate owns req.user and the paused-job CAS. Its private child persists
the resulting immutable record; this module reads that record as the independent
owner verifier and delegates packet claim, decision and canonical receipt to
the existing application ledger. It does not enable Approve or a live provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import re

from awsops.application.s3_canary_approval import (
    CanaryApprovalApplication,
    FrozenCanaryAuthority,
    OwnerApprovalPacket,
    OwnerApprovalVerifier,
    VerifiedOwnerDecision,
)
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding
from awsops.domain.models import canonical_digest, require_text

_BATCH = re.compile(r"batch-canary-[a-f0-9]{32}")
_HEX64 = re.compile(r"[a-f0-9]{64}")
_CANARY_TOOL = "approve_s3_canary_once"


class NativeServerOwnerVerifier:
    """Verify the durable native decision record written by the pinned host seam."""
    def __init__(self, database, record_hash: str):
        self.database, self.record_hash = database, record_hash

    def verify(self, packet, authority, *, action: str, now: int) -> VerifiedOwnerDecision:
        if action not in ("DECISION", "AUDIT_READ") or packet.decision != "REJECT":
            raise ValueError("NATIVE_APPROVAL_NOT_AUTHORIZED")
        with closing(sqlite3.connect(self.database, timeout=2)) as db:
            row = db.execute("SELECT record_json,record_hash FROM native_owner_decisions WHERE batch_id=?",
                             (authority.batch_id,)).fetchone()
        if row is None or row[1] != self.record_hash or canonical_digest(json.loads(row[0])) != row[1]:
            raise ValueError("NATIVE_OWNER_RECORD_UNAVAILABLE")
        record = json.loads(row[0])
        identity_digest = canonical_digest({"principal_id": record["binding"]["principal_id"],
                                            "tenant_id": record["binding"]["tenant_id"]})
        if (record["authority_digest"] != authority.digest
                or record["scope_digest"] != authority.scope_digest
                or record["source_revision"] != authority.source_revision
                or record["decision"] != "reject"
                or identity_digest != authority.principal_binding_digest
                or record["expires_at"] != authority.decision_expires_at
                or record["decided_at"] > now
                or (action == "DECISION" and now >= record["expires_at"])
                or packet.authority_digest != authority.digest
                or packet.principal_binding_digest != authority.principal_binding_digest
                or packet.decision != "REJECT" or packet.proof != self.record_hash):
            raise ValueError("NATIVE_OWNER_RECORD_BINDING_MISMATCH")
        return VerifiedOwnerDecision(packet_digest=packet.digest, authority_digest=authority.digest,
                                     principal_binding_digest=authority.principal_binding_digest,
                                     decision="REJECT", assurance="OWNER_AUTHENTICATED",
                                     verifier_id="LIBRECHAT_NATIVE_CAS", verified_at=record["decided_at"])


def persist_native_owner_decision(database, record: dict, *, now: int) -> str:
    """Persist only the winning host decision for the independent verifier."""
    expected = {"version", "operation", "batch_id", "authority_digest", "scope_digest",
                "source_revision", "decision", "decided_at", "expires_at", "binding"}
    if (type(record) is not dict or set(record) != expected or record.get("version") != 1
            or type(record.get("version")) is not int or record.get("operation") != "native_canary_reject"):
        raise ValueError("INVALID_NATIVE_REJECT_RECORD")
    binding = record.get("binding")
    fields = {"principal_id", "tenant_id", "conversation_id", "action_id", "generation_id", "tool_call_id", "tool"}
    if type(binding) is not dict or set(binding) != fields or binding.get("tool") != _CANARY_TOOL:
        raise ValueError("INVALID_NATIVE_REJECT_BINDING")
    for key in fields - {"tool"}:
        require_text(binding[key], r"[A-Za-z0-9_.:-]{1,128}", "native identity")
    require_text(record["batch_id"], _BATCH.pattern, "canary batch")
    require_text(record["authority_digest"], _HEX64.pattern, "authority digest")
    require_text(record["scope_digest"], _HEX64.pattern, "scope digest")
    require_text(record["source_revision"], r"[a-f0-9]{40}", "source revision")
    if (record["decision"] != "reject" or type(record["decided_at"]) is not int
            or type(record["expires_at"]) is not int or type(now) is not int
            or record["decided_at"] > now or now >= record["expires_at"]):
        raise ValueError("NATIVE_REJECT_EXPIRED_OR_UNSUPPORTED")
    principal = canonical_digest({"principal_id": binding["principal_id"], "tenant_id": binding["tenant_id"]})
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"))
    record_hash = canonical_digest(record)
    with closing(sqlite3.connect(database, timeout=2, isolation_level=None)) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS native_owner_decisions (
                batch_id TEXT PRIMARY KEY, record_json TEXT NOT NULL, record_hash TEXT NOT NULL UNIQUE)""")
            row = db.execute("SELECT authority_json,authority_digest,principal_digest,packet_digest,choice "
                             "FROM application_authority WHERE batch_id=?", (record["batch_id"],)).fetchone()
            if row is None:
                raise ValueError("CANARY_AUTHORITY_NOT_FOUND")
            authority = json.loads(row[0])
            if (row[1] != record["authority_digest"] or canonical_digest(authority) != row[1]
                    or authority.get("scopeDigest") != record["scope_digest"]
                    or authority.get("sourceRevision") != record["source_revision"]
                    or row[2] != principal or authority.get("principalBindingDigest") != principal
                    or record["expires_at"] != authority.get("decisionExpiresAt")):
                raise ValueError("NATIVE_REJECT_AUTHORITY_MISMATCH")
            saved = db.execute("SELECT record_json,record_hash FROM native_owner_decisions WHERE batch_id=?",
                               (record["batch_id"],)).fetchone()
            if saved is None:
                if row[3] is not None or row[4] is not None:
                    raise ValueError("NATIVE_REJECT_ALREADY_CONSUMED")
                db.execute("INSERT INTO native_owner_decisions VALUES (?,?,?)",
                           (record["batch_id"], raw, record_hash))
            elif saved != (raw, record_hash):
                raise ValueError("NATIVE_OWNER_DECISION_ALREADY_CONSUMED")
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return record_hash


def apply_authenticated_native_reject(database, record: dict, binding: CanaryBinding, *,
                                      source_version: str, now: int) -> dict:
    """Run the trusted native Reject through the existing application ledger."""
    record_hash = persist_native_owner_decision(database, record, now=now)
    with closing(sqlite3.connect(database, timeout=2)) as db:
        row = db.execute("SELECT authority_json FROM application_authority WHERE batch_id=?",
                         (record["batch_id"],)).fetchone()
    if row is None:
        raise ValueError("CANARY_AUTHORITY_NOT_FOUND")
    authority = json.loads(row[0])
    with closing(sqlite3.connect(database, timeout=2)) as db:
        batch_row = db.execute("SELECT payload FROM canaries WHERE batch_id=?", (record["batch_id"],)).fetchone()
    if batch_row is None:
        raise ValueError("CANARY_AUTHORITY_NOT_FOUND")
    mode = json.loads(batch_row[0]).get("mode")
    if mode not in ("MOCK", "APPROVED_LAB_WRITE"):
        raise ValueError("UNAPPROVED_TARGET")
    principal = canonical_digest({"principal_id": record["binding"]["principal_id"],
                                  "tenant_id": record["binding"]["tenant_id"]})
    app = CanaryApprovalApplication(
        Path(database), binding, source_revision=record["source_revision"], source_version=source_version,
        adapter_factory=lambda: _reject_only_adapter(Path(database), binding, record["source_revision"], source_version, mode, now),
        mode=mode, verifier=NativeServerOwnerVerifier(database, record_hash),
        clock=lambda: now)
    frozen, _ = app._load_authority(record["batch_id"])
    if (frozen.digest != record["authority_digest"] or frozen.scope_digest != record["scope_digest"]
            or frozen.source_revision != record["source_revision"]
            or frozen.principal_binding_digest != principal):
        raise ValueError("NATIVE_REJECT_AUTHORITY_MISMATCH")
    callback = {**record, "operation": "native_canary_choice"}
    context = NativeCanaryDecision.from_host_callback(
        callback, frozen, received_at=record["decided_at"], decision_record_hash=record_hash)
    bridge = NativeCanaryApprovalAdapter(app, app.verifier)
    result = bridge.decide(context)
    receipts = bridge.receipt(context)
    return {"version": 1, "ok": True, "operation": "native_canary_reject", "dispatch_allowed": False,
            "application_result": result, "application_receipts": receipts,
            "resume_value": {record["binding"]["tool_call_id"]: {"type": "reject", "reason": "REJECTED"}}}


def _reject_only_adapter(path: Path, binding: CanaryBinding, revision: str, version: str,
                         mode: str, now: int) -> CanaryAdapter:
    class RejectOnlyProvider:
        def __init__(self):
            self.mode = mode
        def __getattr__(self, _name):
            raise ValueError("REJECT_ONLY_PROVIDER")
    return CanaryAdapter(path, binding, RejectOnlyProvider(), source_revision=revision,
                         source_version=version, clock=lambda: now)


@dataclass(frozen=True, repr=False)
class NativeCanaryBinding:
    principal_id: str
    tenant_id: str
    conversation_id: str
    action_id: str
    generation_id: str
    tool_call_id: str
    tool: str = _CANARY_TOOL

    def __post_init__(self) -> None:
        for value in (self.principal_id, self.tenant_id, self.conversation_id,
                      self.action_id, self.generation_id, self.tool_call_id):
            require_text(value, r"[A-Za-z0-9_.:-]{1,128}", "native identity")
        if self.tool != _CANARY_TOOL:
            raise ValueError("UNSUPPORTED_NATIVE_CANARY_TOOL")

    def digest(self) -> str:
        return canonical_digest({"principal_id": self.principal_id, "tenant_id": self.tenant_id,
                                 "conversation_id": self.conversation_id, "action_id": self.action_id,
                                 "generation_id": self.generation_id, "tool_call_id": self.tool_call_id,
                                 "tool": self.tool})


@dataclass(frozen=True, repr=False)
class NativeCanaryDecision:
    """Frozen server context returned by the native gate after the winning CAS.

    Native identity is kept as identity, never converted into an owner digest by
    this caller-facing structure. A separate trusted owner verifier must map it
    to the frozen packet principal. The host gate produces this value from
    req.user and the exact running generation; callers cannot assert a claim
    boolean to manufacture it.
    """

    batch_id: str
    authority_digest: str
    scope_digest: str
    source_revision: str
    principal_id: str
    tenant_id: str
    decision: str
    native_binding: NativeCanaryBinding
    decided_at: int
    expires_at: int
    decision_record_hash: str | None = None

    def __post_init__(self) -> None:
        if type(self.native_binding) is not NativeCanaryBinding:
            raise ValueError("INVALID_NATIVE_BINDING")
        require_text(self.batch_id, _BATCH.pattern, "canary batch")
        for value, label in (
            (self.authority_digest, "authority digest"),
            (self.scope_digest, "scope digest"),
            (self.native_binding.digest(), "native binding digest"),
        ):
            require_text(value, _HEX64.pattern, label)
        require_text(self.source_revision, r"[a-f0-9]{40}", "source revision")
        if self.decision not in ("approve", "reject"):
            raise ValueError("UNSUPPORTED_DECISION")
        require_text(self.principal_id, r"[A-Za-z0-9_.:-]{1,128}", "native principal")
        require_text(self.tenant_id, r"(?:system:single-tenant|tenant:[A-Za-z0-9_.:-]{1,128})", "native tenant")
        if (type(self.decided_at) is not int or type(self.expires_at) is not int
                or self.decided_at < 0 or self.expires_at <= self.decided_at):
            raise ValueError("INVALID_NATIVE_DECISION_CONTEXT")
        if self.decision_record_hash is not None:
            require_text(self.decision_record_hash, _HEX64.pattern, "native decision record")

    @classmethod
    def from_host_callback(cls, callback: dict, authority: FrozenCanaryAuthority,
                           *, received_at: int, decision_record_hash: str | None = None) -> "NativeCanaryDecision":
        """Bind the native gate's post-CAS handoff to the saved packet.

        This validates source output; it is not owner authentication. Production
        still needs an independent OwnerApprovalVerifier before application use.
        """
        if type(callback) is not dict or callback.get("version") != 1 or callback.get("operation") != "native_canary_choice":
            raise ValueError("INVALID_NATIVE_CALLBACK")
        binding = callback.get("binding")
        expected = {"principal_id", "tenant_id", "conversation_id", "action_id", "generation_id", "tool_call_id", "tool"}
        if type(binding) is not dict or set(binding) != expected:
            raise ValueError("INVALID_NATIVE_CALLBACK")
        if binding.get("tool") != _CANARY_TOOL:
            raise ValueError("UNSUPPORTED_NATIVE_CANARY_TOOL")
        if (callback.get("batch_id") != authority.batch_id
                or callback.get("scope_digest") != authority.scope_digest
                or callback.get("authority_digest") != authority.digest
                or callback.get("expires_at") != authority.decision_expires_at
                or callback.get("decision") not in ("approve", "reject")
                or callback.get("expires_at") <= received_at):
            raise ValueError("NATIVE_OWNER_DECISION_BINDING_MISMATCH")
        native = NativeCanaryBinding(
            binding["principal_id"], binding["tenant_id"], binding["conversation_id"],
            binding["action_id"], binding["generation_id"], binding["tool_call_id"], binding["tool"],
        )
        context = cls(
            batch_id=authority.batch_id, authority_digest=authority.digest,
            scope_digest=authority.scope_digest, source_revision=authority.source_revision,
            principal_id=binding["principal_id"], tenant_id=binding["tenant_id"],
            decision=callback["decision"], native_binding=native,
            decided_at=received_at, expires_at=callback["expires_at"],
        )
        return cls(
            batch_id=context.batch_id, authority_digest=context.authority_digest,
            scope_digest=context.scope_digest, source_revision=context.source_revision,
            principal_id=context.principal_id, tenant_id=context.tenant_id,
            decision=context.decision, native_binding=context.native_binding,
            decided_at=context.decided_at, expires_at=context.expires_at,
            decision_record_hash=decision_record_hash or context.digest,
        )

    @property
    def digest(self) -> str:
        """Stable private packet proof reference; never authentication alone."""
        return canonical_digest({
            "batchId": self.batch_id,
            "authorityDigest": self.authority_digest,
            "scopeDigest": self.scope_digest,
            "sourceRevision": self.source_revision,
            "principalId": self.principal_id,
            "tenantId": self.tenant_id,
            "decision": self.decision,
            "nativeBindingDigest": self.native_binding.digest(),
            "decidedAt": self.decided_at,
            "expiresAt": self.expires_at,
        })


class NativeCanaryApprovalAdapter:
    """Bridge one immutable host callback into the app's atomic one-use ledger.

    `verifier` must be provided by a mounted independently trusted host. With
    none, the existing application's TRUSTED_HUMAN_APPROVAL_BINDING_REQUIRED
    denial remains in force. This adapter never enables simulation or changes
    the live operator's default-deny path.
    """

    def __init__(self, application: CanaryApprovalApplication,
                 verifier: OwnerApprovalVerifier | None = None):
        self.application = application
        self.verifier = verifier

    def _bound_application(self, context: NativeCanaryDecision) -> tuple[CanaryApprovalApplication, OwnerApprovalPacket]:
        if type(context) is not NativeCanaryDecision:
            raise ValueError("INVALID_NATIVE_CALLBACK")
        authority, _saved = self.application._load_authority(context.batch_id)
        self.application._assert_current_authority(authority)
        if (context.authority_digest != authority.digest
                or context.scope_digest != authority.scope_digest
                or context.source_revision != authority.source_revision
                or context.expires_at > authority.decision_expires_at):
            raise ValueError("NATIVE_OWNER_DECISION_BINDING_MISMATCH")
        packet = OwnerApprovalPacket(
            packet_id="native-" + context.digest[:32],
            authority_digest=authority.digest,
            principal_binding_digest=authority.principal_binding_digest,
            decision="APPROVE_ONCE" if context.decision == "approve" else "REJECT",
            issued_at=context.decided_at,
            expires_at=authority.lifecycle_expires_at,
            proof=context.decision_record_hash or context.digest,
        )
        bound = CanaryApprovalApplication(
            self.application.path,
            self.application.binding,
            source_revision=self.application.revision,
            source_version=self.application.version,
            adapter_factory=self.application.adapter_factory,
            mode=self.application.mode,
            verifier=self.verifier,
            clock=self.application.clock,
        )
        return bound, packet

    def decide(self, context: NativeCanaryDecision) -> dict:
        application, packet = self._bound_application(context)
        return application.decide(packet)

    def cleanup(self, context: NativeCanaryDecision) -> dict:
        application, packet = self._bound_application(context)
        return application.cleanup(packet)

    def receipt(self, context: NativeCanaryDecision) -> list[dict]:
        application, packet = self._bound_application(context)
        return application.receipt(packet)

    def audit(self, context: NativeCanaryDecision) -> dict:
        application, packet = self._bound_application(context)
        return application.audit(packet)
