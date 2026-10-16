"""Application approval boundary for the Issue #90 fixed S3 canary.

This module defines no authentication mechanism and no permissive verifier. A
trusted host must inject an owner-packet verifier. The verifier runs before the
provider factory, and TEST_SIMULATION authorizations are accepted only with a
MOCK provider. The existing four-envelope interchange is unchanged.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import stat
import time
from typing import Callable, Protocol

from awsops.domain.models import canonical_digest, require_text
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding, REGION

SETUP_ACTIONS = ("create", "tags", "public_block", "policy")
CLEANUP_ACTION = "delete"
CLEANUP_READBACK = "fresh-owner-region-task-created-empty-no-foreign-state"
ASSURANCES = frozenset({"OWNER_AUTHENTICATED", "TEST_SIMULATION"})


def _epoch(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ValueError("INVALID_CANARY_EXPIRY") from None
    if parsed.tzinfo is None:
        raise ValueError("INVALID_CANARY_EXPIRY")
    return int(parsed.timestamp())


@dataclass(frozen=True)
class CleanupAuthority:
    enabled: bool
    resource_binding_digest: str
    action: str
    expires_at: int | None
    required_readback: str

    def public_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FrozenCanaryAuthority:
    batch_id: str
    scope_digest: str
    principal_binding_digest: str
    source_revision: str
    account_alias: str
    resource_alias: str
    region: str
    resource_binding_digest: str
    allowed_actions: tuple[str, ...]
    decision_expires_at: int
    estimated_incremental_cost_microusd: int
    cleanup_reserve_microusd: int
    incremental_cost_limit_microusd: int
    cleanup: CleanupAuthority

    def __post_init__(self) -> None:
        require_text(self.batch_id, r"batch-canary-[a-f0-9]{32}", "canary batch")
        require_text(self.scope_digest, r"[a-f0-9]{64}", "canary scope")
        require_text(self.principal_binding_digest, r"[a-f0-9]{64}", "principal binding")
        require_text(self.source_revision, r"[a-f0-9]{40}", "source revision")
        if self.region != REGION or self.allowed_actions != SETUP_ACTIONS:
            raise ValueError("UNAPPROVED_CANARY_ACTION_SCOPE")
        if (type(self.decision_expires_at) is not int or self.decision_expires_at <= 0
                or any(type(v) is not int or v < 0 for v in (
                    self.estimated_incremental_cost_microusd,
                    self.cleanup_reserve_microusd,
                    self.incremental_cost_limit_microusd))
                or self.incremental_cost_limit_microusd <= 0
                or self.estimated_incremental_cost_microusd + self.cleanup_reserve_microusd
                    > self.incremental_cost_limit_microusd):
            raise ValueError("INVALID_CANARY_COST_OR_EXPIRY")
        if self.cleanup.resource_binding_digest != self.resource_binding_digest:
            raise ValueError("CLEANUP_RESOURCE_BINDING_MISMATCH")
        if self.cleanup.enabled:
            if (self.cleanup.action != CLEANUP_ACTION
                    or self.cleanup.required_readback != CLEANUP_READBACK
                    or type(self.cleanup.expires_at) is not int
                    or self.cleanup.expires_at <= self.decision_expires_at
                    or self.cleanup_reserve_microusd <= 0):
                raise ValueError("INVALID_CLEANUP_AUTHORITY")
        elif (self.cleanup.expires_at is not None or self.cleanup.action != CLEANUP_ACTION
              or self.cleanup.required_readback != CLEANUP_READBACK
              or self.cleanup_reserve_microusd != 0):
            raise ValueError("UNEXPECTED_CLEANUP_AUTHORITY")

    def public_dict(self) -> dict:
        return {
            "batchId": self.batch_id,
            "scopeDigest": self.scope_digest,
            "principalBindingDigest": self.principal_binding_digest,
            "sourceRevision": self.source_revision,
            "accountAlias": self.account_alias,
            "resourceAlias": self.resource_alias,
            "region": self.region,
            "resourceBindingDigest": self.resource_binding_digest,
            "allowedActions": list(self.allowed_actions),
            "decisionExpiresAt": self.decision_expires_at,
            "estimatedIncrementalCostMicrousd": self.estimated_incremental_cost_microusd,
            "cleanupReserveMicrousd": self.cleanup_reserve_microusd,
            "incrementalCostLimitMicrousd": self.incremental_cost_limit_microusd,
            "cleanup": self.cleanup.public_dict(),
        }

    @property
    def digest(self) -> str:
        return canonical_digest(self.public_dict())

    @property
    def lifecycle_expires_at(self) -> int:
        return self.cleanup.expires_at if self.cleanup.enabled else self.decision_expires_at

    @classmethod
    def from_batch(cls, batch_envelope: dict, binding: CanaryBinding, principal: str,
                   source_revision: str, *, now: int,
                   estimated_incremental_cost_microusd: int,
                   cleanup_reserve_microusd: int,
                   incremental_cost_limit_microusd: int,
                   cleanup_expires_at: int | None) -> "FrozenCanaryAuthority":
        if (not isinstance(batch_envelope, dict)
                or set(batch_envelope) != {"schemaVersion", "kind", "record"}
                or batch_envelope["schemaVersion"] != "defence-factory/1"
                or batch_envelope["kind"] != "Batch"):
            raise ValueError("INVALID_CANARY_BATCH")
        record = batch_envelope["record"]
        targets = record.get("targets")
        if not isinstance(targets, list) or len(targets) != 1:
            raise ValueError("INVALID_CANARY_TARGET_SCOPE")
        target = targets[0]
        resource = target.get("resource", {})
        if (record.get("mode") not in ("MOCK", "APPROVED_LAB_WRITE")
                or target.get("controlId") != "s3-ssl-requests-only"
                or target.get("capabilityId") != "s3-require-tls"
                or target.get("expectedChange") != "DENY_INSECURE_TRANSPORT"
                or resource.get("resourceType") != "AWS::S3::Bucket"
                or resource.get("region") != binding.region
                or resource.get("resourceAlias") != "resource-disposable-s3-canary"):
            raise ValueError("UNAPPROVED_CANARY_TARGET_SCOPE")
        if (type(now) is not int or not _epoch(record.get("frozenAt")) <= now
                < _epoch(record.get("expiresAt"))):
            raise ValueError("PREPARATION_EXPIRED_OR_FUTURE")
        resource_digest = canonical_digest({
            "accountId": binding.account_id,
            "bucket": binding.bucket,
            "region": binding.region,
        })
        cleanup = CleanupAuthority(
            enabled=cleanup_expires_at is not None,
            resource_binding_digest=resource_digest,
            action=CLEANUP_ACTION,
            expires_at=cleanup_expires_at,
            required_readback=CLEANUP_READBACK,
        )
        if cleanup_expires_at is None:
            cleanup_reserve_microusd = 0
        return cls(
            batch_id=record.get("batchId"),
            scope_digest=record.get("scopeDigest"),
            principal_binding_digest=principal,
            source_revision=source_revision,
            account_alias=resource.get("accountAlias"),
            resource_alias=resource.get("resourceAlias"),
            region=resource.get("region"),
            resource_binding_digest=resource_digest,
            allowed_actions=SETUP_ACTIONS,
            decision_expires_at=_epoch(record.get("expiresAt")),
            estimated_incremental_cost_microusd=estimated_incremental_cost_microusd,
            cleanup_reserve_microusd=cleanup_reserve_microusd,
            incremental_cost_limit_microusd=incremental_cost_limit_microusd,
            cleanup=cleanup,
        )


@dataclass(frozen=True)
class OwnerApprovalPacket:
    """Private packet claims; proof bytes are never persisted or exported."""
    packet_id: str
    authority_digest: str
    principal_binding_digest: str
    decision: str
    issued_at: int
    expires_at: int
    proof: str = field(repr=False)

    def __post_init__(self) -> None:
        require_text(self.packet_id, r"[A-Za-z0-9_.:-]{1,128}", "packet id")
        require_text(self.authority_digest, r"[a-f0-9]{64}", "authority digest")
        require_text(self.principal_binding_digest, r"[a-f0-9]{64}", "principal binding")
        if self.decision not in ("APPROVE_ONCE", "REJECT"):
            raise ValueError("INVALID_DECISION")
        if (type(self.issued_at) is not int or type(self.expires_at) is not int
                or self.issued_at < 0 or self.expires_at <= self.issued_at
                or not isinstance(self.proof, str) or not self.proof):
            raise ValueError("INVALID_APPROVAL_PACKET")

    @property
    def digest(self) -> str:
        return canonical_digest({
            "packetId": self.packet_id,
            "authorityDigest": self.authority_digest,
            "principalBindingDigest": self.principal_binding_digest,
            "decision": self.decision,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
            "proofDigest": canonical_digest(self.proof),
        })


@dataclass(frozen=True)
class VerifiedOwnerDecision:
    """Verifier output; TEST_SIMULATION is accepted only for MOCK providers."""
    packet_digest: str
    authority_digest: str
    principal_binding_digest: str
    decision: str
    assurance: str
    verifier_id: str
    verified_at: int


class OwnerApprovalVerifier(Protocol):
    def verify(self, packet: OwnerApprovalPacket, authority: FrozenCanaryAuthority,
               *, action: str, now: int) -> VerifiedOwnerDecision: ...


class CanaryApprovalApplication:
    """Application seam around the existing durable canary adapter.

    `prepare` receives a caller-created adapter for read-only preparation. Every
    decision, reconciliation, cleanup and export path verifies the same frozen
    packet before invoking `adapter_factory`. Test simulation cannot use a
    non-MOCK mode and there is no simulation option in the production CLI.
    """

    def __init__(self, ledger: Path, binding: CanaryBinding, *, source_revision: str,
                 source_version: str, adapter_factory: Callable[[], CanaryAdapter],
                 mode: str, verifier: OwnerApprovalVerifier | None = None,
                 clock: Callable[[], float] = time.time):
        if mode not in ("MOCK", "APPROVED_LAB_WRITE"):
            raise ValueError("UNAPPROVED_TARGET")
        require_text(source_revision, r"[a-f0-9]{40}", "source revision")
        self.path, self.binding = Path(ledger), binding
        self.revision, self.version = source_revision, source_version
        self.adapter_factory, self.mode = adapter_factory, mode
        self.verifier, self.clock = verifier, clock
        self._check_file()
        with closing(self._db()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS application_authority (
                batch_id TEXT PRIMARY KEY, authority_json TEXT NOT NULL,
                authority_digest TEXT NOT NULL, principal_digest TEXT NOT NULL,
                packet_digest TEXT, assurance TEXT, verifier_id TEXT,
                choice TEXT, verified_at INTEGER, cleanup_status TEXT NOT NULL DEFAULT 'NOT_REQUESTED')""")

    def _check_file(self) -> None:
        mode = self.path.lstat().st_mode
        if self.path.is_symlink() or not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise ValueError("PRIVATE_LEDGER_REQUIRED")

    def _db(self):
        self._check_file()
        db = sqlite3.connect(self.path, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def prepare(self, adapter: CanaryAdapter, principal_digest: str, *, now: int,
                estimated_incremental_cost_microusd: int,
                cleanup_reserve_microusd: int,
                incremental_cost_limit_microusd: int,
                cleanup_expires_at: int | None) -> dict:
        if (adapter.path.resolve() != self.path.resolve() or adapter.binding != self.binding
                or adapter.mode != self.mode or adapter.revision != self.revision):
            raise ValueError("CANARY_PREPARATION_BINDING_MISMATCH")
        batch = adapter.prepare(principal_digest)
        authority = FrozenCanaryAuthority.from_batch(
            batch, self.binding, principal_digest, self.revision, now=now,
            estimated_incremental_cost_microusd=estimated_incremental_cost_microusd,
            cleanup_reserve_microusd=cleanup_reserve_microusd,
            incremental_cost_limit_microusd=incremental_cost_limit_microusd,
            cleanup_expires_at=cleanup_expires_at)
        if now >= authority.decision_expires_at:
            raise ValueError("PREPARATION_EXPIRED_OR_FUTURE")
        with closing(self._db()) as db:
            db.execute("INSERT INTO application_authority VALUES (?,?,?,?,NULL,NULL,NULL,NULL,NULL,'NOT_REQUESTED')",
                       (authority.batch_id, json.dumps(authority.public_dict(), sort_keys=True),
                        authority.digest, principal_digest))
        return batch

    def _load_authority(self, batch_id: str) -> tuple[FrozenCanaryAuthority, tuple]:
        with closing(self._db()) as db:
            row = db.execute("""SELECT authority_json,authority_digest,principal_digest,packet_digest,
                              assurance,verifier_id,choice,verified_at,cleanup_status
                              FROM application_authority WHERE batch_id=?""", (batch_id,)).fetchone()
        if not row:
            raise ValueError("CANARY_AUTHORITY_NOT_FOUND")
        value = json.loads(row[0])
        cleanup = value["cleanup"]
        authority = FrozenCanaryAuthority(
            batch_id=value["batchId"], scope_digest=value["scopeDigest"],
            principal_binding_digest=value["principalBindingDigest"],
            source_revision=value["sourceRevision"], account_alias=value["accountAlias"],
            resource_alias=value["resourceAlias"], region=value["region"],
            resource_binding_digest=value["resourceBindingDigest"],
            allowed_actions=tuple(value["allowedActions"]),
            decision_expires_at=value["decisionExpiresAt"],
            estimated_incremental_cost_microusd=value["estimatedIncrementalCostMicrousd"],
            cleanup_reserve_microusd=value["cleanupReserveMicrousd"],
            incremental_cost_limit_microusd=value["incrementalCostLimitMicrousd"],
            cleanup=CleanupAuthority(**cleanup),
        )
        if (authority.public_dict() != value or authority.digest != row[1]
                or authority.principal_binding_digest != row[2]):
            raise ValueError("CANARY_AUTHORITY_INTEGRITY_FAILURE")
        return authority, row[3:]

    def _verified(self, packet: OwnerApprovalPacket, authority: FrozenCanaryAuthority,
                  *, action: str) -> VerifiedOwnerDecision:
        now = int(self.clock())
        if self.verifier is None:
            raise ValueError("TRUSTED_HUMAN_APPROVAL_BINDING_REQUIRED")
        if (packet.authority_digest != authority.digest
                or packet.principal_binding_digest != authority.principal_binding_digest
                or packet.expires_at != authority.lifecycle_expires_at
                or not packet.issued_at <= now < packet.expires_at):
            raise ValueError("APPROVAL_PACKET_SCOPE_OR_EXPIRY_MISMATCH")
        if action == "DECISION" and not now < authority.decision_expires_at:
            raise ValueError("APPROVAL_DECISION_EXPIRED")
        if action == "CLEANUP" and (not authority.cleanup.enabled
                                     or not now < authority.cleanup.expires_at):
            raise ValueError("CLEANUP_AUTHORITY_EXPIRED_OR_MISSING")
        verified = self.verifier.verify(packet, authority, action=action, now=now)
        if (type(verified) is not VerifiedOwnerDecision
                or verified.packet_digest != packet.digest
                or verified.authority_digest != authority.digest
                or verified.principal_binding_digest != authority.principal_binding_digest
                or verified.decision != packet.decision
                or verified.assurance not in ASSURANCES
                or not isinstance(verified.verifier_id, str) or not verified.verifier_id
                or type(verified.verified_at) is not int
                or not packet.issued_at <= verified.verified_at <= now
                or verified.verified_at >= packet.expires_at):
            raise ValueError("OWNER_DECISION_VERIFICATION_FAILED")
        if verified.assurance == "TEST_SIMULATION" and self.mode != "MOCK":
            raise ValueError("TEST_SIMULATION_CANNOT_AUTHORIZE_LIVE_PROVIDER")
        return verified

    def _adapter(self, authority: FrozenCanaryAuthority) -> CanaryAdapter:
        adapter = self.adapter_factory()
        if (type(adapter) is not CanaryAdapter or adapter.path.resolve() != self.path.resolve()
                or adapter.binding != self.binding or adapter.mode != self.mode
                or adapter.revision != authority.source_revision):
            raise ValueError("CANARY_ADAPTER_BINDING_MISMATCH")
        return adapter

    def decide(self, packet: OwnerApprovalPacket) -> dict:
        authority, saved = self._load_authority(self._batch_for_digest(packet.authority_digest))
        verified = self._verified(packet, authority, action="DECISION")
        if packet.decision not in ("APPROVE_ONCE", "REJECT"):
            raise ValueError("INVALID_DECISION")
        existing_packet, assurance, verifier_id, choice, _verified_at, _cleanup_status = saved
        if existing_packet is not None and (existing_packet != packet.digest or choice != packet.decision):
            raise ValueError("APPROVAL_ALREADY_CONSUMED")
        with closing(self._db()) as db:
            db.execute("UPDATE application_authority SET packet_digest=?,assurance=?,verifier_id=?,choice=?,verified_at=? WHERE batch_id=?",
                       (packet.digest, verified.assurance, verified.verifier_id, packet.decision,
                        verified.verified_at, authority.batch_id))
        adapter = self._adapter(authority)
        if self._canary_decision_exists(authority.batch_id):
            result = adapter.reconcile(authority.batch_id, authority.principal_binding_digest)
            return self._result_envelopes(adapter, authority, result)
        result = adapter.decide(authority.batch_id, authority.scope_digest,
                                authority.principal_binding_digest, packet.decision)
        return result

    def cleanup(self, packet: OwnerApprovalPacket) -> dict:
        if type(packet) is not OwnerApprovalPacket:
            raise ValueError("INVALID_APPROVAL_PACKET")
        authority, saved = self._load_authority(self._batch_for_digest(packet.authority_digest))
        verified = self._verified(packet, authority, action="CLEANUP")
        packet_digest, assurance, verifier_id, choice, _verified_at, cleanup_status = saved
        if (packet_digest != packet.digest or choice != "APPROVE_ONCE"
                or assurance != verified.assurance or verifier_id != verified.verifier_id):
            raise ValueError("CLEANUP_APPROVAL_NOT_BOUND")
        adapter = self._adapter(authority)
        prior = adapter.cleanup_state(authority.batch_id, authority.principal_binding_digest)
        if prior["status"] != "NOT_REQUESTED":
            result = prior
        else:
            result = adapter.cleanup(authority.batch_id, authority.principal_binding_digest,
                                     expires_at=authority.cleanup.expires_at)
        with closing(self._db()) as db:
            db.execute("UPDATE application_authority SET cleanup_status=? WHERE batch_id=?",
                       (result["status"], authority.batch_id))
        return result

    def receipt(self, packet: OwnerApprovalPacket) -> list[dict]:
        if type(packet) is not OwnerApprovalPacket:
            raise ValueError("INVALID_APPROVAL_PACKET")
        authority, saved = self._load_authority(self._batch_for_digest(packet.authority_digest))
        if saved[0] != packet.digest or saved[3] not in ("APPROVE_ONCE", "REJECT"):
            raise ValueError("CANARY_DECISION_NOT_VERIFIED")
        adapter = self._adapter(authority)
        return adapter.receipt(authority.batch_id, authority.principal_binding_digest)

    def audit(self, packet: OwnerApprovalPacket) -> dict:
        if type(packet) is not OwnerApprovalPacket:
            raise ValueError("INVALID_APPROVAL_PACKET")
        authority, saved = self._load_authority(self._batch_for_digest(packet.authority_digest))
        packet_digest, assurance, verifier_id, choice, verified_at, cleanup_status = saved
        if packet_digest != packet.digest or choice not in ("APPROVE_ONCE", "REJECT"):
            raise ValueError("CANARY_DECISION_NOT_VERIFIED")
        with closing(self._db()) as db:
            operations = db.execute("SELECT step,state FROM operations WHERE batch_id=? ORDER BY rowid",
                                    (authority.batch_id,)).fetchall()
        return {
            "schemaVersion": "awsops-issue90-application-audit/1",
            "batchId": authority.batch_id,
            "authorityDigest": authority.digest,
            "packetDigest": packet.digest,
            "sourceRevision": authority.source_revision,
            "decision": choice,
            "verification": assurance,
            "verifierId": verifier_id,
            "verifiedAt": verified_at,
            "allowedActions": list(authority.allowed_actions),
            "cleanupAuthority": authority.cleanup.public_dict(),
            "operations": [{"step": step, "state": state} for step, state in operations],
            "cleanupStatus": cleanup_status,
            "provenance": "SYNTHETIC" if self.mode == "MOCK" else "TRUSTED_PROVIDER_READ",
            "limitation": "SYNTHETIC_ONLY" if self.mode == "MOCK" else "FRESHNESS_NOT_VERIFIED",
        }

    def _batch_for_digest(self, authority_digest: str) -> str:
        require_text(authority_digest, r"[a-f0-9]{64}", "authority digest")
        with closing(self._db()) as db:
            row = db.execute("SELECT batch_id FROM application_authority WHERE authority_digest=?",
                             (authority_digest,)).fetchone()
        if not row:
            raise ValueError("CANARY_AUTHORITY_NOT_FOUND")
        return row[0]

    def _canary_decision_exists(self, batch_id: str) -> bool:
        with closing(self._db()) as db:
            row = db.execute("SELECT decision FROM canaries WHERE batch_id=?", (batch_id,)).fetchone()
        return bool(row and row[0] is not None)

    def _result_envelopes(self, adapter: CanaryAdapter, authority: FrozenCanaryAuthority,
                          result: dict) -> dict:
        return {"batch": {"schemaVersion": "defence-factory/1", "kind": "Batch",
                           "record": json.loads(self._batch_payload(authority.batch_id))},
                "decision": {"schemaVersion": "defence-factory/1", "kind": "Decision",
                             "record": json.loads(self._decision_payload(authority.batch_id))},
                "run": result["run"], "evidence": result["evidence"]}

    def _batch_payload(self, batch_id: str) -> str:
        with closing(self._db()) as db:
            row = db.execute("SELECT payload FROM canaries WHERE batch_id=?", (batch_id,)).fetchone()
        return row[0]

    def _decision_payload(self, batch_id: str) -> str:
        with closing(self._db()) as db:
            row = db.execute("SELECT decision FROM canaries WHERE batch_id=?", (batch_id,)).fetchone()
        return row[0]
